"""Retrieval for the RAG pipeline.

Thin wrapper around a Chroma vector store's similarity search, returning chunks
alongside their ``source`` / ``chunk_index`` metadata so callers can build citations.
"""

from langchain_chroma import Chroma
from langchain_core.documents import Document

DEFAULT_TOP_K = 3


def retrieve(store: Chroma, query: str, k: int = DEFAULT_TOP_K) -> list[Document]:
    """Return the *k* most relevant chunks to *query* from *store*.

    Each returned ``Document`` carries ``source`` and ``chunk_index`` in its
    metadata. Returns an empty list if the store has no data yet.
    """
    return store.similarity_search(query, k=k)
