"""Self-check for deterministic tool logic (no LLM or Pub/Sub calls involved).

Run directly: uv run python tests/test_tools.py

research_account's corpus search isn't covered here: it needs a real
GOOGLE_API_KEY for embeddings, so it's not something a static check can
honestly verify, same as rfp_agent's retrieval. pull_signals's emulator
round-trip isn't covered either: it needs a running Pub/Sub emulator. Run
the agent end to end in `adk web` to validate both paths.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools import buyers, packaging
from tools.signals import _parse_signal
from scripts.publish_fake_signals import _should_publish
from schemas import OutreachDraftList


class _FakeActions:
    skip_summarization = None


class _FakeToolContext:
    def __init__(self, state: dict):
        self.state = dict(state)
        self.actions = _FakeActions()


def test_parse_signal():
    payload = {
        "account_id": "acct_meridian",
        "signal_type": "job_posting",
        "detail": '"VP of Platform Engineering" role opened',
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    data = json.dumps(payload).encode("utf-8")
    assert _parse_signal(data) == payload


def test_automatic_seed_runs_once_per_subscription():
    previous = os.environ.get("SEED_ONLY_ON_CREATE")
    try:
        os.environ["SEED_ONLY_ON_CREATE"] = "1"
        assert _should_publish(subscription_created=True)
        assert not _should_publish(subscription_created=False)
        del os.environ["SEED_ONLY_ON_CREATE"]
        assert _should_publish(subscription_created=False)
    finally:
        if previous is None:
            os.environ.pop("SEED_ONLY_ON_CREATE", None)
        else:
            os.environ["SEED_ONLY_ON_CREATE"] = previous


def test_map_buyers():
    researched_signals = json.dumps(
        [
            {
                "account_id": "acct_meridian",
                "signal_type": "job_posting",
                "detail": "test",
                "timestamp": "2026-01-01T00:00:00+00:00",
                "account": {"account_id": "acct_meridian", "name": "Meridian Health"},
                "proof_points": [],
            }
        ]
    )
    ctx = _FakeToolContext({"researched_signals": researched_signals})
    result = asyncio.run(buyers.map_buyers(ctx))
    assert "error" not in result, result
    mapped = json.loads(ctx.state["mapped_signals"])
    assert len(mapped) == 1
    target_personas = {c["persona"] for c in mapped[0]["target_contacts"]}
    assert target_personas == {"eng_leadership", "it_ops"}, target_personas
    assert ctx.actions.skip_summarization is True


def test_map_buyers_missing_state():
    ctx = _FakeToolContext({})
    result = asyncio.run(buyers.map_buyers(ctx))
    assert "error" in result
    assert ctx.actions.skip_summarization is True


def test_assemble_outreach_packet():
    mapped_signals = json.dumps(
        [
            {
                "account_id": "acct_meridian",
                "signal_type": "job_posting",
                "detail": '"VP of Platform Engineering" role opened',
                "account": {"account_id": "acct_meridian", "name": "Meridian Health"},
                "target_contacts": [],
            }
        ]
    )
    drafts = [
        {
            "account_id": "acct_meridian",
            "contact_name": "Dana Whitfield",
            "contact_title": "VP of Platform Engineering",
            "subject": "Scaling platform engineering at Meridian",
            "body": "Saw the new role you posted...",
            "confidence": "high",
            "needs_review": False,
        }
    ]
    ctx = _FakeToolContext(
        {"mapped_signals": mapped_signals, "drafts": {"items": drafts}}
    )
    result = asyncio.run(packaging.assemble_outreach_packet(ctx))
    assert isinstance(result, str), result
    markdown = result
    assert "Meridian Health" in markdown
    assert "Dana Whitfield" in markdown
    assert "Scaling platform engineering at Meridian" in markdown
    assert ctx.actions.skip_summarization is True
    assert ctx.state["drafts"] == drafts
    assert ctx.state["final_document"] == markdown


def test_assemble_outreach_packet_missing_state():
    ctx = _FakeToolContext({})
    result = asyncio.run(packaging.assemble_outreach_packet(ctx))
    assert "error" in result
    assert ctx.actions.skip_summarization is True


def test_output_schema_has_object_root():
    assert OutreachDraftList.model_json_schema()["type"] == "object"


if __name__ == "__main__":
    checks = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for check in checks:
        check()
        print(f"ok: {check.__name__}")
    print(f"{len(checks)} checks passed")
