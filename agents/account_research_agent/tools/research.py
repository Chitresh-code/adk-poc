"""Enriches pulled signals with fixture account data and matching proof points.

Semantic search reuses the same chromadb helper as Agent 1's corpus search
(see common/retrieval.py), pointed at this agent's own case-study corpus.
"""

from __future__ import annotations

import json
from pathlib import Path

from google.adk.tools import ToolContext

from common.retrieval import get_corpus_collection, search_corpus

_DATA_DIR = Path(__file__).resolve().parent.parent / "data"
_ACCOUNTS_PATH = _DATA_DIR / "fixtures" / "accounts.json"
_CORPUS_DIR = _DATA_DIR / "corpus"
_CHROMA_DIR = _DATA_DIR / "chroma"
_COLLECTION_NAME = "account_research_corpus"


def _load_accounts() -> dict[str, dict]:
    accounts = json.loads(_ACCOUNTS_PATH.read_text(encoding="utf-8"))
    return {a["account_id"]: a for a in accounts}


async def research_account(tool_context: ToolContext, k: int = 2) -> dict:
    """Enriches each pulled signal with its account record and proof points.

    Sets skip_summarization on every path, matching every other tool-only
    step in this pipeline: the LLM is forced to call this tool (see
    agent.py), and without skip_summarization that would also force a
    second, pointless tool-call attempt on the follow-up summarization turn.

    Args:
        tool_context: injected by ADK, gives access to session state.
        k: proof-point snippets to retrieve per signal.

    Returns:
        A dict with "researched_count", or "error" if state["signals"] is
        missing (signal intake must run first).
    """
    tool_context.actions.skip_summarization = True

    signals = tool_context.state.get("signals")
    if not signals:
        return {"error": "No signals in state. Run signal intake first."}

    accounts = _load_accounts()
    collection = get_corpus_collection(_CHROMA_DIR, _COLLECTION_NAME, _CORPUS_DIR)

    enriched = []
    for signal in signals:
        account = accounts.get(signal["account_id"])
        if account is None:
            enriched.append({**signal, "account": None, "proof_points": []})
            continue
        query = f"{signal['signal_type']}: {signal['detail']} ({account['industry']})"
        proof_points = search_corpus(collection, query, k=k)
        enriched.append({**signal, "account": account, "proof_points": proof_points})

    tool_context.state["researched_signals"] = json.dumps(enriched, indent=2)
    return {"researched_count": len(enriched)}
