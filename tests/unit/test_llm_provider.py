"""Unit tests for llm_provider.get_llm's 4-provider dispatch and fail-fast paths.

Every provider's underlying SDK/client is mocked, so no real Gemini/OpenAI/
Anthropic/Ollama call is ever made. Missing-key and invalid-provider paths are
exercised via monkeypatch.setenv/delenv only — the real .env is never touched.
"""

import types

import ollama
import pytest

import llm_provider

ALL_PROVIDER_KEYS = (
    "GEMINI_API_KEY",
    "GEMINI_LLM_MODEL",
    "OPENAI_API_KEY",
    "ANTHROPIC_API_KEY",
    "LLM_PROVIDER",
)


@pytest.fixture(autouse=True)
def _clean_provider_env(monkeypatch):
    """Start each test from a known-empty provider environment so results do not
    depend on whatever the ambient shell / loaded .env happens to contain.
    """
    for key in ALL_PROVIDER_KEYS:
        monkeypatch.delenv(key, raising=False)


class _RecordingModel:
    """Stand-in for a LangChain chat model class: records how it was built."""

    def __init__(self, **kwargs):
        self.kwargs = kwargs


def _patch_chat_class(monkeypatch, module_path, attr):
    """Patch ``<module>.<attr>`` (imported lazily inside get_llm) with a recorder."""
    module = __import__(module_path, fromlist=[attr])
    monkeypatch.setattr(module, attr, _RecordingModel)


class TestProviderDispatch:
    def test_gemini_returns_google_model(self, monkeypatch):
        monkeypatch.setenv("LLM_PROVIDER", "gemini")
        monkeypatch.setenv("GEMINI_API_KEY", "fake-key")
        monkeypatch.setenv("GEMINI_LLM_MODEL", "gemini-2.5-flash")
        _patch_chat_class(
            monkeypatch, "langchain_google_genai", "ChatGoogleGenerativeAI"
        )

        model = llm_provider.get_llm()

        assert isinstance(model, _RecordingModel)
        assert model.kwargs["model"] == "gemini-2.5-flash"

    def test_gemini_is_the_default_provider(self, monkeypatch):
        # LLM_PROVIDER unset -> defaults to gemini.
        monkeypatch.setenv("GEMINI_API_KEY", "fake-key")
        monkeypatch.setenv("GEMINI_LLM_MODEL", "gemini-2.5-flash")
        _patch_chat_class(
            monkeypatch, "langchain_google_genai", "ChatGoogleGenerativeAI"
        )

        assert isinstance(llm_provider.get_llm(), _RecordingModel)

    def test_openai_returns_openai_model(self, monkeypatch):
        monkeypatch.setenv("LLM_PROVIDER", "openai")
        monkeypatch.setenv("OPENAI_API_KEY", "fake-key")
        _patch_chat_class(monkeypatch, "langchain_openai", "ChatOpenAI")

        model = llm_provider.get_llm()

        assert isinstance(model, _RecordingModel)
        assert model.kwargs["model"] == llm_provider.OPENAI_DEFAULT_MODEL

    def test_anthropic_returns_anthropic_model(self, monkeypatch):
        monkeypatch.setenv("LLM_PROVIDER", "anthropic")
        monkeypatch.setenv("ANTHROPIC_API_KEY", "fake-key")
        _patch_chat_class(monkeypatch, "langchain_anthropic", "ChatAnthropic")

        model = llm_provider.get_llm()

        assert isinstance(model, _RecordingModel)
        assert model.kwargs["model"] == llm_provider.ANTHROPIC_DEFAULT_MODEL

    def test_ollama_returns_ollama_model_when_pulled(self, monkeypatch):
        monkeypatch.setenv("LLM_PROVIDER", "ollama")
        _patch_chat_class(monkeypatch, "langchain_ollama", "ChatOllama")

        # Fake the ollama client so no local Ollama server is required.
        default_model = llm_provider.OLLAMA_DEFAULT_MODEL
        listed = types.SimpleNamespace(
            models=[types.SimpleNamespace(model=default_model)]
        )
        fake_client = types.SimpleNamespace(list=lambda: listed)
        monkeypatch.setattr(ollama, "Client", lambda: fake_client)

        assert isinstance(llm_provider.get_llm(), _RecordingModel)


class TestFailFast:
    def test_missing_gemini_key_exits(self, monkeypatch):
        monkeypatch.setenv("LLM_PROVIDER", "gemini")
        with pytest.raises(SystemExit):
            llm_provider.get_llm()

    def test_gemini_missing_model_exits(self, monkeypatch):
        monkeypatch.setenv("LLM_PROVIDER", "gemini")
        monkeypatch.setenv("GEMINI_API_KEY", "fake-key")
        # No GEMINI_LLM_MODEL and no model_override.
        with pytest.raises(SystemExit):
            llm_provider.get_llm()

    def test_missing_openai_key_exits(self, monkeypatch):
        monkeypatch.setenv("LLM_PROVIDER", "openai")
        with pytest.raises(SystemExit):
            llm_provider.get_llm()

    def test_missing_anthropic_key_exits(self, monkeypatch):
        monkeypatch.setenv("LLM_PROVIDER", "anthropic")
        with pytest.raises(SystemExit):
            llm_provider.get_llm()

    def test_ollama_unreachable_exits(self, monkeypatch):
        monkeypatch.setenv("LLM_PROVIDER", "ollama")

        def _raise_conn():
            raise ConnectionError("ollama down")

        fake_client = types.SimpleNamespace(list=_raise_conn)
        monkeypatch.setattr(ollama, "Client", lambda: fake_client)

        with pytest.raises(SystemExit):
            llm_provider.get_llm()

    def test_ollama_model_not_pulled_exits(self, monkeypatch):
        monkeypatch.setenv("LLM_PROVIDER", "ollama")
        listed = types.SimpleNamespace(
            models=[types.SimpleNamespace(model="some-other-model:latest")]
        )
        fake_client = types.SimpleNamespace(list=lambda: listed)
        monkeypatch.setattr(ollama, "Client", lambda: fake_client)

        with pytest.raises(SystemExit):
            llm_provider.get_llm()

    def test_invalid_provider_exits(self, monkeypatch):
        monkeypatch.setenv("LLM_PROVIDER", "not-a-real-provider")
        with pytest.raises(SystemExit):
            llm_provider.get_llm()
