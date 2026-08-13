"""Deterministic CRM hygiene sweep: missing fields, stale activity, stalled
stage duration, and possible duplicate accounts.

Ordinary Python, not a model call, for the same reason churn_agent's risk
scoring is: hygiene flags need to be explainable and reproducible from the
same CRM snapshot every run, not a model's best guess at what looks off.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

from google.adk.tools import ToolContext

# Only open deals get swept; closed_won/closed_lost deals are done, flagging
# them as "stale" or "stalled" would be noise.
_STALLED_STAGE_THRESHOLD_DAYS = {
    "discovery": 21,
    "qualification": 21,
    "proposal": 25,
    "negotiation": 20,
}
_STALE_ACTIVITY_THRESHOLD_DAYS = 21
_REQUIRED_FIELDS = ("amount", "close_date", "next_step")


def _days_since(iso_str: str, now: datetime) -> int:
    then = datetime.fromisoformat(iso_str)
    return (now - then).days


def _missing_fields(deal: dict) -> list[str]:
    return [field for field in _REQUIRED_FIELDS if not deal.get(field)]


def _rationale(missing: list[str], stale_days: int | None, stalled_days: int | None, stage: str) -> list[str]:
    points = []
    if missing:
        points.append(f"Missing required field(s): {', '.join(missing)}.")
    if stale_days is not None:
        points.append(
            f"No activity in {stale_days} days (threshold: {_STALE_ACTIVITY_THRESHOLD_DAYS})."
        )
    if stalled_days is not None:
        points.append(
            f"In {stage} stage for {stalled_days} days "
            f"(threshold: {_STALLED_STAGE_THRESHOLD_DAYS[stage]})."
        )
    return points


def _normalize_domain(domain: str) -> str:
    return domain.strip().lower().removeprefix("https://").removeprefix("http://").removeprefix("www.").rstrip("/")


def _duplicate_pairs(accounts: list[dict]) -> list[dict]:
    by_domain: dict[str, list[dict]] = {}
    for account in accounts:
        by_domain.setdefault(_normalize_domain(account["domain"]), []).append(account)

    pairs = []
    for domain, group in by_domain.items():
        if len(group) < 2:
            continue
        for i in range(len(group)):
            for j in range(i + 1, len(group)):
                pairs.append(
                    {
                        "account_id_a": group[i]["account_id"],
                        "account_name_a": group[i]["name"],
                        "account_id_b": group[j]["account_id"],
                        "account_name_b": group[j]["name"],
                        "matched_on": "domain",
                        "domain": domain,
                    }
                )
    return pairs


async def sweep_crm_hygiene(tool_context: ToolContext) -> dict:
    """Flags missing fields, staleness, stalled stage duration, and duplicate accounts.

    Sets skip_summarization on every path, matching every other tool-only
    step in this pipeline: the LLM is forced to call this tool (see
    agent.py), and without skip_summarization that would also force a
    second, pointless tool-call attempt on the follow-up summarization turn.

    Args:
        tool_context: injected by ADK, gives access to session state.

    Returns:
        A dict with "flagged_count" and "duplicate_pair_count", or "error"
        if state["deals"]/state["accounts"] are missing (run load_crm_records
        first).
    """
    tool_context.actions.skip_summarization = True

    deals_raw = tool_context.state.get("deals")
    accounts_raw = tool_context.state.get("accounts")
    if not deals_raw or not accounts_raw:
        tool_context.state["swept_deals"] = "[]"
        tool_context.state["duplicate_pairs"] = "[]"
        return {"error": "No CRM records in state. Run load_crm_records first."}

    deals = json.loads(deals_raw)
    accounts = json.loads(accounts_raw)
    now = datetime.now(timezone.utc)

    swept = []
    for deal in deals:
        stage = deal["stage"]
        if stage not in _STALLED_STAGE_THRESHOLD_DAYS:
            continue  # closed_won / closed_lost: nothing to sweep

        missing = _missing_fields(deal)

        activity_days = _days_since(deal["last_activity_at"], now)
        stale_days = activity_days if activity_days > _STALE_ACTIVITY_THRESHOLD_DAYS else None

        stage_days = _days_since(deal["stage_entered_at"], now)
        stalled_days = (
            stage_days if stage_days > _STALLED_STAGE_THRESHOLD_DAYS[stage] else None
        )

        issue_types = []
        if missing:
            issue_types.append("missing_fields")
        if stale_days is not None:
            issue_types.append("stale")
        if stalled_days is not None:
            issue_types.append("stalled")

        swept.append(
            {
                **deal,
                "issue_types": issue_types,
                "rationale": _rationale(missing, stale_days, stalled_days, stage),
            }
        )

    # Duplicate accounts are an account-level issue, not a deal-level one:
    # a deal under either account isn't itself wrong, so this doesn't touch
    # swept deals' issue_types, it's reported as its own section.
    duplicate_pairs = _duplicate_pairs(accounts)

    tool_context.state["swept_deals"] = json.dumps(swept)
    tool_context.state["duplicate_pairs"] = json.dumps(duplicate_pairs)
    return {
        "flagged_count": sum(1 for d in swept if d["issue_types"]),
        "duplicate_pair_count": len(duplicate_pairs),
    }
