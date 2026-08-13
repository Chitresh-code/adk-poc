"""Pulls fake buying-signal messages from the local Pub/Sub emulator.

google-cloud-pubsub connects to PUBSUB_EMULATOR_HOST automatically (no
credentials needed) whenever that env var is set. Nothing publishes on its
own: run scripts/publish_fake_signals.py first, which also creates the topic
and subscription this reads from. See docs/account-research-agent.md.
"""

from __future__ import annotations

import json
import os

from google.adk.tools import ToolContext

TOPIC_ID = "account-buying-signals"
SUBSCRIPTION_ID = "account-buying-signals-sub"
_DEFAULT_PROJECT_ID = "adk-poc-local"


def project_id() -> str:
    return os.environ.get("PUBSUB_PROJECT_ID") or os.environ.get(
        "GOOGLE_CLOUD_PROJECT", _DEFAULT_PROJECT_ID
    )


def _parse_signal(data: bytes) -> dict:
    """Decodes one published message's JSON payload into a signal dict."""
    payload = json.loads(data.decode("utf-8"))
    return {
        "account_id": payload["account_id"],
        "signal_type": payload["signal_type"],
        "detail": payload["detail"],
        "timestamp": payload["timestamp"],
    }


async def pull_signals(tool_context: ToolContext, max_messages: int = 10) -> dict:
    """Pulls and acknowledges pending buying-signal messages from the emulator.

    Sets skip_summarization on every path, matching every other tool-only
    step in this pipeline: the LLM is forced to call this tool (see
    agent.py), and without skip_summarization that would also force a
    second, pointless tool-call attempt on the follow-up summarization turn.

    Args:
        tool_context: injected by ADK, gives access to session state.
        max_messages: upper bound on how many pending signals to pull.

    Returns:
        A dict with "signal_count", or "error" if the emulator isn't
        configured, the topic/subscription doesn't exist yet, or nothing is
        pending.
    """
    tool_context.actions.skip_summarization = True

    if not os.environ.get("PUBSUB_EMULATOR_HOST"):
        return {
            "error": (
                "PUBSUB_EMULATOR_HOST is not set. Start the Pub/Sub "
                "emulator and export it first, see "
                "docs/account-research-agent.md."
            )
        }

    from google.api_core.exceptions import NotFound
    from google.cloud import pubsub_v1

    subscriber = pubsub_v1.SubscriberClient()
    subscription_path = subscriber.subscription_path(project_id(), SUBSCRIPTION_ID)

    with subscriber:
        try:
            response = subscriber.pull(
                request={
                    "subscription": subscription_path,
                    "max_messages": max_messages,
                }
            )
        except NotFound:
            return {
                "error": (
                    "No subscription found. Run "
                    "scripts/publish_fake_signals.py first, it creates the "
                    "topic and subscription."
                )
            }

        if not response.received_messages:
            return {
                "error": "No pending signals. Run scripts/publish_fake_signals.py first."
            }

        signals = [_parse_signal(m.message.data) for m in response.received_messages]
        subscriber.acknowledge(
            request={
                "subscription": subscription_path,
                "ack_ids": [m.ack_id for m in response.received_messages],
            }
        )

    tool_context.state["signals"] = signals
    return {"signal_count": len(signals)}
