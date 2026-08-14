"""Reads deal and account records from the same Firestore emulator revops_agent uses.

Firestore is this repo's "system of record" starting at Agent 4 (see
docs/plan.md); this agent reads the same revops_accounts/revops_deals
collections revops_agent seeds rather than standing up a second copy of the
same fixture CRM. Collection names and project_id() are imported from
revops_agent.tools.crm instead of redefined here, so the two agents can't
drift apart on what those collections are called.

Read-only: this step never writes. The write happens later, in
tools/packaging.py, once a call has actually been analyzed and matched to a
specific deal.
"""

from __future__ import annotations

import json
import os

from google.adk.tools import ToolContext

from revops_agent.tools.crm import ACCOUNTS_COLLECTION, DEALS_COLLECTION, project_id


async def load_deal_context(tool_context: ToolContext) -> dict:
    """Reads every account and deal and builds the candidate list for matching.

    Sets skip_summarization on every path, matching every other tool-only
    step in this pipeline: the LLM is forced to call this tool (see
    agent.py), and without skip_summarization that would also force a
    second, pointless tool-call attempt on the follow-up summarization turn.

    Always sets state["candidate_deals"] before returning, including on the
    error path (to "[]"): the analyze step's instruction interpolates
    {candidate_deals} unconditionally, and a missing state key there raises
    a KeyError deep in ADK's instruction templating instead of a readable
    error, so this step must never leave that key unset.

    Args:
        tool_context: injected by ADK, gives access to session state.

    Returns:
        A dict with "deal_count", or "error" if the emulator isn't
        configured or hasn't been seeded yet.
    """
    tool_context.actions.skip_summarization = True

    if not os.environ.get("FIRESTORE_EMULATOR_HOST"):
        tool_context.state["candidate_deals"] = "[]"
        return {
            "error": (
                "FIRESTORE_EMULATOR_HOST is not set. Start the Firestore "
                "emulator and export it first, see "
                "docs/call-coaching-agent.md."
            )
        }

    from google.cloud import firestore

    client = firestore.Client(project=project_id())
    accounts = [doc.to_dict() for doc in client.collection(ACCOUNTS_COLLECTION).stream()]
    deals = [doc.to_dict() for doc in client.collection(DEALS_COLLECTION).stream()]

    if not accounts or not deals:
        tool_context.state["candidate_deals"] = "[]"
        return {
            "error": (
                "No CRM records found. Run "
                "revops_agent/scripts/seed_firestore.py first, it loads the "
                "fixture accounts and deals into the emulator this agent "
                "also reads from."
            )
        }

    accounts_by_id = {a["account_id"]: a for a in accounts}
    candidate_deals = [
        {
            "deal_id": deal["deal_id"],
            "account_id": deal["account_id"],
            "account_name": accounts_by_id.get(deal["account_id"], {}).get("name"),
            "deal_name": deal["name"],
            "stage": deal["stage"],
            "amount": deal.get("amount"),
        }
        for deal in deals
    ]

    tool_context.state["candidate_deals"] = json.dumps(candidate_deals)
    return {"deal_count": len(candidate_deals)}
