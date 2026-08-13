"""Grounds flagged accounts in retention/expansion playbook material.

Semantic search reuses the same chromadb helper as Agent 1 and Agent 2 (see
common/retrieval.py), pointed at this agent's own playbook corpus.
"""

from __future__ import annotations

import json
from pathlib import Path

from google.adk.tools import ToolContext

from common.retrieval import get_corpus_collection, search_corpus

_DATA_DIR = Path(__file__).resolve().parent.parent / "data"
_CORPUS_DIR = _DATA_DIR / "corpus"
_CHROMA_DIR = _DATA_DIR / "chroma"
_COLLECTION_NAME = "churn_playbook_corpus"


async def research_playbook(tool_context: ToolContext, k: int = 2) -> dict:
    """Attaches playbook snippets to every flagged (note_type set) account.

    Sets skip_summarization on every path, matching every other tool-only
    step in this pipeline: the LLM is forced to call this tool (see
    agent.py), and without skip_summarization that would also force a
    second, pointless tool-call attempt on the follow-up summarization turn.

    Args:
        tool_context: injected by ADK, gives access to session state.
        k: playbook snippets to retrieve per flagged account.

    Always sets state["accounts_with_context"] before returning, including
    on the error path (to "[]"): the draft step's instruction interpolates
    {accounts_with_context} unconditionally, and a missing state key there
    raises a KeyError deep in ADK's instruction templating instead of a
    readable error, so this step must never leave that key unset.

    Returns:
        A dict with "flagged_count", or "error" if state["scored_accounts"]
        is missing (risk scoring must run first).
    """
    tool_context.actions.skip_summarization = True

    scored_raw = tool_context.state.get("scored_accounts")
    if not scored_raw:
        tool_context.state["accounts_with_context"] = "[]"
        return {"error": "No scored accounts in state. Run risk scoring first."}

    scored = json.loads(scored_raw)
    collection = get_corpus_collection(_CHROMA_DIR, _COLLECTION_NAME, _CORPUS_DIR)

    enriched = []
    flagged_count = 0
    for account in scored:
        if account["note_type"] is None:
            enriched.append({**account, "context": []})
            continue
        flagged_count += 1
        query = (
            f"{account['note_type']} for a {account['industry']} account, "
            f"risk {account['risk_tier']}: {'; '.join(account['rationale'])}"
        )
        context = search_corpus(collection, query, k=k)
        enriched.append({**account, "context": context})

    tool_context.state["accounts_with_context"] = json.dumps(enriched, indent=2)
    return {"flagged_count": flagged_count}
