"""Resolves each researched signal to the contacts it should reach."""

from __future__ import annotations

import json
from pathlib import Path

from google.adk.tools import ToolContext

_DATA_DIR = Path(__file__).resolve().parent.parent / "data"
_CONTACTS_PATH = _DATA_DIR / "fixtures" / "contacts.json"
_SIGNAL_CATEGORY_MAP_PATH = _DATA_DIR / "signal_category_map.json"


def _load_contacts_by_account() -> dict[str, list[dict]]:
    contacts = json.loads(_CONTACTS_PATH.read_text(encoding="utf-8"))
    by_account: dict[str, list[dict]] = {}
    for contact in contacts:
        by_account.setdefault(contact["account_id"], []).append(contact)
    return by_account


def _load_signal_category_map() -> dict[str, list[str]]:
    return json.loads(_SIGNAL_CATEGORY_MAP_PATH.read_text(encoding="utf-8"))


async def map_buyers(tool_context: ToolContext) -> dict:
    """Adds target_contacts to each researched signal, filtered by persona.

    Sets skip_summarization on every path, matching every other tool-only
    step in this pipeline: the LLM is forced to call this tool (see
    agent.py), and without skip_summarization that would also force a
    second, pointless tool-call attempt on the follow-up summarization turn.

    Always sets state["mapped_signals"] before returning, including on the
    error path (to "[]"): the draft step's instruction interpolates
    {mapped_signals} unconditionally, and a missing state key there raises a
    KeyError deep in ADK's instruction templating instead of a readable
    error, so this step must never leave that key unset.

    Returns:
        A dict with "mapped_count", or "error" if state["researched_signals"]
        is missing (account research must run first).
    """
    tool_context.actions.skip_summarization = True

    researched_signals = tool_context.state.get("researched_signals")
    if not researched_signals:
        tool_context.state["mapped_signals"] = "[]"
        return {"error": "No researched signals in state. Run account research first."}

    signals = json.loads(researched_signals)
    contacts_by_account = _load_contacts_by_account()
    signal_category_map = _load_signal_category_map()

    mapped = []
    for signal in signals:
        target_personas = signal_category_map.get(signal["signal_type"], [])
        account_contacts = contacts_by_account.get(signal["account_id"], [])
        targets = [c for c in account_contacts if c["persona"] in target_personas]
        mapped.append({**signal, "target_contacts": targets})

    tool_context.state["mapped_signals"] = json.dumps(mapped, indent=2)
    return {"mapped_count": len(mapped)}
