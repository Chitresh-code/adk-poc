"""Live, end-to-end test for churn_agent: runs the real pipeline against a
real model and a real corpus, the same way a user asking `adk web` to
check account health would trigger it.

Spends real API quota: this run makes roughly 5 model calls (signals,
scoring, research, draft, package) plus one embedding call per flagged
account for corpus search. Not something to run on every save, see
agents/tests/run_all.py.

Run directly: cd agents && uv run python tests/test_churn_agent.py
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

_AGENTS_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_AGENTS_DIR))

from dotenv import load_dotenv

load_dotenv(_AGENTS_DIR / ".env")

from live_runner import run_agent_live  # noqa: E402

from churn_agent.agent import root_agent  # noqa: E402

_USER_TEXT = "Check account health and prepare QBR and cross-sell notes."


def test_check_account_health_end_to_end():
    if not os.environ.get("GOOGLE_API_KEY"):
        print("SKIP: GOOGLE_API_KEY not set, can't run churn_agent live.")
        return

    events, state = asyncio.run(run_agent_live(root_agent, _USER_TEXT))
    assert events, "Expected at least one event from the run."

    accounts = state.get("accounts")
    assert isinstance(accounts, str) and accounts != "[]", accounts

    scored_accounts = state.get("scored_accounts")
    assert isinstance(scored_accounts, str) and scored_accounts != "[]", scored_accounts

    drafts = state.get("drafts")
    assert isinstance(drafts, list) and drafts, drafts
    for draft in drafts:
        assert draft["note_type"] in ("qbr_prep", "cross_sell"), draft
        assert draft["confidence"] in ("high", "medium", "low"), draft
        assert isinstance(draft["needs_review"], bool), draft
        assert draft["account_id"], draft

    # needs_review depends on the model's live judgment call of whether a
    # retrieved play actually supports the account (Pinecrest's industry has
    # no dedicated play in the corpus by design, but a generic retrieved play
    # can still legitimately apply), so it isn't asserted here; only that the
    # pipeline produces at least one confident, grounded note.
    confidences = {d["confidence"] for d in drafts}
    assert confidences & {"high", "medium"}, drafts

    final_document = state.get("final_document")
    assert isinstance(final_document, str) and final_document.strip(), final_document
    assert "# Account Health Packet" in final_document, final_document
    assert "Meridian Health" in final_document, final_document


if __name__ == "__main__":
    checks = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for check in checks:
        check()
        print(f"ok: {check.__name__}")
    print(f"{len(checks)} checks passed")
