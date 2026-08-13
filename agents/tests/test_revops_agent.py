"""Live, end-to-end test for revops_agent: runs the real pipeline against a
real model and a real Firestore emulator, the same way a user asking
`adk web` to sweep the CRM would trigger it.

Needs a running Firestore emulator (FIRESTORE_EMULATOR_HOST set), see
docs/revops-agent.md; skips cleanly if that's not available rather than
failing. Spends real API quota when it does run: roughly 5 model calls
(crm, hygiene, forecast, draft, package). Not something to run on every
save, see agents/tests/run_all.py.

Run directly: cd agents && uv run python tests/test_revops_agent.py
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

_AGENTS_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_AGENTS_DIR))
sys.path.insert(0, str(_AGENTS_DIR / "revops_agent" / "scripts"))

from dotenv import load_dotenv

load_dotenv(_AGENTS_DIR / ".env")

from live_runner import run_agent_live  # noqa: E402

from revops_agent.agent import root_agent  # noqa: E402

_USER_TEXT = "Sweep the CRM for hygiene issues and sharpen the forecast."


def test_sweep_crm_end_to_end():
    if not os.environ.get("GOOGLE_API_KEY"):
        print("SKIP: GOOGLE_API_KEY not set, can't run revops_agent live.")
        return
    if not os.environ.get("FIRESTORE_EMULATOR_HOST"):
        print(
            "SKIP: FIRESTORE_EMULATOR_HOST not set, no Firestore emulator to "
            "read CRM records from. See docs/revops-agent.md."
        )
        return

    import seed_firestore

    try:
        seed_firestore.main()
    except Exception as e:  # emulator not actually reachable despite the env var
        print(f"SKIP: could not seed Firestore ({e!r}). Is the emulator running?")
        return

    events, state = asyncio.run(run_agent_live(root_agent, _USER_TEXT))
    assert events, "Expected at least one event from the run."

    accounts = state.get("accounts")
    assert isinstance(accounts, str) and accounts != "[]", accounts

    swept_deals = state.get("swept_deals")
    assert isinstance(swept_deals, str) and swept_deals != "[]", swept_deals

    forecast = state.get("forecast")
    assert isinstance(forecast, str) and forecast != "[]", forecast

    drafts = state.get("drafts")
    assert isinstance(drafts, list) and drafts, drafts
    for draft in drafts:
        assert draft["subject_type"] in ("deal", "account_pair"), draft
        assert draft["confidence"] in ("high", "medium", "low"), draft
        assert isinstance(draft["needs_review"], bool), draft
        assert draft["subject_id"], draft

    # The duplicate account pair is a merge decision, never rubber-stamped.
    duplicate_drafts = [d for d in drafts if d["subject_type"] == "account_pair"]
    assert duplicate_drafts, drafts
    assert all(d["needs_review"] for d in duplicate_drafts), duplicate_drafts

    final_document = state.get("final_document")
    assert isinstance(final_document, str) and final_document.strip(), final_document
    assert "# CRM Hygiene & Forecast Report" in final_document, final_document
    assert "Meridian" in final_document, final_document


if __name__ == "__main__":
    checks = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for check in checks:
        check()
        print(f"ok: {check.__name__}")
    print(f"{len(checks)} checks passed")
