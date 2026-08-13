"""Live, end-to-end test for rfp_agent: runs the real pipeline against a
real model and a real corpus, the same way a user pasting text into `adk
web` would trigger it.

Spends real API quota: this run makes roughly 5 model calls (intake,
decompose, retrieve, draft, package) plus one embedding call per question
for corpus search. Not something to run on every save, see
agents/tests/run_all.py.

Run directly: cd agents && uv run python tests/test_rfp_agent.py
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from live_runner import run_agent_live  # noqa: E402

from rfp_agent.agent import root_agent  # noqa: E402

# "Are you SOC 2 certified?" is covered by data/corpus/past_answers/soc2.md.
# "On-premise deployment" is one of the two categories the corpus
# deliberately doesn't cover, see docs/rfp-agent.md's corpus
# seeding section, so this pasted questionnaire exercises both the grounded
# and the needs-SME-review paths in one run.
_SAMPLE_QUESTIONNAIRE = """Security Questionnaire

1. Are you SOC 2 certified? If so, which trust principles are covered?
2. Do you offer an on-premise deployment option?
"""


def test_paste_text_end_to_end():
    if not os.environ.get("GOOGLE_API_KEY"):
        print("SKIP: GOOGLE_API_KEY not set, can't run rfp_agent live.")
        return

    events, state = asyncio.run(run_agent_live(root_agent, _SAMPLE_QUESTIONNAIRE))
    assert events, "Expected at least one event from the run."

    assert state.get("source_filename") == "pasted_text", state.get("source_filename")

    questions = state.get("questions")
    assert isinstance(questions, list) and len(questions) == 2, questions

    drafts = state.get("drafts")
    assert isinstance(drafts, list) and len(drafts) == 2, drafts
    for draft in drafts:
        assert draft["confidence"] in ("high", "medium", "low"), draft
        assert isinstance(draft["needs_sme_review"], bool), draft

    # The corpus covers SOC 2 but not on-premise deployment, so this run
    # should produce at least one confident, sourced answer and at least
    # one needing SME review, not five-out-of-five in either direction.
    confidences = {d["confidence"] for d in drafts}
    needs_review_flags = {d["needs_sme_review"] for d in drafts}
    assert confidences & {"high", "medium"}, drafts
    assert True in needs_review_flags, drafts

    final_document = state.get("final_document")
    assert isinstance(final_document, str) and final_document.strip(), final_document
    assert "# RFP Response Draft" in final_document, final_document
    assert "Are you SOC 2 certified" in final_document, final_document


if __name__ == "__main__":
    checks = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for check in checks:
        check()
        print(f"ok: {check.__name__}")
    print(f"{len(checks)} checks passed")
