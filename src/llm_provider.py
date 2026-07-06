"""Chat model provider selection for the CLI (``main.py``) and REST API
(``api/main.py``).

Reads ``LLM_PROVIDER`` from the environment (default: ``gemini``, preserving this
project's original behavior for anyone who doesn't set the var) and returns a
ready-to-use LangChain chat model. Every failure mode here is fatal at startup —
there is no sensible way to run the chatbot without a working chat model backend —
and errors are printed in the same ``console.print("[red]...[/]")`` +
``sys.exit(1)`` style ``rag/embeddings.py`` already uses for
``EMBEDDINGS_PROVIDER``.

This is a separate, parallel concern from ``rag/embeddings.py``'s
``EMBEDDINGS_PROVIDER`` (which selects the RAG embeddings backend) — the two are
structurally similar but not related, and are not to be merged.
"""

import os
import sys

from rich.console import Console

console = Console()

DEFAULT_LLM_PROVIDER = "gemini"
VALID_LLM_PROVIDERS = ("gemini", "openai", "anthropic", "ollama")

# Provider-specific default chat model names, used when --model/model_override is
# not supplied. Gemini deliberately has no hardcoded default here — it must come
# from --model or the GEMINI_LLM_MODEL env var, preserving exact pre-existing
# behavior.
OPENAI_DEFAULT_MODEL = "gpt-4o-mini"
ANTHROPIC_DEFAULT_MODEL = "claude-3-5-haiku-latest"
OLLAMA_DEFAULT_MODEL = "llama3.2:3b"


def _fail(message: str) -> None:
    console.print(f"[red]{message}[/]")
    sys.exit(1)


def _get_gemini_llm(model_override: str | None):
    """Build a ChatGoogleGenerativeAI instance, failing fast if GEMINI_API_KEY is
    unset or no model name is available from either --model or GEMINI_LLM_MODEL.
    """
    from langchain_google_genai import ChatGoogleGenerativeAI

    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        _fail(
            "Missing required env var: GEMINI_API_KEY. "
            "Copy .env.example to .env and fill in your key."
        )
        return None

    model = model_override or os.environ.get("GEMINI_LLM_MODEL", "").strip()
    if not model:
        _fail(
            "No model specified. Set GEMINI_LLM_MODEL in .env "
            "or pass --model <model-name> on the command line."
        )
        return None

    return ChatGoogleGenerativeAI(model=model, google_api_key=api_key)


def _get_openai_llm(model_override: str | None):
    """Build a ChatOpenAI instance, failing fast if OPENAI_API_KEY is unset.

    Reuses OPENAI_API_KEY, the same env var already used for RAG embeddings
    (rag/embeddings.py's EMBEDDINGS_PROVIDER=openai) — not a new key.
    """
    from langchain_openai import ChatOpenAI

    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not api_key:
        _fail(
            "Missing required env var: OPENAI_API_KEY (needed because "
            "LLM_PROVIDER=openai). Add it to your .env file."
        )
        return None

    model = model_override or OPENAI_DEFAULT_MODEL
    return ChatOpenAI(model=model, api_key=api_key)


def _get_anthropic_llm(model_override: str | None):
    """Build a ChatAnthropic instance, failing fast if ANTHROPIC_API_KEY is unset."""
    from langchain_anthropic import ChatAnthropic

    api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not api_key:
        _fail(
            "Missing required env var: ANTHROPIC_API_KEY (needed because "
            "LLM_PROVIDER=anthropic). Add it to your .env file."
        )
        return None

    model = model_override or ANTHROPIC_DEFAULT_MODEL
    return ChatAnthropic(model=model, api_key=api_key)


def _get_ollama_llm(model_override: str | None):
    """Build a ChatOllama instance, failing fast if Ollama or the model aren't
    available locally. Mirrors rag/embeddings.py's _get_ollama_embeddings() exactly.
    """
    import ollama
    from langchain_ollama import ChatOllama

    model = model_override or OLLAMA_DEFAULT_MODEL

    try:
        available_models = {m.model for m in ollama.Client().list().models}
    except ConnectionError:
        _fail(
            "Could not reach Ollama. Make sure it is installed and running "
            "(https://ollama.com/download), then try again."
        )
        return None

    model_pulled = any(
        name == model or name.startswith(f"{model}:") for name in available_models
    )
    if not model_pulled:
        _fail(f"Model '{model}' is not pulled in Ollama. Fix: ollama pull {model}")
        return None

    return ChatOllama(model=model)


def get_llm(model_override: str | None = None):
    """Return a ready LangChain chat model per the LLM_PROVIDER env var.

    Parameters
    ----------
    model_override:
        When supplied (e.g. via --model), takes precedence over the provider's
        default/env-configured model name.

    Exits the process with a clear, actionable message if the selected provider
    isn't usable (missing API key, unreachable/unpulled Ollama model, or an
    unrecognized provider name).
    """
    provider = os.environ.get("LLM_PROVIDER", "").strip().lower()
    if not provider:
        provider = DEFAULT_LLM_PROVIDER

    if provider == "gemini":
        return _get_gemini_llm(model_override)
    if provider == "openai":
        return _get_openai_llm(model_override)
    if provider == "anthropic":
        return _get_anthropic_llm(model_override)
    if provider == "ollama":
        return _get_ollama_llm(model_override)

    _fail(
        f"Invalid LLM_PROVIDER: '{provider}'. Valid options: "
        + ", ".join(VALID_LLM_PROVIDERS)
    )
    return None
