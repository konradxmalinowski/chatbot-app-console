# Testing Patterns

**Analysis Date:** 2026-06-06

## Current State

**No tests exist.** There is no test directory, no test files, and no test runner configuration. This is explicitly documented in `CLAUDE.md`: "There is no test suite yet."

## Test Framework

**Recommended:** pytest (per `CLAUDE.md`: "When adding tests, use pytest")

**Currently installed:** pytest is not in `requirements.txt`. It must be added before writing tests.

**Run Commands (once set up):**
```bash
pip install pytest pytest-mock        # install
pytest                                 # run all tests
pytest -v                             # verbose output
pytest --cov=. --cov-report=term      # with coverage (requires pytest-cov)
```

## What Should Be Tested

### `get_session_history` (`main.py:33`)
- Returns a new `InMemoryChatMessageHistory` for an unknown session ID
- Returns the same object for a repeated session ID (identity check)
- Populates `history_state` dict on first call
- Handles multiple different session IDs independently

### `chat_with_llm` (`main.py:47`)
- Calls `conversation_chain.invoke` with the correct `input` key
- Passes a `RunnableConfig` with `session_id: "1"`
- Prints the response prefixed with `"AI: "`
- Does not raise on normal invocation (requires mocking the chain)

### `main` loop (`main.py:55`)
- Exits cleanly on empty input (`""` or whitespace-only)
- Calls `chat_with_llm` with the user's prompt
- Catches exceptions from `chat_with_llm` and prints `"Error: ..."` without crashing

### `constants.py`
- `SYSTEM_PROMPT` is a non-empty string
- `SYSTEM_PROMPT` contains expected structural markers (e.g., `# ROLE`, `# CONTEXT`)

## Challenges for Testing

**LLM calls require a live API key:**
- `ChatGoogleGenerativeAI` makes network requests to Google's API
- Tests must mock `conversation_chain.invoke` or the `llm` object to avoid real calls
- Use `unittest.mock.patch` or `pytest-mock`'s `mocker.patch`

**Module-level side effects at import time:**
- `load_dotenv(verbose=True)` runs on import
- `llm`, `parser`, `chat_template_prompt`, `base_chain`, and `conversation_chain` are constructed at module level
- Importing `main` without a valid `GEMINI_API_KEY` in the environment may cause errors depending on LangChain's validation
- Mitigation: set dummy env vars before importing, or refactor construction into a factory function

**Mutable global state:**
- `history_state = {}` is module-level and shared across all tests
- Tests that call `get_session_history` will mutate this dict
- Mitigation: clear `history_state` in a `setup`/teardown fixture, or reset via `importlib.reload`

**Hardcoded session ID:**
- `chat_with_llm` always uses `session_id: "1"` — no way to isolate sessions per test without patching

## Recommended Test Structure

```
chatbot-app/
├── main.py
├── constants.py
├── requirements.txt
└── tests/
    ├── __init__.py
    ├── test_session_history.py   # unit tests for get_session_history
    ├── test_chat.py              # unit tests for chat_with_llm (mocked chain)
    ├── test_main_loop.py         # integration tests for main() input handling
    └── test_constants.py        # smoke tests for SYSTEM_PROMPT structure
```

## Example Test Patterns

**Testing `get_session_history` (pure unit test — no mocking needed):**
```python
import main

def test_get_session_history_creates_new_session():
    main.history_state.clear()
    history = main.get_session_history("test-session")
    assert "test-session" in main.history_state

def test_get_session_history_returns_same_object():
    main.history_state.clear()
    h1 = main.get_session_history("abc")
    h2 = main.get_session_history("abc")
    assert h1 is h2
```

**Testing `chat_with_llm` (requires mocking the chain):**
```python
from unittest.mock import patch
import main

def test_chat_with_llm_prints_response(capsys):
    with patch.object(main.conversation_chain, "invoke", return_value="Hello!"):
        main.chat_with_llm("hi")
    captured = capsys.readouterr()
    assert "AI: Hello!" in captured.out
```

**Testing exception handling in `main` loop:**
```python
from unittest.mock import patch, MagicMock
import main

def test_main_loop_handles_exception(capsys, monkeypatch):
    inputs = iter(["trigger error", ""])
    monkeypatch.setattr("builtins.input", lambda _: next(inputs))
    with patch.object(main, "chat_with_llm", side_effect=RuntimeError("boom")):
        main.main()
    captured = capsys.readouterr()
    assert "Error: boom" in captured.out
```

## Coverage Targets (recommended)

| Module | Priority | Notes |
|--------|----------|-------|
| `get_session_history` | High | Pure logic, easy to test |
| `chat_with_llm` | High | Mock the chain; verify print output |
| `main` loop | Medium | Test exit condition and error path |
| `constants.py` | Low | Smoke test only |

---

*Testing analysis: 2026-06-06*
