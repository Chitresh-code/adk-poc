"""Shared chromadb corpus search, embedded/on-disk, no server.

Embeddings come from Gemini (model configurable via GOOGLE_EMBEDDING_MODEL,
see .env.example). Needs GOOGLE_API_KEY even when MODEL_PROVIDER=openai:
retrieval doesn't switch providers, see docs/plan.md.

One collection per agent (own chroma dir, own collection name, own corpus
dir), so agents don't share an index; the embedding/query logic underneath
is what's shared.
"""

from __future__ import annotations

import os
from pathlib import Path

import chromadb
from chromadb.utils.embedding_functions import GoogleGeminiEmbeddingFunction

_DEFAULT_EMBEDDING_MODEL = "gemini-embedding-001"


def _embedding_function() -> GoogleGeminiEmbeddingFunction:
    model_name = os.environ.get("GOOGLE_EMBEDDING_MODEL", _DEFAULT_EMBEDDING_MODEL)
    return GoogleGeminiEmbeddingFunction(
        model_name=model_name, api_key_env_var="GOOGLE_API_KEY"
    )


def get_corpus_collection(
    chroma_dir: Path, collection_name: str, corpus_dir: Path
) -> chromadb.Collection:
    """Returns collection_name from chroma_dir, seeding it from corpus_dir if empty.

    Reseeding is keyed on corpus file count vs. collection count: cheap,
    avoids re-embedding on every process start, and self-heals if a file was
    added since the last run.
    """
    client = chromadb.PersistentClient(path=str(chroma_dir))
    collection = client.get_or_create_collection(
        name=collection_name, embedding_function=_embedding_function()
    )

    corpus_files = sorted(corpus_dir.rglob("*.md"))
    if not corpus_files:
        raise RuntimeError(f"No corpus files found under {corpus_dir}.")

    if collection.count() == len(corpus_files):
        return collection

    ids = [str(f.relative_to(corpus_dir)) for f in corpus_files]
    documents = [f.read_text(encoding="utf-8") for f in corpus_files]
    metadatas = [{"source": ids[i]} for i in range(len(corpus_files))]
    collection.upsert(ids=ids, documents=documents, metadatas=metadatas)
    return collection


def search_corpus(collection: chromadb.Collection, query: str, k: int = 3) -> list[dict]:
    """Returns the top-k corpus snippets most relevant to query.

    Each result has "source" (the corpus filename, for traceability) and
    "text" (the matched document).
    """
    results = collection.query(query_texts=[query], n_results=k)
    documents = results["documents"][0] if results["documents"] else []
    metadatas = results["metadatas"][0] if results["metadatas"] else []
    return [
        {"source": meta.get("source", "unknown"), "text": doc}
        for doc, meta in zip(documents, metadatas)
    ]
