"""Reads CRM records (accounts, deals) from the local Firestore emulator.

google-cloud-firestore connects to FIRESTORE_EMULATOR_HOST automatically (no
credentials needed) whenever that env var is set. Nothing seeds the emulator
on its own: run scripts/seed_firestore.py first, which loads
data/seed/accounts.json and deals.json into it. See docs/revops-agent.md.

Read-only: this tool and every step downstream of it only ever read from
Firestore, never write back to it. See docs/revops-agent.md for why.
"""

from __future__ import annotations

import json
import os

from google.adk.tools import ToolContext

ACCOUNTS_COLLECTION = "revops_accounts"
DEALS_COLLECTION = "revops_deals"
_DEFAULT_PROJECT_ID = "adk-poc-local"


def project_id() -> str:
    return os.environ.get("FIRESTORE_PROJECT_ID") or os.environ.get(
        "GOOGLE_CLOUD_PROJECT", _DEFAULT_PROJECT_ID
    )


async def load_crm_records(tool_context: ToolContext) -> dict:
    """Reads accounts and deals from Firestore and joins deals to their account.

    Sets skip_summarization on every path, matching every other tool-only
    step in this pipeline: the LLM is forced to call this tool (see
    agent.py), and without skip_summarization that would also force a
    second, pointless tool-call attempt on the follow-up summarization turn.

    Args:
        tool_context: injected by ADK, gives access to session state.

    Returns:
        A dict with "account_count" and "deal_count", or "error" if the
        emulator isn't configured or hasn't been seeded yet.
    """
    tool_context.actions.skip_summarization = True

    if not os.environ.get("FIRESTORE_EMULATOR_HOST"):
        tool_context.state["accounts"] = "[]"
        tool_context.state["deals"] = "[]"
        return {
            "error": (
                "FIRESTORE_EMULATOR_HOST is not set. Start the Firestore "
                "emulator and export it first, see "
                "docs/revops-agent.md."
            )
        }

    from google.cloud import firestore

    client = firestore.Client(project=project_id())
    accounts = [doc.to_dict() for doc in client.collection(ACCOUNTS_COLLECTION).stream()]
    deals = [doc.to_dict() for doc in client.collection(DEALS_COLLECTION).stream()]

    if not accounts or not deals:
        tool_context.state["accounts"] = "[]"
        tool_context.state["deals"] = "[]"
        return {
            "error": (
                "No CRM records found. Run scripts/seed_firestore.py first, "
                "it loads the fixture accounts and deals into the emulator."
            )
        }

    accounts_by_id = {a["account_id"]: a for a in accounts}
    joined_deals = []
    for deal in deals:
        account = accounts_by_id.get(deal["account_id"], {})
        joined_deals.append(
            {
                **deal,
                "account_name": account.get("name"),
                "industry": account.get("industry"),
                "segment": account.get("segment"),
            }
        )

    tool_context.state["accounts"] = json.dumps(accounts)
    tool_context.state["deals"] = json.dumps(joined_deals)
    return {"account_count": len(accounts), "deal_count": len(joined_deals)}
