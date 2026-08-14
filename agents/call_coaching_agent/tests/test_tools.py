"""Self-check for deterministic tool logic (no LLM, Firestore emulator, or
Whisper model load involved).

Run directly: uv run python tests/test_tools.py

load_call's audio-transcription branch and load_deal_context aren't covered
here: one needs a real Whisper model load, the other a real Firestore
emulator. Run the agent end to end in `adk web`, or see
agents/tests/test_call_coaching_agent.py, to validate those paths.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

_AGENT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_AGENT_DIR))
sys.path.insert(0, str(_AGENT_DIR.parent))

from google.genai import types

from tools import packaging
from tools.intake import load_call

_FIXTURES_DIR = Path(__file__).resolve().parent.parent / "data" / "fixtures"


class _FakeActions:
    skip_summarization = None


class _FakeToolContext:
    def __init__(self, state: dict, user_content: types.Content | None = None):
        self.state = dict(state)
        self.actions = _FakeActions()
        self.user_content = user_content


def _text_turn(text: str) -> types.Content:
    return types.Content(role="user", parts=[types.Part(text=text)])


def _attachment_turn(data: bytes, mime_type: str) -> types.Content:
    return types.Content(
        role="user",
        parts=[types.Part(inline_data=types.Blob(data=data, mime_type=mime_type))],
    )


def test_load_call_pasted_text():
    ctx = _FakeToolContext({}, _text_turn("Rep: Hi. Prospect: Hi back."))
    result = asyncio.run(load_call(ctx))
    assert "error" not in result, result
    assert ctx.state["transcript_text"] == "Rep: Hi. Prospect: Hi back."
    assert ctx.state["call_source"] == "pasted text"
    assert ctx.actions.skip_summarization is True


def test_load_call_transcript_attachment():
    transcript = (_FIXTURES_DIR / "meridian_health_negotiation_call.md").read_text(encoding="utf-8")
    ctx = _FakeToolContext({}, _attachment_turn(transcript.encode("utf-8"), "text/markdown"))
    result = asyncio.run(load_call(ctx))
    assert "error" not in result, result
    assert ctx.state["transcript_text"] == transcript
    assert "transcript attachment" in ctx.state["call_source"]


def test_load_call_unsupported_attachment():
    ctx = _FakeToolContext({}, _attachment_turn(b"not real", "application/zip"))
    result = asyncio.run(load_call(ctx))
    assert "error" in result
    assert ctx.state["transcript_text"] == ""
    assert ctx.actions.skip_summarization is True


def test_load_call_no_input():
    ctx = _FakeToolContext({}, _text_turn(""))
    result = asyncio.run(load_call(ctx))
    assert "error" in result
    assert ctx.state["transcript_text"] == ""
    assert ctx.actions.skip_summarization is True


def _analysis(**overrides) -> dict:
    base = {
        "matched_account_id": "acct_pinecrest",
        "matched_account_name": "Pinecrest Robotics",
        "matched_deal_id": "deal_pinecrest_renewal",
        "matched_deal_stage": "negotiation",
        "elements_covered": ["metrics", "economic_buyer", "competition"],
        "elements_missing": ["paper_process"],
        "methodology_tier": "strong",
        "competitor_mentions": ["Vantage Ops"],
        "risk_level": "high",
        "risk_rationale": "Competitor Vantage Ops is in a late-stage price comparison.",
    }
    base.update(overrides)
    return base


def _note(**overrides) -> dict:
    base = {
        "summary": "Strong methodology coverage, but Vantage Ops is actively being compared on price.",
        "coaching_actions": ["Send the revised quote with the value recap before the prospect decides."],
        "confidence": "medium",
        "needs_review": True,
    }
    base.update(overrides)
    return base


def test_update_crm_and_package_writes_when_flagged_and_matched():
    ctx = _FakeToolContext(
        {"analysis": _analysis(), "coaching_note": _note(), "transcript_text": "...", "call_source": "pasted text"}
    )
    result = asyncio.run(packaging.update_crm_and_package(ctx))
    assert "error" not in result, result
    markdown = result["markdown"]
    assert "# Call Coaching Report" in markdown
    assert "Pinecrest Robotics" in markdown
    assert "Vantage Ops" in markdown
    assert "Needs review:** yes" in markdown
    assert "CRM update skipped: FIRESTORE_EMULATOR_HOST is not set." in markdown
    assert ctx.actions.skip_summarization is True
    assert ctx.state["final_document"] == markdown


def test_update_crm_and_package_skips_when_low_risk():
    ctx = _FakeToolContext(
        {
            "analysis": _analysis(risk_level="low", competitor_mentions=[], risk_rationale="Clean call, no risk signals."),
            "coaching_note": _note(needs_review=False, confidence="high"),
            "transcript_text": "...",
            "call_source": "pasted text",
        }
    )
    result = asyncio.run(packaging.update_crm_and_package(ctx))
    assert "error" not in result, result
    assert "CRM update skipped: risk level is low" in result["markdown"]


def test_update_crm_and_package_skips_when_unmatched():
    ctx = _FakeToolContext(
        {
            "analysis": _analysis(matched_account_id=None, matched_account_name=None, matched_deal_id=None, matched_deal_stage=None),
            "coaching_note": _note(),
            "transcript_text": "...",
            "call_source": "pasted text",
        }
    )
    result = asyncio.run(packaging.update_crm_and_package(ctx))
    assert "error" not in result, result
    assert "CRM update skipped: no deal was matched" in result["markdown"]
    assert "_No CRM deal could be confidently matched to this call._" in result["markdown"]


def test_update_crm_and_package_missing_state():
    ctx = _FakeToolContext({})
    result = asyncio.run(packaging.update_crm_and_package(ctx))
    assert "error" in result
    assert ctx.actions.skip_summarization is True


if __name__ == "__main__":
    checks = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for check in checks:
        check()
        print(f"ok: {check.__name__}")
    print(f"{len(checks)} checks passed")
