"""Utilities for persisting and restoring LangChain conversation history as JSON."""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage

logger = logging.getLogger(__name__)


def _message_to_dict(message: BaseMessage) -> dict:
    """Convert a LangChain message to a plain serialisable dict."""
    if isinstance(message, HumanMessage):
        role = "human"
    elif isinstance(message, AIMessage):
        role = "ai"
    else:
        # Fallback: use the class name lowercased so nothing is lost
        role = type(message).__name__.lower()
    return {"role": role, "content": message.content}


def _dict_to_message(data: dict) -> BaseMessage:
    """Convert a plain dict back to the appropriate LangChain message type."""
    role = data.get("role", "")
    content = data.get("content", "")
    if role == "human":
        return HumanMessage(content=content)
    if role == "ai":
        return AIMessage(content=content)
    # Unknown role — treat as AIMessage so the history is not silently dropped
    logger.warning("Unknown message role %r in session file — treating as AI.", role)
    return AIMessage(content=content)


def save_session(
    session_id: str,
    messages: list[BaseMessage],
    sessions_dir: Path,
) -> None:
    """Serialise *messages* to ``<sessions_dir>/<session_id>.json``.

    Creates *sessions_dir* (and any parents) if it does not exist.
    """
    sessions_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "session_id": session_id,
        "messages": [_message_to_dict(m) for m in messages],
        "saved_at": datetime.now(timezone.utc).isoformat(),
    }
    session_file = sessions_dir / f"{session_id}.json"
    session_file.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def load_session(session_id: str, sessions_dir: Path) -> list[BaseMessage]:
    """Load messages from ``<sessions_dir>/<session_id>.json``.

    Returns an empty list when the file does not exist or is corrupt.
    """
    session_file = sessions_dir / f"{session_id}.json"
    if not session_file.exists():
        return []

    try:
        raw = session_file.read_text(encoding="utf-8")
        payload = json.loads(raw)
        return [_dict_to_message(d) for d in payload.get("messages", [])]
    except (json.JSONDecodeError, KeyError, TypeError) as exc:
        logger.warning(
            "Could not load session %r (%s) — starting fresh.", session_id, exc
        )
        return []
