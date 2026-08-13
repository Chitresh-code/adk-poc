"""Self-check for deterministic tool logic (no LLM or Firestore emulator calls).

Run directly: uv run python tests/test_tools.py

load_crm_records isn't covered here: it needs a real Firestore emulator,
same as account_research_agent's pull_signals. Run the agent end to end in
`adk web` (with the emulator running and seeded) to validate that path.
"""

from __future__ import annotations

import asyncio
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.seed_firestore import _prepare_deal
from tools import forecast, hygiene, packaging

_SEED_DIR = Path(__file__).resolve().parent.parent / "data" / "seed"


class _FakeActions:
    skip_summarization = None


class _FakeToolContext:
    def __init__(self, state: dict):
        self.state = dict(state)
        self.actions = _FakeActions()


def _load_fixture_state() -> dict:
    accounts = json.loads((_SEED_DIR / "accounts.json").read_text(encoding="utf-8"))
    deals_raw = json.loads((_SEED_DIR / "deals.json").read_text(encoding="utf-8"))
    accounts_by_id = {a["account_id"]: a for a in accounts}
    now = datetime.now(timezone.utc)
    deals = []
    for deal in deals_raw:
        prepared = _prepare_deal(dict(deal), now)
        account = accounts_by_id[prepared["account_id"]]
        deals.append(
            {
                **prepared,
                "account_name": account["name"],
                "industry": account["industry"],
                "segment": account["segment"],
            }
        )
    return {"accounts": json.dumps(accounts), "deals": json.dumps(deals)}


def test_sweep_crm_hygiene():
    ctx = _FakeToolContext(_load_fixture_state())
    result = asyncio.run(hygiene.sweep_crm_hygiene(ctx))
    assert "error" not in result, result
    swept = json.loads(ctx.state["swept_deals"])
    by_id = {d["deal_id"]: d for d in swept}

    # closed_won deals are excluded from the sweep entirely
    assert "deal_meridian_renewal_prior" not in by_id

    assert by_id["deal_meridian_expansion"]["issue_types"] == []
    assert by_id["deal_meridian_dup_renewal"]["issue_types"] == []
    assert by_id["deal_pinecrest_renewal"]["issue_types"] == ["missing_fields"]
    assert by_id["deal_fernwood_addon"]["issue_types"] == ["stalled"]
    assert by_id["deal_brightline_upsell"]["issue_types"] == ["stale"]
    assert by_id["deal_solace_renewal"]["issue_types"] == []

    duplicate_pairs = json.loads(ctx.state["duplicate_pairs"])
    assert len(duplicate_pairs) == 1
    pair = duplicate_pairs[0]
    assert {pair["account_id_a"], pair["account_id_b"]} == {"acct_meridian", "acct_meridian_dup"}
    assert ctx.actions.skip_summarization is True


def test_sweep_crm_hygiene_missing_state():
    ctx = _FakeToolContext({})
    result = asyncio.run(hygiene.sweep_crm_hygiene(ctx))
    assert "error" in result
    assert ctx.state["swept_deals"] == "[]"
    assert ctx.actions.skip_summarization is True


def test_sharpen_forecast():
    ctx = _FakeToolContext(_load_fixture_state())
    asyncio.run(hygiene.sweep_crm_hygiene(ctx))
    result = asyncio.run(forecast.sharpen_forecast(ctx))
    assert "error" not in result, result
    data = json.loads(ctx.state["forecast"])
    by_id = {d["deal_id"]: d for d in data["deals"]}

    assert by_id["deal_meridian_expansion"]["sharpened_category"] == "commit"
    assert by_id["deal_pinecrest_renewal"]["sharpened_category"] == "unforecastable"
    assert by_id["deal_fernwood_addon"]["sharpened_category"] == "pipeline"
    assert by_id["deal_brightline_upsell"]["sharpened_category"] == "best_case"
    assert by_id["deal_solace_renewal"]["sharpened_category"] == "pipeline"

    assert data["unforecastable_deal_ids"] == ["deal_pinecrest_renewal"]
    assert ctx.actions.skip_summarization is True


def test_sharpen_forecast_missing_state():
    ctx = _FakeToolContext({})
    result = asyncio.run(forecast.sharpen_forecast(ctx))
    assert "error" in result
    assert ctx.actions.skip_summarization is True


def test_assemble_hygiene_report():
    ctx = _FakeToolContext(_load_fixture_state())
    asyncio.run(hygiene.sweep_crm_hygiene(ctx))
    asyncio.run(forecast.sharpen_forecast(ctx))
    ctx.state["drafts"] = [
        {
            "subject_type": "deal",
            "subject_id": "deal_pinecrest_renewal",
            "issue_types": ["missing_fields"],
            "summary": "Pinecrest's renewal is missing an amount and close date.",
            "recommended_fix": "Ask Priya Anand to fill in amount and close date.",
            "confidence": "high",
            "needs_review": False,
        },
        {
            "subject_type": "account_pair",
            "subject_id": "acct_meridian|acct_meridian_dup",
            "issue_types": ["possible_duplicate"],
            "summary": "Meridian Health and Meridian Healthcare Group share a domain.",
            "recommended_fix": "Confirm and merge into acct_meridian, it has the larger active deal.",
            "confidence": "medium",
            "needs_review": True,
        },
    ]
    result = asyncio.run(packaging.assemble_hygiene_report(ctx))
    assert "error" not in result, result
    markdown = result["markdown"]
    assert "Pinecrest Robotics" in markdown
    assert "Meridian Health" in markdown
    assert "Brightline Logistics" in markdown
    assert "Solace Media" in markdown
    assert "Needs review:** yes" in markdown
    assert ctx.actions.skip_summarization is True
    assert ctx.state["final_document"] == markdown


def test_assemble_hygiene_report_missing_state():
    ctx = _FakeToolContext({})
    result = asyncio.run(packaging.assemble_hygiene_report(ctx))
    assert "error" in result
    assert ctx.actions.skip_summarization is True


if __name__ == "__main__":
    checks = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for check in checks:
        check()
        print(f"ok: {check.__name__}")
    print(f"{len(checks)} checks passed")
