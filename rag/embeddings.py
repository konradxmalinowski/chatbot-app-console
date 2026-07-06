"""Embeddings provider selection for the RAG pipeline.

Reads ``EMBEDDINGS_PROVIDER`` from the environment (default: ``ollama``, which needs
no cloud API key) and returns a ready-to-use LangChain embeddings object. Every
failure mode here is fatal at startup — there is no sensible way to run RAG without
a working embeddings backend — and errors are printed in the same
``console.print("[red]...[/]")`` + ``sys.exit(1)`` style ``main.py`` already uses for
``GEMINI_API_KEY``.
"""

import os
import sys

from rich.console import Console

console = Console()

DEFAULT_EMBEDDINGS_PROVIDER = "ollama"
OLLAMA_EMBEDDING_MODEL = "nomic-embed-text"
OPENAI_EMBEDDING_MODEL = "text-embedding-3-small"
VALID_PROVIDERS = ("ollama", "openai")


def _fail(message: str) -> None:
    console.print(f"[red]{message}[/]")
    sys.exit(1)


def _get_ollama_embeddings():
    """Build an OllamaEmbeddings instance, failing fast if Ollama or the model
    aren't available locally.
    """
    import ollama
    from langchain_ollama import OllamaEmbeddings

    try:
        available_models = {model.model for model in ollama.Client().list().models}
    except ConnectionError:
        _fail(
            "Could not reach Ollama. Make sure it is installed and running "
            "(https://ollama.com/download), then try again."
        )
        return None

    model_pulled = any(
        name == OLLAMA_EMBEDDING_MODEL or name.startswith(f"{OLLAMA_EMBEDDING_MODEL}:")
        for name in available_models
    )
    if not model_pulled:
        _fail(
            f"Embedding model '{OLLAMA_EMBEDDING_MODEL}' is not pulled in Ollama. "
            f"Fix: ollama pull {OLLAMA_EMBEDDING_MODEL}"
        )
        return None

    return OllamaEmbeddings(model=OLLAMA_EMBEDDING_MODEL)


def _get_openai_embeddings():
    """Build an OpenAIEmbeddings instance, failing fast if OPENAI_API_KEY is unset."""
    from langchain_openai import OpenAIEmbeddings

    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not api_key:
        _fail(
            "Missing required env var: OPENAI_API_KEY (needed because "
            "EMBEDDINGS_PROVIDER=openai). Add it to your .env file."
        )
        return None

    return OpenAIEmbeddings(model=OPENAI_EMBEDDING_MODEL, api_key=api_key)


def get_embeddings_provider():
    """Return a LangChain embeddings object per the ``EMBEDDINGS_PROVIDER`` env var.

    Exits the process with a clear, actionable message if the selected provider
    isn't usable (unreachable Ollama / model not pulled, missing OPENAI_API_KEY, or
    an unrecognized provider name).
    """
    provider = os.environ.get("EMBEDDINGS_PROVIDER", "").strip().lower()
    if not provider:
        provider = DEFAULT_EMBEDDINGS_PROVIDER

    if provider == "ollama":
        return _get_ollama_embeddings()
    if provider == "openai":
        return _get_openai_embeddings()

    _fail(
        f"Invalid EMBEDDINGS_PROVIDER: '{provider}'. Valid options: "
        + ", ".join(VALID_PROVIDERS)
    )
    return None
