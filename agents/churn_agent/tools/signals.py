"""Loads and joins fixture usage, ticket, and sentiment data per account."""

from __future__ import annotations

import json
from pathlib import Path

from google.adk.tools import ToolContext

_DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "fixtures"
_ACCOUNTS_PATH = _DATA_DIR / "accounts.json"
_USAGE_PATH = _DATA_DIR / "usage.json"
_TICKETS_PATH = _DATA_DIR / "tickets.json"
_SENTIMENT_PATH = _DATA_DIR / "sentiment.json"


def _load(path: Path) -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8"))


async def load_account_signals(tool_context: ToolContext) -> dict:
    """Joins fixture usage, ticket, and sentiment data into one record per account.

    Sets skip_summarization on every path, matching every other tool-only
    step in this pipeline: the LLM is forced to call this tool (see
    agent.py), and without skip_summarization that would also force a
    second, pointless tool-call attempt on the follow-up summarization turn.

    Returns:
        A dict with "account_count".
    """
    tool_context.actions.skip_summarization = True

    accounts = _load(_ACCOUNTS_PATH)
    usage_by_account = {u["account_id"]: u for u in _load(_USAGE_PATH)}
    tickets_by_account: dict[str, list[dict]] = {}
    for ticket in _load(_TICKETS_PATH):
        tickets_by_account.setdefault(ticket["account_id"], []).append(ticket)
    sentiment_by_account = {s["account_id"]: s for s in _load(_SENTIMENT_PATH)}

    joined = []
    for account in accounts:
        account_id = account["account_id"]
        joined.append(
            {
                **account,
                "usage": usage_by_account.get(account_id),
                "tickets": tickets_by_account.get(account_id, []),
                "sentiment": sentiment_by_account.get(account_id),
            }
        )

    tool_context.state["accounts"] = json.dumps(joined, indent=2)
    return {"account_count": len(joined)}
