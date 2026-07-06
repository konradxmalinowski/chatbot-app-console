"""Unit tests for the CLI entry point (main.py).

The interactive loop is driven by mocking ``builtins.input``; the LLM is the
deterministic fake fixture. No real network or real .env credentials are used
(get_llm is patched wherever it would build a real provider client).
"""

import anthropic
import openai
import pytest
from google.api_core.exceptions import GoogleAPIError, PermissionDenied
from langchain_core.chat_history import InMemoryChatMessageHistory
from langchain_core.messages import HumanMessage

import main
from constants import DEFAULT_SESSION_ID, MAX_INPUT_LENGTH

# Each provider-specific exception main.py maps to a graceful degrade path.
PROVIDER_EXCEPTIONS = [
    PermissionDenied("denied"),
    GoogleAPIError("network"),
    openai.OpenAIError("openai down"),
    anthropic.AnthropicError("anthropic down"),
    ConnectionError("ollama down"),
    RuntimeError("unexpected"),
]


@pytest.fixture(autouse=True)
def _isolate_disk_and_logs(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "SESSIONS_DIR", tmp_path / "sessions")
    import agent.graph as agent_graph

    monkeypatch.setattr(agent_graph, "LOGS_DIR", tmp_path / "logs")


def _feed_inputs(monkeypatch, values):
    it = iter(values)
    monkeypatch.setattr("builtins.input", lambda *a, **k: next(it))


class StubChain:
    """Minimal stand-in for the LCEL conversation chain used by chat_with_llm."""

    def __init__(self, chunks=None, exc=None):
        self._chunks = chunks or []
        self._exc = exc

    def stream(self, _inp, config=None):
        if self._exc is not None:
            raise self._exc
        yield from self._chunks


class TestPlaceholders:
    def test_placeholder_warning_does_not_raise(self):
        # SYSTEM_PROMPT ships with intentional unfilled placeholders.
        main._check_system_prompt_placeholders()


class TestBuildChain:
    def test_returns_chain_and_empty_history_fresh(self, monkeypatch, fake_llm):
        monkeypatch.setattr(main, "get_llm", lambda *a, **k: fake_llm)

        chain, history_state = main.build_chain()

        assert chain is not None
        assert history_state == {}

    def test_resumes_prior_session(self, monkeypatch, fake_llm, tmp_path):
        # Pre-seed a session file the builder should restore.
        from session_store import save_session

        save_session(
            DEFAULT_SESSION_ID, [HumanMessage(content="earlier")], main.SESSIONS_DIR
        )
        monkeypatch.setattr(main, "get_llm", lambda *a, **k: fake_llm)

        _chain, history_state = main.build_chain()

        assert DEFAULT_SESSION_ID in history_state

    def test_rag_enabled_falls_back_when_store_empty(self, monkeypatch, fake_llm):
        monkeypatch.setattr(main, "get_llm", lambda *a, **k: fake_llm)
        monkeypatch.setattr(main, "build_rag_store", lambda *a, **k: (None, "no docs"))

        chain, _history = main.build_chain(rag_enabled=True)

        assert chain is not None


class TestChatWithLlm:
    def test_joins_streamed_chunks(self):
        result = main.chat_with_llm(StubChain(chunks=["Hel", "lo"]), "hi")
        assert result == "Hello"

    @pytest.mark.parametrize("exc", PROVIDER_EXCEPTIONS)
    def test_provider_errors_degrade_to_empty(self, exc):
        # Every mapped provider failure must be caught and turned into "" rather
        # than propagating a raw traceback to the user.
        assert main.chat_with_llm(StubChain(exc=exc), "hi") == ""


class TestBuildAgentGraph:
    def test_builds_agent_graph(self, monkeypatch, fake_llm):
        monkeypatch.setattr(main, "get_llm", lambda *a, **k: fake_llm)
        from agent.graph import AgentGraph

        assert isinstance(main.build_agent_graph(), AgentGraph)


class TestRunAgentTurn:
    def test_approve_runs_tool(self, monkeypatch, fake_llm):
        from agent.graph import AgentGraph

        graph = AgentGraph(fake_llm)
        _feed_inputs(monkeypatch, ["y"])

        main.run_agent_turn(graph, "cli-approve", "please calc 2+2")

        assert graph.has_pending_approval("cli-approve") is False

    def test_reject_skips_tool(self, monkeypatch, fake_llm):
        from agent.graph import AgentGraph

        graph = AgentGraph(fake_llm)
        _feed_inputs(monkeypatch, ["n"])

        main.run_agent_turn(graph, "cli-reject", "please calc 2+2")

        assert graph.has_pending_approval("cli-reject") is False

    @pytest.mark.parametrize("exc", PROVIDER_EXCEPTIONS)
    def test_start_turn_error_degrades_gracefully(self, exc):
        class RaisingGraph:
            def start_turn(self, _s, _m):
                raise exc

        # Must not propagate — the CLI catches every mapped provider error.
        main.run_agent_turn(RaisingGraph(), "err-session", "please calc 2+2")


class TestMain:
    def test_agent_and_rag_are_mutually_exclusive(self, monkeypatch):
        monkeypatch.setattr("sys.argv", ["main.py", "--agent", "--rag"])
        with pytest.raises(SystemExit):
            main.main()

    def test_plain_mode_runs_and_saves(self, monkeypatch, fake_llm):
        monkeypatch.setattr("sys.argv", ["main.py"])
        history = {DEFAULT_SESSION_ID: InMemoryChatMessageHistory()}
        monkeypatch.setattr(
            main, "build_chain", lambda *a, **k: (StubChain(chunks=["ok"]), history)
        )
        saved = {}
        monkeypatch.setattr(
            main,
            "save_session",
            lambda sid, msgs, d: saved.update({"called": True}),
        )
        # One real message, then an empty line to exit the loop.
        _feed_inputs(monkeypatch, ["hello", ""])

        main.main()

        assert saved.get("called") is True

    def test_agent_mode_exits_on_empty_input(self, monkeypatch, fake_llm):
        monkeypatch.setattr("sys.argv", ["main.py", "--agent"])
        monkeypatch.setattr(main, "build_agent_graph", lambda *a, **k: object())
        _feed_inputs(monkeypatch, [""])

        # Empty first input breaks the loop before any turn runs.
        main.main()

    def test_plain_mode_rejects_overlong_input(self, monkeypatch):
        monkeypatch.setattr("sys.argv", ["main.py"])
        monkeypatch.setattr(main, "build_chain", lambda *a, **k: (StubChain(), {}))
        # Over-limit line triggers the warning+continue path, then "" exits.
        _feed_inputs(monkeypatch, ["x" * (MAX_INPUT_LENGTH + 1), ""])

        main.main()

    def test_agent_mode_rejects_overlong_input(self, monkeypatch):
        monkeypatch.setattr("sys.argv", ["main.py", "--agent"])
        monkeypatch.setattr(main, "build_agent_graph", lambda *a, **k: object())
        _feed_inputs(monkeypatch, ["x" * (MAX_INPUT_LENGTH + 1), ""])

        main.main()
