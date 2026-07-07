"""Shared pytest fixtures for the chatbot-app test suite.

Design constraints (see the task spec):
  * Zero real network calls to any LLM/embeddings/search provider.
  * Never read, mutate, or overwrite the repo's real ``.env`` — all environment
    state is simulated with ``monkeypatch.setenv/delenv``.
  * All on-disk side effects (sessions, agent logs) are redirected into ``tmp_path``.
"""

import time

import jwt
import pytest
from langchain_core.documents import Document
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.runnables import Runnable

# Test-only secrets. These are simulated via monkeypatch.setenv — they never touch
# the real .env file and are not real credentials for any provider. Both must be
# at least 32 chars and differ from each other to satisfy
# api.auth.validate_secret_strength()'s startup guard (SEC-001/SEC-006).
TEST_JWT_SECRET = "test-jwt-secret-do-not-use-in-prod"  # noqa: S105
TEST_API_SECRET = "test-api-secret-value-do-not-use-in-prod"  # noqa: S105
JWT_ALGORITHM = "HS256"

DEFAULT_MOCK_REPLY = "This is a deterministic mock response."


class FakeChatModel(Runnable):
    """Provider-agnostic mock chat model, usable both inside LCEL chains
    (``prompt | llm | parser``) and directly by ``AgentGraph`` (which calls
    ``llm.bind_tools(TOOLS)`` then ``.invoke(messages)``).

    Behaviour is content-driven and fully deterministic — no network of any kind:
      * If the conversation already contains a ``ToolMessage`` (a tool ran or was
        declined), return a plain final answer. This is what stops the agent loop
        after a tool executes.
      * Else, inspect the most recent human message:
          - contains ``"multitool"`` -> emit two tool calls (disclosure test).
          - contains ``"calc"`` or ``"usetool"`` -> emit one calculator tool call.
          - otherwise -> plain final answer.
    """

    def __init__(self, final_text: str = DEFAULT_MOCK_REPLY) -> None:
        self.final_text = final_text
        self.invoke_count = 0

    # --- helpers -----------------------------------------------------------
    @staticmethod
    def _to_messages(model_input):
        if hasattr(model_input, "to_messages"):
            return model_input.to_messages()
        if isinstance(model_input, list):
            return model_input
        if isinstance(model_input, str):
            return [HumanMessage(content=model_input)]
        return []

    @staticmethod
    def _last_human_text(messages) -> str:
        for message in reversed(messages):
            if isinstance(message, HumanMessage):
                content = message.content
                return content if isinstance(content, str) else str(content)
        return ""

    # --- Runnable interface ------------------------------------------------
    def invoke(self, input, config=None, **kwargs):  # noqa: A002 - Runnable API name
        self.invoke_count += 1
        messages = self._to_messages(input)

        if any(isinstance(m, ToolMessage) for m in messages):
            return AIMessage(content=self.final_text)

        lowered = self._last_human_text(messages).lower()

        if "multitool" in lowered:
            return AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "calculator",
                        "args": {"expression": "2 + 2"},
                        "id": "call_multi_1",
                        "type": "tool_call",
                    },
                    {
                        "name": "read_doc",
                        "args": {"filename": "faq.md"},
                        "id": "call_multi_2",
                        "type": "tool_call",
                    },
                ],
            )

        if "calc" in lowered or "usetool" in lowered:
            return AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "calculator",
                        "args": {"expression": "2 + 2"},
                        "id": "call_calc_1",
                        "type": "tool_call",
                    }
                ],
            )

        return AIMessage(content=self.final_text)

    def stream(self, input, config=None, **kwargs):  # noqa: A002 - Runnable API name
        yield self.invoke(input, config=config, **kwargs)

    def bind_tools(self, tools, **kwargs):
        # Returning self keeps the same deterministic behaviour and invoke counter
        # that AgentGraph then drives via .invoke(messages).
        return self


@pytest.fixture
def fake_llm() -> FakeChatModel:
    return FakeChatModel()


@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    """Reset the module-level slowapi limiter's in-memory storage before every
    test. The limiter is a process-global singleton whose counters otherwise bleed
    across tests, which would make both the rate-limit assertions and the
    happy-path endpoints flaky (a happy-path test could inherit an exhausted
    budget and get a spurious 429).
    """
    try:
        from api.rate_limit import limiter

        limiter._storage.reset()
    except Exception:  # noqa: BLE001 - import/reset failures must not break tests
        pass
    yield


@pytest.fixture
def jwt_env(monkeypatch):
    """Simulate a fully configured auth environment without touching .env."""
    monkeypatch.setenv("JWT_SECRET_KEY", TEST_JWT_SECRET)
    monkeypatch.setenv("API_SECRET", TEST_API_SECRET)
    return {"jwt_secret": TEST_JWT_SECRET, "api_secret": TEST_API_SECRET}


@pytest.fixture
def auth_token(jwt_env) -> str:
    """A valid, signed JWT matching the test JWT_SECRET_KEY."""
    now = int(time.time())
    payload = {"sub": "api-client", "iat": now, "exp": now + 3600}
    return jwt.encode(payload, jwt_env["jwt_secret"], algorithm=JWT_ALGORITHM)


@pytest.fixture
def auth_headers(auth_token) -> dict:
    return {"Authorization": f"Bearer {auth_token}"}


@pytest.fixture
def api_secret() -> str:
    """The plaintext API secret matching what jwt_env sets as API_SECRET."""
    return TEST_API_SECRET


def _fake_chunks():
    return [
        Document(
            page_content="Refunds are processed within 14 days of the request.",
            metadata={"source": "faq.md"},
        )
    ]


def _build_client(monkeypatch, tmp_path, fake_llm, *, rag_available: bool):
    """Construct a TestClient with the app fully mocked out.

    Patches every seam the FastAPI ``lifespan`` touches at startup so no real LLM,
    embeddings, vector store, or filesystem-in-repo access happens.
    """
    from fastapi.testclient import TestClient

    import api.main as api_main

    monkeypatch.setattr(api_main, "get_llm", lambda *a, **k: fake_llm)

    if rag_available:
        rag_store = object()  # opaque sentinel; retrieve() is patched below
        monkeypatch.setattr(
            api_main, "build_rag_store", lambda *a, **k: (rag_store, "rag ready")
        )
        import rag.retriever as rag_retriever

        monkeypatch.setattr(
            rag_retriever, "retrieve", lambda store, query, k=3: _fake_chunks()
        )
    else:
        monkeypatch.setattr(
            api_main, "build_rag_store", lambda *a, **k: (None, "rag disabled")
        )

    # Redirect all on-disk writes out of the repo tree.
    monkeypatch.setattr(api_main, "SESSIONS_DIR", tmp_path / "sessions")
    import agent.graph as agent_graph

    monkeypatch.setattr(agent_graph, "LOGS_DIR", tmp_path / "logs")

    # TestClient(app) as a context manager triggers the lifespan (which reads the
    # patched get_llm / build_rag_store above).
    with TestClient(api_main.app) as client:
        yield client


@pytest.fixture
def client(monkeypatch, tmp_path, fake_llm, jwt_env):
    """TestClient with RAG available (vector store initialised)."""
    yield from _build_client(monkeypatch, tmp_path, fake_llm, rag_available=True)


@pytest.fixture
def client_no_rag(monkeypatch, tmp_path, fake_llm, jwt_env):
    """TestClient with RAG unavailable (vector store not initialised -> 503)."""
    yield from _build_client(monkeypatch, tmp_path, fake_llm, rag_available=False)
