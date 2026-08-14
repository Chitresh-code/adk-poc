"""Live, end-to-end tests for call_coaching_agent: runs the real pipeline
against a real model and a real Firestore emulator, the same way a user
pasting a call transcript into `adk web` would trigger it. A second test
covers the local Whisper transcription path in isolation, using a
throwaway audio clip synthesized on the fly (macOS `say` only; skips
cleanly on platforms without a local TTS command, since this repo ships no
audio fixtures, see docs/call-coaching-agent.md).

Needs a running Firestore emulator (FIRESTORE_EMULATOR_HOST set), seeded
with revops_agent's fixture accounts/deals, since call_coaching_agent
matches calls against the same CRM data revops_agent reads. Skips cleanly
if that's not available rather than failing. Spends real API quota when it
does run: roughly 2 model calls for the pipeline test (analyze, draft).

Run directly: cd agents && uv run python tests/test_call_coaching_agent.py
"""

from __future__ import annotations

import asyncio
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

_AGENTS_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_AGENTS_DIR))
sys.path.insert(0, str(_AGENTS_DIR / "revops_agent" / "scripts"))

from dotenv import load_dotenv

load_dotenv(_AGENTS_DIR / ".env")

from live_runner import run_agent_live  # noqa: E402

from call_coaching_agent.agent import root_agent  # noqa: E402
from call_coaching_agent.tools.intake import load_call  # noqa: E402

_FIXTURE_TRANSCRIPT = (
    _AGENTS_DIR / "call_coaching_agent" / "data" / "fixtures" / "pinecrest_robotics_negotiation_call.md"
).read_text(encoding="utf-8")


def test_analyze_call_end_to_end():
    if not os.environ.get("GOOGLE_API_KEY"):
        print("SKIP: GOOGLE_API_KEY not set, can't run call_coaching_agent live.")
        return
    if not os.environ.get("FIRESTORE_EMULATOR_HOST"):
        print(
            "SKIP: FIRESTORE_EMULATOR_HOST not set, no Firestore emulator to "
            "match calls against. See docs/call-coaching-agent.md."
        )
        return

    import seed_firestore

    try:
        seed_firestore.main()
    except Exception as e:  # emulator not actually reachable despite the env var
        print(f"SKIP: could not seed Firestore ({e!r}). Is the emulator running?")
        return

    events, state = asyncio.run(run_agent_live(root_agent, _FIXTURE_TRANSCRIPT))
    assert events, "Expected at least one event from the run."

    assert state.get("transcript_text") == _FIXTURE_TRANSCRIPT
    assert state.get("call_source") == "pasted text"

    candidate_deals = json.loads(state.get("candidate_deals") or "[]")
    assert candidate_deals, "Expected candidate deals from the seeded CRM."

    analysis = state.get("analysis")
    assert isinstance(analysis, dict), analysis
    assert analysis["methodology_tier"] in ("strong", "adequate", "weak"), analysis
    assert analysis["risk_level"] in ("high", "medium", "low"), analysis
    assert isinstance(analysis["competitor_mentions"], list), analysis

    note = state.get("coaching_note")
    assert isinstance(note, dict), note
    assert note["confidence"] in ("high", "medium", "low"), note
    assert isinstance(note["needs_review"], bool), note
    assert note["coaching_actions"], note

    final_document = state.get("final_document")
    assert isinstance(final_document, str) and final_document.strip(), final_document
    assert "# Call Coaching Report" in final_document, final_document

    if analysis["matched_deal_id"] and analysis["risk_level"] in ("high", "medium"):
        from google.cloud import firestore
        from google.cloud.firestore_v1.base_query import FieldFilter

        from call_coaching_agent.tools.packaging import CALL_COACHING_COLLECTION
        from revops_agent.tools.crm import project_id

        client = firestore.Client(project=project_id())
        notes = list(
            client.collection(CALL_COACHING_COLLECTION)
            .where(filter=FieldFilter("deal_id", "==", analysis["matched_deal_id"]))
            .stream()
        )
        assert notes, "Expected a written call_coaching_notes doc for the matched, flagged deal."
        print(f"  CRM write verified: {len(notes)} note(s) for {analysis['matched_deal_id']}.")
    else:
        print(f"  No CRM write expected this run (matched_deal_id={analysis['matched_deal_id']!r}, risk_level={analysis['risk_level']!r}).")


def test_audio_transcription_live():
    if shutil.which("say") is None:
        print("SKIP: no local TTS command (`say`) available to synthesize a test clip.")
        return

    class _FakeActions:
        skip_summarization = None

    class _FakePart:
        def __init__(self, data: bytes, mime_type: str):
            self.text = None
            self.inline_data = _FakeBlob(data, mime_type)

    class _FakeBlob:
        def __init__(self, data: bytes, mime_type: str):
            self.data = data
            self.mime_type = mime_type

    class _FakeContent:
        def __init__(self, parts):
            self.parts = parts

    class _FakeToolContext:
        def __init__(self, parts):
            self.state: dict = {}
            self.actions = _FakeActions()
            self.user_content = _FakeContent(parts)

    with tempfile.TemporaryDirectory() as tmp:
        wav_path = Path(tmp) / "clip.wav"
        subprocess.run(
            ["say", "-o", str(wav_path), "--data-format=LEF32@22050", "Confirm the budget owner before the next call."],
            check=True,
            capture_output=True,
        )
        data = wav_path.read_bytes()

    ctx = _FakeToolContext([_FakePart(data, "audio/wav")])
    result = asyncio.run(load_call(ctx))
    assert "error" not in result, result
    transcript = ctx.state["transcript_text"]
    assert transcript.strip(), "Expected non-empty transcript from local Whisper transcription."
    print(f"  Transcribed: {transcript!r}")
    assert "budget" in transcript.lower(), transcript


if __name__ == "__main__":
    checks = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for check in checks:
        check()
        print(f"ok: {check.__name__}")
    print(f"{len(checks)} checks passed")
