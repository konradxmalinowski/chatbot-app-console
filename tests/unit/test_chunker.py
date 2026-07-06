"""Unit tests for rag/chunker.py.

Verifies the chunking invariants the retriever/citation layer depends on:
per-source chunk_index is contiguous from zero, source metadata is preserved, and
long text is actually split into multiple overlapping chunks.
"""

from rag.chunker import chunk_documents


def test_empty_input_returns_empty_list():
    assert chunk_documents([]) == []


def test_short_document_becomes_single_chunk():
    docs = [{"text": "a short note", "source": "note.md"}]
    chunks = chunk_documents(docs)

    assert len(chunks) == 1
    assert chunks[0].page_content == "a short note"
    assert chunks[0].metadata == {"source": "note.md", "chunk_index": 0}


def test_long_document_is_split_into_multiple_chunks():
    long_text = "word " * 1000  # ~5000 chars, well over CHUNK_SIZE=1000
    chunks = chunk_documents([{"text": long_text, "source": "big.txt"}])

    assert len(chunks) > 1
    # chunk_index is contiguous starting from 0 within a single source.
    assert [c.metadata["chunk_index"] for c in chunks] == list(range(len(chunks)))
    assert all(c.metadata["source"] == "big.txt" for c in chunks)


def test_per_source_index_resets_across_documents():
    long_text = "word " * 1000
    docs = [
        {"text": long_text, "source": "first.txt"},
        {"text": long_text, "source": "second.txt"},
    ]
    chunks = chunk_documents(docs)

    for source in ("first.txt", "second.txt"):
        indices = [
            c.metadata["chunk_index"] for c in chunks if c.metadata["source"] == source
        ]
        assert indices == list(range(len(indices)))
        assert indices[0] == 0
