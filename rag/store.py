"""ChromaDB-backed vector store for the RAG pipeline.

Wraps ``langchain_chroma.Chroma`` so callers don't need to know about chromadb
directly. ``build_or_load`` is idempotent across runs: if the persisted collection
already has data, it is loaded as-is; chunks are only embedded and added the first
time (or after the persisted directory is cleared).
"""

import logging
from pathlib import Path

from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings

logger = logging.getLogger(__name__)

DEFAULT_PERSIST_DIRECTORY = "chroma_db/"
COLLECTION_NAME = "rag_documents"


def build_or_load(
    chunks: list[Document],
    embeddings: Embeddings,
    persist_directory: str = DEFAULT_PERSIST_DIRECTORY,
    collection_name: str = COLLECTION_NAME,
) -> Chroma:
    """Return a Chroma vector store, embedding *chunks* only if none are stored yet.

    Parameters
    ----------
    chunks:
        Chunked documents to embed on first run. Ignored if the persisted collection
        already contains data.
    embeddings:
        A LangChain embeddings object, e.g. from ``rag.embeddings.get_embeddings_provider``.
    persist_directory:
        Directory ChromaDB persists its data to. Created automatically if missing.
    """
    Path(persist_directory).mkdir(parents=True, exist_ok=True)

    store = Chroma(
        collection_name=collection_name,
        embedding_function=embeddings,
        persist_directory=persist_directory,
    )

    existing = store.get(limit=1)
    has_data = bool(existing.get("ids"))

    if has_data:
        logger.info(
            "Loaded existing Chroma collection '%s' from %s (skipping re-embedding).",
            collection_name,
            persist_directory,
        )
    elif chunks:
        store.add_documents(chunks)
        logger.info(
            "Embedded and stored %d chunks in Chroma collection '%s' at %s.",
            len(chunks),
            collection_name,
            persist_directory,
        )
    else:
        logger.warning(
            "No existing data in %s and no chunks to embed — store is empty.",
            persist_directory,
        )

    return store
