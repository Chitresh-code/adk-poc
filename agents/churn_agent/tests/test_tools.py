"""Self-check for deterministic tool logic (no LLM or corpus-embedding calls).

Run directly: uv run python tests/test_tools.py

research_playbook's corpus search isn't covered here: it needs a real
GOOGLE_API_KEY for embeddings, same as rfp_agent's retrieval and
account_research_agent's research_account. Run the agent end to end in
`adk web` to validate that path.
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools import packaging, scoring, signals


class _FakeActions:
    skip_summarization = None


class _FakeToolContext:
    def __init__(self, state: dict):
        self.state = dict(state)
        self.actions = _FakeActions()


def test_load_account_signals():
    ctx = _FakeToolContext({})
    result = asyncio.run(signals.load_account_signals(ctx))
    assert "error" not in result, result
    accounts = json.loads(ctx.state["accounts"])
    assert result["account_count"] == len(accounts) == 5
    meridian = next(a for a in accounts if a["account_id"] == "acct_meridian")
    assert meridian["usage"]["mau_current"] == 110
    assert len(meridian["tickets"]) == 1
    assert meridian["sentiment"]["trend"] == "declining"
    solace = next(a for a in accounts if a["account_id"] == "acct_solace")
    assert solace["tickets"] == []
    assert ctx.actions.skip_summarization is True


def test_score_churn_risk():
    ctx = _FakeToolContext({})
    asyncio.run(signals.load_account_signals(ctx))
    result = asyncio.run(scoring.score_churn_risk(ctx))
    assert "error" not in result, result
    scored = json.loads(ctx.state["scored_accounts"])
    by_id = {a["account_id"]: a for a in scored}

    # declining usage plus an open critical/high ticket or negative sentiment
    assert by_id["acct_meridian"]["risk_tier"] == "high"
    assert by_id["acct_meridian"]["note_type"] == "qbr_prep"
    assert by_id["acct_pinecrest"]["risk_tier"] == "high"
    assert by_id["acct_pinecrest"]["note_type"] == "qbr_prep"

    # a single flag (negative sentiment alone, usage held flat) -> medium
    assert by_id["acct_fernwood"]["risk_tier"] == "medium"
    assert by_id["acct_fernwood"]["note_type"] == "qbr_prep"

    # growing usage, no open risk ticket, no negative sentiment -> expansion
    assert by_id["acct_brightline"]["risk_tier"] == "low"
    assert by_id["acct_brightline"]["note_type"] == "cross_sell"

    # flat usage, no signals -> stable, no note
    assert by_id["acct_solace"]["risk_tier"] == "low"
    assert by_id["acct_solace"]["note_type"] is None
    assert ctx.actions.skip_summarization is True


def test_score_churn_risk_missing_state():
    ctx = _FakeToolContext({})
    result = asyncio.run(scoring.score_churn_risk(ctx))
    assert "error" in result
    assert ctx.state["scored_accounts"] == "[]"
    assert ctx.actions.skip_summarization is True


def test_assemble_account_packet():
    scored_accounts = json.dumps(
        [
            {
                "account_id": "acct_meridian",
                "name": "Meridian Health",
                "industry": "healthcare",
                "segment": "mid-market",
                "risk_tier": "high",
                "note_type": "qbr_prep",
                "rationale": ["Usage declined 39%"],
            },
            {
                "account_id": "acct_solace",
                "name": "Solace Media",
                "industry": "media",
                "segment": "mid-market",
                "risk_tier": "low",
                "note_type": None,
                "rationale": ["No churn or expansion signals this cycle."],
            },
        ]
    )
    drafts = [
        {
            "account_id": "acct_meridian",
            "note_type": "qbr_prep",
            "summary": "Sync failures are driving disengagement.",
            "recommended_actions": ["Schedule a health-check call this week."],
            "confidence": "high",
            "needs_review": False,
        }
    ]
    ctx = _FakeToolContext({"scored_accounts": scored_accounts, "drafts": drafts})
    result = asyncio.run(packaging.assemble_account_packet(ctx))
    assert "error" not in result, result
    markdown = result["markdown"]
    assert "Meridian Health" in markdown
    assert "Sync failures are driving disengagement." in markdown
    assert "Solace Media" in markdown
    assert "## Stable: no action needed" in markdown
    assert ctx.actions.skip_summarization is True
    assert ctx.state["final_document"] == markdown


def test_assemble_account_packet_missing_state():
    ctx = _FakeToolContext({})
    result = asyncio.run(packaging.assemble_account_packet(ctx))
    assert "error" in result
    assert ctx.actions.skip_summarization is True


if __name__ == "__main__":
    checks = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for check in checks:
        check()
        print(f"ok: {check.__name__}")
    print(f"{len(checks)} checks passed")
