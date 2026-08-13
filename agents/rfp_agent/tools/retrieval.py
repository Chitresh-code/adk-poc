"""Local semantic search over the RFP answer corpus.

chromadb PersistentClient, embedded/on-disk, no server. Embeddings come from
Gemini (model configurable via GOOGLE_EMBEDDING_MODEL, see .env.example), so
this needs GOOGLE_API_KEY even when MODEL_PROVIDER=openai (the LLM calls can
go elsewhere; retrieval doesn't switch providers, see docs/plan.md).
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import chromadb
from chromadb.utils.embedding_functions import GoogleGeminiEmbeddingFunction

from google.adk.tools import ToolContext

_DATA_DIR = Path(__file__).resolve().parent.parent / "data"
_CORPUS_DIR = _DATA_DIR / "corpus"
_CHROMA_DIR = _DATA_DIR / "chroma"
_COLLECTION_NAME = "rfp_corpus"
_DEFAULT_EMBEDDING_MODEL = "gemini-embedding-001"


def _embedding_function() -> GoogleGeminiEmbeddingFunction:
    model_name = os.environ.get("GOOGLE_EMBEDDING_MODEL", _DEFAULT_EMBEDDING_MODEL)
    return GoogleGeminiEmbeddingFunction(
        model_name=model_name, api_key_env_var="GOOGLE_API_KEY"
    )


def _get_collection() -> chromadb.Collection:
    """Returns the corpus collection, seeding it from data/corpus/ if empty.

    Reseeding is keyed on corpus file count vs. collection count: cheap,
    avoids re-embedding on every process start, and self-heals if a file was
    added since the last run.
    """
    client = chromadb.PersistentClient(path=str(_CHROMA_DIR))
    collection = client.get_or_create_collection(
        name=_COLLECTION_NAME, embedding_function=_embedding_function()
    )

    corpus_files = sorted(_CORPUS_DIR.rglob("*.md"))
    if not corpus_files:
        raise RuntimeError(f"No corpus files found under {_CORPUS_DIR}.")

    if collection.count() == len(corpus_files):
        return collection

    ids = [str(f.relative_to(_CORPUS_DIR)) for f in corpus_files]
    documents = [f.read_text(encoding="utf-8") for f in corpus_files]
    metadatas = [{"source": ids[i]} for i in range(len(corpus_files))]
    collection.upsert(ids=ids, documents=documents, metadatas=metadatas)
    return collection


def search_corpus(query: str, k: int = 3) -> list[dict]:
    """Returns the top-k corpus snippets most relevant to query.

    Each result has "source" (the corpus filename, so drafts stay
    traceable) and "text" (the matched document).
    """
    collection = _get_collection()
    results = collection.query(query_texts=[query], n_results=k)
    documents = results["documents"][0] if results["documents"] else []
    metadatas = results["metadatas"][0] if results["metadatas"] else []
    return [
        {"source": meta.get("source", "unknown"), "text": doc}
        for doc, meta in zip(documents, metadatas)
    ]


async def retrieve_context(tool_context: ToolContext, k: int = 3) -> dict:
    """Runs search_corpus for every decomposed question and writes results.

    Sets skip_summarization on every path, matching parse_document: the LLM
    is forced to call this tool (see agent.py), and without
    skip_summarization that would also force a second, pointless tool-call
    attempt on the follow-up summarization turn.

    Args:
        tool_context: injected by ADK, gives access to session state.
        k: snippets to retrieve per question.

    Returns:
        A dict with "question_count", or "error" if state["questions"] is
        missing (the decompose step must run first).
    """
    tool_context.actions.skip_summarization = True

    questions = tool_context.state.get("questions")
    if not questions:
        return {"error": "No questions in state. Run decompose first."}

    enriched = []
    for q in questions:
        snippets = search_corpus(q["question"], k=k)
        enriched.append({**q, "snippets": snippets})

    tool_context.state["questions_with_context"] = json.dumps(enriched, indent=2)
    return {"question_count": len(enriched)}
