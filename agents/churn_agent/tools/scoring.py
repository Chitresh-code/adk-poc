"""Deterministic churn-risk scoring, no model call involved.

Risk tiers have to be explainable and reproducible from the same fixture
data every run, not whatever a model free-forms this time, so this is
ordinary code, not an LlmAgent step.
"""

from __future__ import annotations

import json

from google.adk.tools import ToolContext

_USAGE_DECLINE_THRESHOLD = -0.15
_USAGE_GROWTH_THRESHOLD = 0.15
_SENTIMENT_NEGATIVE_THRESHOLD = -0.2
_OPEN_RISK_SEVERITIES = {"critical", "high"}


def _usage_trend(usage: dict | None) -> tuple[str, float]:
    if not usage:
        return "unknown", 0.0
    prior, current = usage["mau_prior"], usage["mau_current"]
    change = (current - prior) / prior if prior else 0.0
    if change <= _USAGE_DECLINE_THRESHOLD:
        return "declining", change
    if change >= _USAGE_GROWTH_THRESHOLD:
        return "growing", change
    return "flat", change


def _open_risk_tickets(tickets: list[dict]) -> list[dict]:
    return [
        t
        for t in tickets
        if t["status"] == "open" and t["severity"] in _OPEN_RISK_SEVERITIES
    ]


def _rationale(usage: dict | None, trend: str, change: float, open_tickets: list[dict], sentiment: dict) -> list[str]:
    lines = []
    if trend != "unknown":
        direction = "declined" if trend == "declining" else "grew" if trend == "growing" else "held steady"
        lines.append(
            f"Usage {direction} {abs(change):.0%} "
            f"({usage['mau_prior']} -> {usage['mau_current']} monthly active users)"
        )
    for t in open_tickets:
        lines.append(f"Open {t['severity']} ticket: {t['subject']}")
    if sentiment:
        lines.append(
            f"Sentiment trending {sentiment.get('trend', 'unknown')} "
            f"(score {sentiment.get('score')})"
        )
    if not lines:
        lines.append("No churn or expansion signals this cycle.")
    return lines


async def score_churn_risk(tool_context: ToolContext) -> dict:
    """Scores each joined account record into a risk tier and note type.

    Sets skip_summarization on every path, matching every other tool-only
    step in this pipeline: the LLM is forced to call this tool (see
    agent.py), and without skip_summarization that would also force a
    second, pointless tool-call attempt on the follow-up summarization turn.

    Always sets state["scored_accounts"] before returning, including on the
    error path (to "[]"): the research step's instruction interpolates
    {accounts_with_context} downstream of this key unconditionally, and a
    missing state key there raises a KeyError deep in ADK's instruction
    templating instead of a readable error, so this step must never leave
    that key unset.

    Risk tier rules: "high" is a usage decline of 15%+ combined with an open
    critical/high ticket or negative sentiment (score below -0.2); "medium"
    is any single one of those three signals on its own; "low" is none of
    them. A "low" account with 15%+ usage growth and no negative signal is
    an expansion candidate. Accounts flagged "high" or "medium" get
    note_type "qbr_prep"; expansion candidates get "cross_sell"; every other
    account gets note_type None and no note downstream, "flags churn risk
    early" only means something if stable accounts are visibly skipped, not
    every account getting a note regardless.

    Returns:
        A dict with "scored_count", or "error" if state["accounts"] is
        missing (signal intake must run first).
    """
    tool_context.actions.skip_summarization = True

    accounts_raw = tool_context.state.get("accounts")
    if not accounts_raw:
        tool_context.state["scored_accounts"] = "[]"
        return {"error": "No accounts in state. Run signal intake first."}

    accounts = json.loads(accounts_raw)
    scored = []
    for account in accounts:
        trend, change = _usage_trend(account.get("usage"))
        open_tickets = _open_risk_tickets(account.get("tickets", []))
        sentiment = account.get("sentiment") or {}
        sentiment_negative = sentiment.get("score", 0.0) < _SENTIMENT_NEGATIVE_THRESHOLD

        declining = trend == "declining"
        growing = trend == "growing"
        flagged = declining or bool(open_tickets) or sentiment_negative

        if declining and (open_tickets or sentiment_negative):
            risk_tier = "high"
        elif flagged:
            risk_tier = "medium"
        else:
            risk_tier = "low"

        expansion_candidate = growing and not open_tickets and not sentiment_negative

        if risk_tier in ("high", "medium"):
            note_type = "qbr_prep"
        elif expansion_candidate:
            note_type = "cross_sell"
        else:
            note_type = None

        scored.append(
            {
                "account_id": account["account_id"],
                "name": account["name"],
                "industry": account["industry"],
                "segment": account["segment"],
                "risk_tier": risk_tier,
                "note_type": note_type,
                "rationale": _rationale(account.get("usage"), trend, change, open_tickets, sentiment),
            }
        )

    tool_context.state["scored_accounts"] = json.dumps(scored, indent=2)
    return {"scored_count": len(scored)}
