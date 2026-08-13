"""Publishes a batch of fake buying-signal messages to the local Pub/Sub emulator.

Creates the topic and subscription if they don't exist yet. Run this before
asking the agent to check for new signals: the pipeline only ever pulls, it
never publishes on its own. Requires PUBSUB_EMULATOR_HOST to be set, see
docs/agent-2-account-research-agent.md.

Run: uv run python account_research_agent/scripts/publish_fake_signals.py
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.signals import SUBSCRIPTION_ID, TOPIC_ID, project_id

_FAKE_SIGNALS = [
    {
        "account_id": "acct_meridian",
        "signal_type": "job_posting",
        "detail": '"VP of Platform Engineering" role opened',
    },
    {
        "account_id": "acct_brightline",
        "signal_type": "funding_round",
        "detail": "Closed a $40M Series C",
    },
    {
        "account_id": "acct_fernwood",
        "signal_type": "executive_change",
        "detail": "New CTO announced",
    },
    {
        "account_id": "acct_pinecrest",
        "signal_type": "pricing_page_visit",
        "detail": "Visited the pricing page three times this week",
    },
    {
        "account_id": "acct_solace",
        "signal_type": "competitor_mention",
        "detail": "Mentioned a competitor's platform in a public review",
    },
]


def _should_publish(subscription_created: bool) -> bool:
    return subscription_created or os.environ.get("SEED_ONLY_ON_CREATE") != "1"


def main() -> None:
    if not os.environ.get("PUBSUB_EMULATOR_HOST"):
        raise SystemExit(
            "PUBSUB_EMULATOR_HOST is not set. Start the Pub/Sub emulator "
            "and export it first, see docs/agent-2-account-research-agent.md."
        )

    from google.api_core.exceptions import AlreadyExists
    from google.cloud import pubsub_v1

    pid = project_id()
    publisher = pubsub_v1.PublisherClient()
    subscriber = pubsub_v1.SubscriberClient()
    topic_path = publisher.topic_path(pid, TOPIC_ID)
    subscription_path = subscriber.subscription_path(pid, SUBSCRIPTION_ID)

    try:
        publisher.create_topic(request={"name": topic_path})
    except AlreadyExists:
        pass
    subscription_created = False
    try:
        subscriber.create_subscription(
            request={"name": subscription_path, "topic": topic_path}
        )
        subscription_created = True
    except AlreadyExists:
        pass

    if not _should_publish(subscription_created):
        print(f"Signals already initialized for {subscription_path}; skipping")
        return

    for signal in _FAKE_SIGNALS:
        payload = {**signal, "timestamp": datetime.now(timezone.utc).isoformat()}
        publisher.publish(topic_path, json.dumps(payload).encode("utf-8")).result()

    print(f"Published {len(_FAKE_SIGNALS)} fake signals to {topic_path}")


if __name__ == "__main__":
    main()
