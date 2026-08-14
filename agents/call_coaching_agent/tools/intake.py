"""Reads a sales call from the current chat turn into transcript text.

Handles three ways a call can arrive in `adk web`, converging on the same
plain-text transcript regardless of which one was used: an audio file
attached to the chat turn (transcribed locally with faster-whisper, no
cloud speech API), a transcript file attached to the chat turn, or text
pasted directly into the chat. Format for attachments is decided by MIME
type, matching rfp_agent/tools/intake.py's dispatch pattern.

Transcription runs entirely locally: faster-whisper (open-weight Whisper
models via ctranslate2) needs no network access and sends no audio to any
third party, keeping call content off any external service, consistent
with this repo's fixture-data-only, no-live-SaaS-integration boundary (see
docs/plan.md).
"""

from __future__ import annotations

import io
import os

from google.adk.tools import ToolContext

_TEXT_EXTENSIONS = {
    "text/plain": ".txt",
    "text/markdown": ".md",
}

_AUDIO_EXTENSIONS = {
    "audio/mpeg": ".mp3",
    "audio/mp3": ".mp3",
    "audio/wav": ".wav",
    "audio/x-wav": ".wav",
    "audio/wave": ".wav",
    "audio/mp4": ".m4a",
    "audio/x-m4a": ".m4a",
    "audio/webm": ".webm",
    "audio/ogg": ".ogg",
    "audio/flac": ".flac",
    "audio/x-flac": ".flac",
}

_DEFAULT_WHISPER_MODEL_SIZE = "base"

_whisper_model = None  # lazy singleton, loaded once per process on first use


def _get_whisper_model():
    global _whisper_model
    if _whisper_model is None:
        from faster_whisper import WhisperModel

        model_size = os.environ.get("WHISPER_MODEL_SIZE", _DEFAULT_WHISPER_MODEL_SIZE)
        _whisper_model = WhisperModel(model_size, device="cpu", compute_type="int8")
    return _whisper_model


def _parse_text(data: bytes) -> str:
    return data.decode("utf-8", errors="replace")


def _transcribe_audio(data: bytes) -> str:
    model = _get_whisper_model()
    segments, _info = model.transcribe(io.BytesIO(data))
    return " ".join(segment.text.strip() for segment in segments)


async def load_call(tool_context: ToolContext) -> dict:
    """Reads the call from this turn: an attached file, or pasted text.

    Sets skip_summarization on every path, matching every other tool-only
    step in this pipeline: the LLM is forced to call this tool (see
    agent.py), and without skip_summarization that would also force a
    second, pointless tool-call attempt on the follow-up summarization turn.

    Args:
        tool_context: injected by ADK, gives access to the current turn.

    Always sets state["transcript_text"] before returning, including on the
    error path (to ""): the analyze step's instruction interpolates
    {transcript_text} unconditionally, and a missing state key there raises
    a KeyError deep in ADK's instruction templating instead of a readable
    error, so this step must never leave that key unset.

    Returns:
        A dict with "source", or "error" if no audio, transcript file, or
        pasted text was found on this turn.
    """
    tool_context.actions.skip_summarization = True

    user_content = tool_context.user_content
    if user_content is not None and user_content.parts:
        for part in user_content.parts:
            if part.inline_data is not None and part.inline_data.data:
                mime_type = part.inline_data.mime_type or ""
                if mime_type in _AUDIO_EXTENSIONS:
                    transcript = _transcribe_audio(part.inline_data.data)
                    source = f"audio attachment ({mime_type}, transcribed locally)"
                elif mime_type in _TEXT_EXTENSIONS:
                    transcript = _parse_text(part.inline_data.data)
                    source = f"transcript attachment ({mime_type})"
                else:
                    tool_context.state["transcript_text"] = ""
                    tool_context.state["call_source"] = "none"
                    return {
                        "error": (
                            f"Unsupported attachment type {mime_type!r}. "
                            f"Supported audio: {', '.join(sorted(set(_AUDIO_EXTENSIONS)))}. "
                            f"Supported transcript files: {', '.join(sorted(set(_TEXT_EXTENSIONS)))}."
                        )
                    }
                if transcript.strip():
                    tool_context.state["transcript_text"] = transcript
                    tool_context.state["call_source"] = source
                    return {"source": source}

        pasted_text = "\n".join(p.text for p in user_content.parts if p.text)
        if pasted_text.strip():
            tool_context.state["transcript_text"] = pasted_text
            tool_context.state["call_source"] = "pasted text"
            return {"source": "pasted text"}

    tool_context.state["transcript_text"] = ""
    tool_context.state["call_source"] = "none"
    return {
        "error": (
            "No call found. Attach an audio file, attach a transcript "
            "(.txt/.md), or paste the call transcript directly in chat."
        )
    }
