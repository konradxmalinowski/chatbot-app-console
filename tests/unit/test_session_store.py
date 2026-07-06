"""Unit tests for session_store save/load round-tripping."""

from langchain_core.messages import AIMessage, HumanMessage

from session_store import load_session, save_session


def test_save_load_roundtrip_preserves_role_and_content(tmp_path):
    session_id = "roundtrip"
    messages = [
        HumanMessage(content="Hello, what is your return policy?"),
        AIMessage(content="Returns are accepted within 14 days."),
    ]

    save_session(session_id, messages, tmp_path)
    loaded = load_session(session_id, tmp_path)

    assert len(loaded) == 2
    assert isinstance(loaded[0], HumanMessage)
    assert isinstance(loaded[1], AIMessage)
    assert loaded[0].content == "Hello, what is your return policy?"
    assert loaded[1].content == "Returns are accepted within 14 days."


def test_load_missing_session_returns_empty_list(tmp_path):
    assert load_session("never-saved", tmp_path) == []


def test_load_corrupt_session_returns_empty_list(tmp_path):
    corrupt = tmp_path / "broken.json"
    corrupt.write_text("{ this is not valid json", encoding="utf-8")
    assert load_session("broken", tmp_path) == []


def test_save_creates_missing_directory(tmp_path):
    nested = tmp_path / "does" / "not" / "exist"
    save_session("s1", [HumanMessage(content="hi")], nested)
    assert (nested / "s1.json").exists()
