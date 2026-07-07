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


def _safe_session_path(session_id: str, sessions_dir: Path) -> Path | None:
    """Resolve ``<sessions_dir>/<session_id>.json`` and verify it stays inside
    ``sessions_dir``.

    This module is a shared utility with no guard of its own beyond this — it
    currently relies entirely on the pydantic ``SESSION_ID_PATTERN`` regex at the
    API boundary (see ``api/models.py``) to keep ``session_id`` traversal-safe.
    Mirrors the containment check already used in ``agent/tools.py``'s
    ``read_doc`` (``resolve()`` + ``is_relative_to``) so this module is safe even
    if a future caller reaches it without going through that boundary. Returns
    ``None`` (never raises) on a malformed ``session_id`` or an escape attempt —
    callers treat that the same as "nothing to load" / "refuse to write".
    """
    try:
        sessions_root = sessions_dir.resolve()
        candidate = (sessions_dir / f"{session_id}.json").resolve()
    except (OSError, ValueError) as exc:
        logger.warning("Rejected malformed session_id %r: %s", session_id, exc)
        return None

    if not candidate.is_relative_to(sessions_root):
        logger.warning(
            "Rejected session_id %r — resolved path escapes sessions_dir.",
            session_id,
        )
        return None

    return candidate


def save_session(
    session_id: str,
    messages: list[BaseMessage],
    sessions_dir: Path,
) -> None:
    """Serialise *messages* to ``<sessions_dir>/<session_id>.json``.

    Creates *sessions_dir* (and any parents) if it does not exist. Silently
    refuses to write (logging a warning) if *session_id* would resolve outside
    *sessions_dir*.
    """
    sessions_dir.mkdir(parents=True, exist_ok=True)
    session_file = _safe_session_path(session_id, sessions_dir)
    if session_file is None:
        return

    payload = {
        "session_id": session_id,
        "messages": [_message_to_dict(m) for m in messages],
        "saved_at": datetime.now(timezone.utc).isoformat(),
    }
    session_file.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def load_session(session_id: str, sessions_dir: Path) -> list[BaseMessage]:
    """Load messages from ``<sessions_dir>/<session_id>.json``.

    Returns an empty list when the file does not exist, is corrupt, or
    *session_id* would resolve outside *sessions_dir*.
    """
    session_file = _safe_session_path(session_id, sessions_dir)
    if session_file is None or not session_file.exists():
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
