"""Chunking for the RAG pipeline.

Splits each loaded document's text into overlapping chunks so retrieval can return
focused fragments instead of whole files. Every chunk carries ``source`` (the
originating filename) and ``chunk_index`` (its position within that file) metadata,
which the retriever surfaces for citations.
"""

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

CHUNK_SIZE = 1000
CHUNK_OVERLAP = 200


def chunk_documents(
    documents: list[dict],
    chunk_size: int = CHUNK_SIZE,
    chunk_overlap: int = CHUNK_OVERLAP,
) -> list[Document]:
    """Split loaded documents into overlapping chunks with source metadata.

    Parameters
    ----------
    documents:
        List of ``{"text": str, "source": str}`` dicts, as returned by
        ``rag.loader.load_documents``.

    Returns a list of LangChain ``Document`` objects, each with ``source`` and
    ``chunk_index`` in its metadata. Returns an empty list when *documents* is empty.
    """
    if not documents:
        return []

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
    )

    chunks: list[Document] = []
    for document in documents:
        source = document["source"]
        text_chunks = splitter.split_text(document["text"])
        for chunk_index, text_chunk in enumerate(text_chunks):
            chunks.append(
                Document(
                    page_content=text_chunk,
                    metadata={"source": source, "chunk_index": chunk_index},
                )
            )

    return chunks
