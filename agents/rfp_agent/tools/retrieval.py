"""Local semantic search over the RFP answer corpus.

Wraps common/retrieval.py's shared chromadb helper with this agent's own
corpus dir, chroma dir, and collection name.
"""

from __future__ import annotations

import json
from pathlib import Path

from google.adk.tools import ToolContext

from common.retrieval import get_corpus_collection
from common.retrieval import search_corpus as _search_corpus

_DATA_DIR = Path(__file__).resolve().parent.parent / "data"
_CORPUS_DIR = _DATA_DIR / "corpus"
_CHROMA_DIR = _DATA_DIR / "chroma"
_COLLECTION_NAME = "rfp_corpus"


def search_corpus(query: str, k: int = 3) -> list[dict]:
    """Returns the top-k corpus snippets most relevant to query.

    Each result has "source" (the corpus filename, so drafts stay
    traceable) and "text" (the matched document).
    """
    collection = get_corpus_collection(_CHROMA_DIR, _COLLECTION_NAME, _CORPUS_DIR)
    return _search_corpus(collection, query, k=k)


async def retrieve_context(tool_context: ToolContext, k: int = 3) -> dict:
    """Runs search_corpus for every decomposed question and writes results.

    Sets skip_summarization on every path, matching parse_document: the LLM
    is forced to call this tool (see agent.py), and without
    skip_summarization that would also force a second, pointless tool-call
    attempt on the follow-up summarization turn.

    Args:
        tool_context: injected by ADK, gives access to session state.
        k: snippets to retrieve per question.

    Always sets state["questions_with_context"] before returning, including
    on the error path (to "[]"): the draft step's instruction interpolates
    {questions_with_context} unconditionally, and a missing state key there
    raises a KeyError deep in ADK's instruction templating instead of a
    readable error, so this step must never leave that key unset.

    Returns:
        A dict with "question_count", or "error" if state["questions"] is
        missing (the decompose step must run first).
    """
    tool_context.actions.skip_summarization = True

    questions = tool_context.state.get("questions")
    if isinstance(questions, dict):
        # decompose's output_schema wraps the list (see schemas.QuestionList);
        # normalize back to a plain list, once, for every step downstream.
        questions = questions.get("items", [])
        tool_context.state["questions"] = questions
    if not questions:
        tool_context.state["questions_with_context"] = "[]"
        return {"error": "No questions in state. Run decompose first."}

    enriched = []
    for q in questions:
        snippets = search_corpus(q["question"], k=k)
        enriched.append({**q, "snippets": snippets})

    tool_context.state["questions_with_context"] = json.dumps(enriched, indent=2)
    return {"question_count": len(enriched)}
