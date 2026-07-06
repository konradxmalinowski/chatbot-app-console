import argparse
import logging
import os
import sys

from dotenv import load_dotenv
from google.api_core.exceptions import GoogleAPIError, PermissionDenied
from langchain_core.chat_history import InMemoryChatMessageHistory
from langchain_core.runnables import RunnableConfig
from langchain_core.runnables.history import RunnableWithMessageHistory
from rich.console import Console

from chain_builder import build_base_chain, build_llm
from constants import (
    DEFAULT_SESSION_ID,
    MAX_INPUT_LENGTH,
    SESSIONS_DIR,
    SYSTEM_PROMPT,
)
from rag.bootstrap import build_rag_store
from session_store import load_session, save_session

logging.basicConfig(level=logging.ERROR, format="%(levelname)s: %(message)s")

console = Console()

_PLACEHOLDER_MARKERS = [
    "[NAZWA FIRMY",
    "[GŁÓWNY CEL",
    "[EMAIL/LINK",
    "[Temat",
]


def _validate_env() -> tuple[str, str]:
    """Read and validate required environment variables.

    Returns (api_key, env_model). env_model may be an empty string when the
    caller intends to supply a model override.  Exits immediately if GEMINI_API_KEY
    is absent.
    """
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    env_model = os.environ.get("GEMINI_LLM_MODEL", "").strip()

    if not api_key:
        console.print(
            "[red]Missing required env var: GEMINI_API_KEY. "
            "Copy .env.example to .env and fill in your key.[/]"
        )
        sys.exit(1)

    return api_key, env_model


def _check_system_prompt_placeholders() -> None:
    """Warn if SYSTEM_PROMPT still contains unfilled template placeholders."""
    found = [marker for marker in _PLACEHOLDER_MARKERS if marker in SYSTEM_PROMPT]
    if found:
        console.print(
            "[yellow]Warning:[/] SYSTEM_PROMPT contains unfilled placeholders: "
            + ", ".join(found)
            + ". Customize constants.py before deploying."
        )


def _init_rag_store():
    """Build or load the RAG vector store from ``docs/`` (CLI ``--rag`` mode).

    Returns None (with a printed warning) when ``docs/`` has no usable content, so
    the caller can fall back to non-RAG mode instead of crashing. Any embeddings
    provider failure (unreachable Ollama, missing model, missing OPENAI_API_KEY,
    invalid EMBEDDINGS_PROVIDER) exits the process — there is no sensible RAG
    fallback for that case, matching the fail-fast style used elsewhere in this file.

    The actual load/chunk/embed/build sequence lives in ``rag.bootstrap.build_rag_store``,
    shared with the REST API (``api/main.py``); this wrapper just applies the CLI's
    ``rich`` markup around the plain status message it returns.
    """
    store, message = build_rag_store()
    if store is None:
        console.print(f"[yellow]Warning:[/] {message}")
    else:
        console.print(f"[dim]{message}[/]")
    return store


def build_chain(model_override: str | None = None, rag_enabled: bool = False):
    """Build and return (conversation_chain, history_state).

    Parameters
    ----------
    model_override:
        When supplied (e.g. via --model), takes precedence over the
        GEMINI_LLM_MODEL environment variable.
    rag_enabled:
        When True, retrieves top-k chunks from ``docs/`` per turn and injects them
        into the prompt with citation instructions. Falls back to standard
        (non-RAG) behavior if ``docs/`` has no usable content. Default False keeps
        behavior identical to before RAG existed.
    """
    load_dotenv()

    api_key, env_model = _validate_env()
    _check_system_prompt_placeholders()

    llm_model = model_override or env_model
    if not llm_model:
        console.print(
            "[red]No model specified. Set GEMINI_LLM_MODEL in .env "
            "or pass --model <model-name> on the command line.[/]"
        )
        sys.exit(1)

    llm = build_llm(api_key, llm_model)

    rag_store = _init_rag_store() if rag_enabled else None

    base_chain = build_base_chain(llm, rag_store=rag_store)

    history_state: dict[str, InMemoryChatMessageHistory] = {}

    # Restore previous session if one exists
    prior_messages = load_session(DEFAULT_SESSION_ID, SESSIONS_DIR)
    if prior_messages:
        restored = InMemoryChatMessageHistory()
        restored.add_messages(prior_messages)
        history_state[DEFAULT_SESSION_ID] = restored
        console.print(
            f"[dim]Resumed session with {len(prior_messages)} previous messages.[/]"
        )

    def get_session_history(session_id: str) -> InMemoryChatMessageHistory:
        if session_id not in history_state:
            history_state[session_id] = InMemoryChatMessageHistory()
        return history_state[session_id]

    conversation_chain = RunnableWithMessageHistory(
        runnable=base_chain,
        get_session_history=get_session_history,
        input_messages_key="input",
        history_messages_key="chat_history",
    )

    return conversation_chain, history_state


def chat_with_llm(conversation_chain, user_prompt: str) -> str:
    """Send user_prompt to the LLM and return the full response string."""
    config = RunnableConfig({"configurable": {"session_id": DEFAULT_SESSION_ID}})

    try:
        response_parts = []
        for chunk in conversation_chain.stream({"input": user_prompt}, config=config):
            print(chunk, end="", flush=True)
            response_parts.append(chunk)
        print()  # trailing newline after stream
        return "".join(response_parts)
    except PermissionDenied:
        logging.error("API key invalid or quota exceeded.")
        console.print("[red]Error:[/] API key invalid or quota exceeded.")
        return ""
    except GoogleAPIError:
        logging.error("Network error — check your connection.")
        console.print("[red]Error:[/] Network error — check your connection.")
        return ""
    except Exception as exc:
        logging.error("Unexpected error: %s", exc)
        console.print(f"[red]Error:[/] Unexpected error: {exc}")
        return ""


def main():
    parser = argparse.ArgumentParser(
        description="chatbot-app — LangChain + Gemini CLI chatbot"
    )
    parser.add_argument(
        "--model",
        metavar="MODEL",
        default=None,
        help="Gemini model name to use (overrides GEMINI_LLM_MODEL env var)",
    )
    parser.add_argument(
        "--rag",
        action="store_true",
        help=(
            "Enable retrieval-augmented generation over documents in docs/. "
            "Falls back to normal mode with a warning if docs/ has no usable content."
        ),
    )
    args = parser.parse_args()

    conversation_chain, history_state = build_chain(
        model_override=args.model, rag_enabled=args.rag
    )

    console.rule("[bold]chatbot-app[/]")

    while True:
        console.print("[bold green]You:[/] ", end="")
        user_prompt = input("")

        if not user_prompt.strip():
            break

        if len(user_prompt) > MAX_INPUT_LENGTH:
            console.print(
                f"[yellow]Warning:[/] input exceeds {MAX_INPUT_LENGTH} characters. "
                "Please shorten your message and try again."
            )
            continue

        console.print("[bold cyan]AI:[/] ", end="")
        chat_with_llm(conversation_chain, user_prompt)

    history = history_state.get(DEFAULT_SESSION_ID)
    if history is not None:
        save_session(DEFAULT_SESSION_ID, history.messages, SESSIONS_DIR)
        console.print("[dim]Session saved.[/]")


if __name__ == "__main__":
    main()
