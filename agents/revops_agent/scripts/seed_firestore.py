"""Loads the fixture accounts and deals into the local Firestore emulator.

Converts each deal's relative day-offsets (close_date_days_from_now,
stage_entered_days_ago, last_activity_days_ago) into absolute timestamps at
seed time, so the demo's staleness/stalled-stage math stays correct
whenever this is run, not just on the day the fixtures were written.
Overwrites both collections on every run (Firestore document IDs are set
directly, no dedup logic needed the way Pub/Sub's ack'd queue needed one).
Requires FIRESTORE_EMULATOR_HOST to be set, see docs/revops-agent.md.

Run: uv run python revops_agent/scripts/seed_firestore.py
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.crm import ACCOUNTS_COLLECTION, DEALS_COLLECTION, project_id

_SEED_DIR = Path(__file__).resolve().parent.parent / "data" / "seed"


def _prepare_deal(deal: dict, now: datetime) -> dict:
    close_days = deal.pop("close_date_days_from_now")
    stage_days_ago = deal.pop("stage_entered_days_ago")
    activity_days_ago = deal.pop("last_activity_days_ago")
    return {
        **deal,
        "close_date": (now + timedelta(days=close_days)).date().isoformat() if close_days is not None else None,
        "stage_entered_at": (now - timedelta(days=stage_days_ago)).isoformat(),
        "last_activity_at": (now - timedelta(days=activity_days_ago)).isoformat(),
    }


def main() -> None:
    if not os.environ.get("FIRESTORE_EMULATOR_HOST"):
        raise SystemExit(
            "FIRESTORE_EMULATOR_HOST is not set. Start the Firestore "
            "emulator and export it first, see docs/revops-agent.md."
        )

    from google.cloud import firestore

    accounts = json.loads((_SEED_DIR / "accounts.json").read_text(encoding="utf-8"))
    deals = json.loads((_SEED_DIR / "deals.json").read_text(encoding="utf-8"))

    now = datetime.now(timezone.utc)
    client = firestore.Client(project=project_id())

    batch = client.batch()
    for account in accounts:
        ref = client.collection(ACCOUNTS_COLLECTION).document(account["account_id"])
        batch.set(ref, account)
    for deal in deals:
        prepared = _prepare_deal(dict(deal), now)
        ref = client.collection(DEALS_COLLECTION).document(prepared["deal_id"])
        batch.set(ref, prepared)
    batch.commit()

    print(f"Seeded {len(accounts)} accounts and {len(deals)} deals into project {project_id()}")


if __name__ == "__main__":
    main()
