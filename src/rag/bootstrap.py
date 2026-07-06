"""Shared RAG vector-store bootstrap logic.

Used by both the CLI (``main.py``, opt-in via ``--rag``) and the REST API
(``api/main.py``, built once at startup so ``/chat/rag`` can serve immediately).
Deliberately decoupled from any particular UI: it returns a plain status message
instead of printing anything itself, so the CLI can wrap it in ``rich`` markup and
the API can log it, without duplicating the load/chunk/embed/build sequence.
"""

from constants import CHROMA_PERSIST_DIR, DOCS_DIR


def build_rag_store():
    """Build or load the RAG vector store from ``docs/``.

    Returns ``(store, message)``. ``store`` is ``None`` when ``docs/`` has no usable
    content — callers should treat that as "RAG unavailable" rather than an error.
    ``message`` is a plain-English, markup-free description of the outcome for the
    caller to display however it likes.

    Embeddings provider failures (unreachable Ollama, model not pulled, missing
    ``OPENAI_API_KEY``, invalid ``EMBEDDINGS_PROVIDER``) exit the process — see
    ``rag.embeddings.get_embeddings_provider`` — there is no sensible RAG fallback
    for a broken embeddings backend. Callers that must not crash on this (e.g. the
    API, where ``/chat`` should keep working even if RAG can't start) should catch
    ``SystemExit`` around this call.
    """
    from rag.chunker import chunk_documents
    from rag.embeddings import get_embeddings_provider
    from rag.loader import load_documents
    from rag.store import build_or_load

    documents = load_documents(DOCS_DIR)
    if not documents:
        return None, (
            f"no readable documents found in '{DOCS_DIR}/'. Continuing in non-RAG mode."
        )

    chunks = chunk_documents(documents)
    embeddings = get_embeddings_provider()
    store = build_or_load(chunks, embeddings, persist_directory=str(CHROMA_PERSIST_DIR))
    message = (
        f"RAG mode enabled — {len(documents)} document(s), "
        f"{len(chunks)} chunk(s) available for retrieval."
    )
    return store, message
