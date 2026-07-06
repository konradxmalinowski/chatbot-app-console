"""Unit tests for rag/loader.py document loading."""

from rag.loader import load_documents


def test_loads_txt_and_md_files(tmp_path):
    (tmp_path / "a.txt").write_text("plain text content", encoding="utf-8")
    (tmp_path / "b.md").write_text("# Markdown content", encoding="utf-8")

    docs = load_documents(tmp_path)

    sources = {d["source"] for d in docs}
    assert sources == {"a.txt", "b.md"}
    by_source = {d["source"]: d["text"] for d in docs}
    assert by_source["a.txt"] == "plain text content"
    assert by_source["b.md"] == "# Markdown content"


def test_skips_unsupported_extensions_without_crashing(tmp_path):
    (tmp_path / "keep.md").write_text("keep me", encoding="utf-8")
    (tmp_path / "skip.csv").write_text("a,b,c", encoding="utf-8")
    (tmp_path / "skip.py").write_text("print('no')", encoding="utf-8")

    docs = load_documents(tmp_path)

    assert [d["source"] for d in docs] == ["keep.md"]


def test_skips_empty_files(tmp_path):
    (tmp_path / "empty.txt").write_text("   \n  ", encoding="utf-8")
    (tmp_path / "real.txt").write_text("has content", encoding="utf-8")

    docs = load_documents(tmp_path)

    assert [d["source"] for d in docs] == ["real.txt"]


def test_missing_directory_returns_empty_list(tmp_path):
    assert load_documents(tmp_path / "no-such-dir") == []


def test_skips_undecodable_text_file(tmp_path):
    # Invalid UTF-8 bytes -> _read_text_file returns None -> file is skipped,
    # never fatal.
    (tmp_path / "bad.txt").write_bytes(b"\xff\xfe\x00\x01 not utf-8")
    (tmp_path / "good.md").write_text("fine", encoding="utf-8")

    docs = load_documents(tmp_path)

    assert [d["source"] for d in docs] == ["good.md"]


def test_skips_corrupt_pdf(tmp_path):
    # A file with a .pdf extension that is not a valid PDF must be skipped, not
    # crash the loader.
    (tmp_path / "broken.pdf").write_bytes(b"%PDF-1.4 this is not a real pdf")
    (tmp_path / "good.txt").write_text("fine", encoding="utf-8")

    docs = load_documents(tmp_path)

    assert "good.txt" in {d["source"] for d in docs}
    assert "broken.pdf" not in {d["source"] for d in docs}


def test_ignores_subdirectories(tmp_path):
    (tmp_path / "sub").mkdir()
    (tmp_path / "top.md").write_text("top-level", encoding="utf-8")

    docs = load_documents(tmp_path)

    assert [d["source"] for d in docs] == ["top.md"]
