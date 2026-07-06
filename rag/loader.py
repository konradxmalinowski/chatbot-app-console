"""Document loading for the RAG pipeline.

Walks a directory, dispatches each file to the reader matching its extension, and
returns the extracted text alongside its source filename. Unsupported extensions and
unreadable files are skipped (logged), never fatal — the caller decides what to do
with an empty result (e.g. fall back to non-RAG mode).
"""

from pathlib import Path

from pypdf import PdfReader
from pypdf.errors import PdfReadError
from rich.console import Console

console = Console()

SUPPORTED_EXTENSIONS = {".pdf", ".txt", ".md"}


def _read_pdf(path: Path) -> str | None:
    """Extract text from a PDF file. Returns None if the file can't be parsed.

    Catches broadly (not just the expected pypdf/IO exceptions) because a malformed
    or adversarial PDF can trigger failure modes pypdf doesn't wrap consistently
    (e.g. decompression bombs, deeply nested objects) — one bad file must never
    crash the whole CLI at startup; it should just be skipped, per this loader's
    documented behavior.
    """
    try:
        reader = PdfReader(str(path))
        pages_text = [page.extract_text() or "" for page in reader.pages]
        return "\n".join(pages_text)
    except (PdfReadError, OSError, ValueError) as exc:
        console.print(f"[yellow]Warning:[/] skipping unreadable PDF {path.name}: {exc}")
        return None
    except Exception as exc:  # noqa: BLE001 — see docstring: must never crash the loader
        console.print(
            f"[yellow]Warning:[/] skipping unparseable PDF {path.name}: {exc}"
        )
        return None


def _read_text_file(path: Path) -> str | None:
    """Read a plain-text or Markdown file. Returns None if it can't be decoded."""
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        console.print(
            f"[yellow]Warning:[/] skipping unreadable file {path.name}: {exc}"
        )
        return None


_READERS = {
    ".pdf": _read_pdf,
    ".txt": _read_text_file,
    ".md": _read_text_file,
}


def load_documents(docs_dir: Path) -> list[dict]:
    """Load every supported document under *docs_dir*.

    Returns a list of ``{"text": str, "source": str}`` dicts, one per successfully
    read file. Missing or empty directories, unsupported extensions, and unreadable
    files are not errors — they simply contribute nothing to the result, with a
    logged warning for anything that was skipped.
    """
    if not docs_dir.exists() or not docs_dir.is_dir():
        console.print(
            f"[yellow]Warning:[/] docs directory {docs_dir} does not exist — no RAG content."
        )
        return []

    documents: list[dict] = []
    for path in sorted(docs_dir.iterdir()):
        if not path.is_file():
            continue

        extension = path.suffix.lower()
        reader = _READERS.get(extension)
        if reader is None:
            console.print(
                f"[yellow]Warning:[/] skipping unsupported file extension "
                f"'{extension}' for {path.name}"
            )
            continue

        text = reader(path)
        if text is None:
            continue

        if not text.strip():
            console.print(f"[yellow]Warning:[/] skipping empty document: {path.name}")
            continue

        documents.append({"text": text, "source": path.name})

    return documents
