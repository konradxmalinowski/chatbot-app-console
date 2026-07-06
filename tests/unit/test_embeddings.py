"""Unit tests for rag/embeddings.py provider dispatch and fail-fast paths.

Mirrors test_llm_provider.py: every backend is mocked, no real Ollama/OpenAI call,
and env state is simulated with monkeypatch only (never touching .env).
"""

import types

import ollama
import pytest

from rag import embeddings


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    for key in ("EMBEDDINGS_PROVIDER", "OPENAI_API_KEY"):
        monkeypatch.delenv(key, raising=False)


class _Recording:
    def __init__(self, **kwargs):
        self.kwargs = kwargs


class TestDispatch:
    def test_ollama_is_default_when_model_pulled(self, monkeypatch):
        import langchain_ollama

        monkeypatch.setattr(langchain_ollama, "OllamaEmbeddings", _Recording)
        listed = types.SimpleNamespace(
            models=[types.SimpleNamespace(model=embeddings.OLLAMA_EMBEDDING_MODEL)]
        )
        monkeypatch.setattr(
            ollama, "Client", lambda: types.SimpleNamespace(list=lambda: listed)
        )

        assert isinstance(embeddings.get_embeddings_provider(), _Recording)

    def test_openai_provider(self, monkeypatch):
        import langchain_openai

        monkeypatch.setenv("EMBEDDINGS_PROVIDER", "openai")
        monkeypatch.setenv("OPENAI_API_KEY", "fake-key")
        monkeypatch.setattr(langchain_openai, "OpenAIEmbeddings", _Recording)

        model = embeddings.get_embeddings_provider()
        assert isinstance(model, _Recording)
        assert model.kwargs["model"] == embeddings.OPENAI_EMBEDDING_MODEL


class TestFailFast:
    def test_openai_missing_key_exits(self, monkeypatch):
        monkeypatch.setenv("EMBEDDINGS_PROVIDER", "openai")
        with pytest.raises(SystemExit):
            embeddings.get_embeddings_provider()

    def test_ollama_unreachable_exits(self, monkeypatch):
        def _raise():
            raise ConnectionError("down")

        monkeypatch.setattr(
            ollama, "Client", lambda: types.SimpleNamespace(list=_raise)
        )
        with pytest.raises(SystemExit):
            embeddings.get_embeddings_provider()

    def test_ollama_model_not_pulled_exits(self, monkeypatch):
        listed = types.SimpleNamespace(
            models=[types.SimpleNamespace(model="something-else")]
        )
        monkeypatch.setattr(
            ollama, "Client", lambda: types.SimpleNamespace(list=lambda: listed)
        )
        with pytest.raises(SystemExit):
            embeddings.get_embeddings_provider()

    def test_invalid_provider_exits(self, monkeypatch):
        monkeypatch.setenv("EMBEDDINGS_PROVIDER", "pinecone")
        with pytest.raises(SystemExit):
            embeddings.get_embeddings_provider()
