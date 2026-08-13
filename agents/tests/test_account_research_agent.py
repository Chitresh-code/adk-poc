"""Live, end-to-end test for account_research_agent: runs the real pipeline
against a real model, a real corpus, and a real Pub/Sub emulator, the same
way a user asking `adk web` to check for new signals would trigger it.

Needs a running Pub/Sub emulator (PUBSUB_EMULATOR_HOST set), see
docs/agent-2-account-research-agent.md; skips cleanly if that's not
available rather than failing. Spends real API quota when it does run:
roughly 5 model calls (signals, research, buyers, draft, package) plus one
embedding call per signal for corpus search. Not something to run on every
save, see agents/tests/run_all.py.

Run directly: cd agents && uv run python tests/test_account_research_agent.py
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

_AGENTS_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_AGENTS_DIR))
sys.path.insert(0, str(_AGENTS_DIR / "account_research_agent" / "scripts"))

from dotenv import load_dotenv

load_dotenv(_AGENTS_DIR / ".env")

from live_runner import run_agent_live  # noqa: E402

from account_research_agent.agent import root_agent  # noqa: E402

_USER_TEXT = "Check for new buying signals."


def test_check_signals_end_to_end():
    if not os.environ.get("GOOGLE_API_KEY"):
        print("SKIP: GOOGLE_API_KEY not set, can't run account_research_agent live.")
        return
    if not os.environ.get("PUBSUB_EMULATOR_HOST"):
        print(
            "SKIP: PUBSUB_EMULATOR_HOST not set, no Pub/Sub emulator to pull "
            "signals from. See docs/agent-2-account-research-agent.md."
        )
        return

    import publish_fake_signals

    try:
        publish_fake_signals.main()
    except Exception as e:  # emulator not actually reachable despite the env var
        print(f"SKIP: could not publish fake signals ({e!r}). Is the emulator running?")
        return

    events, state = asyncio.run(run_agent_live(root_agent, _USER_TEXT))
    assert events, "Expected at least one event from the run."

    signals = state.get("signals")
    assert isinstance(signals, list) and signals, signals

    mapped_signals = state.get("mapped_signals")
    assert isinstance(mapped_signals, str) and mapped_signals != "[]", mapped_signals

    drafts = state.get("drafts")
    assert isinstance(drafts, list) and drafts, drafts
    for draft in drafts:
        assert draft["confidence"] in ("high", "medium", "low"), draft
        assert isinstance(draft["needs_review"], bool), draft
        assert draft["account_id"], draft

    final_document = state.get("final_document")
    assert isinstance(final_document, str) and final_document.strip(), final_document
    assert "# Outreach Packet" in final_document, final_document


if __name__ == "__main__":
    checks = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for check in checks:
        check()
        print(f"ok: {check.__name__}")
    print(f"{len(checks)} checks passed")
