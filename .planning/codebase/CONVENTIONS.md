# Coding Conventions

**Analysis Date:** 2026-06-06

## Naming Patterns

**Files:**
- `snake_case` for all Python files: `main.py`, `constants.py`

**Functions:**
- `snake_case`: `get_session_history`, `chat_with_llm`, `main`

**Variables:**
- `snake_case` for local and module-level variables: `gemini_api_key`, `gemini_llm_model`, `history_state`, `user_prompt`, `base_chain`, `conversation_chain`, `chat_template_prompt`

**Constants:**
- `UPPER_SNAKE_CASE` for true constants defined in `constants.py`: `SYSTEM_PROMPT`

**Types:**
- No custom classes defined; standard Python types used

## Code Style

**Formatter/Linter:**
- Ruff (`ruff==0.15.16`) for both linting and formatting
- Commands: `ruff check --fix .` (lint + auto-fix), `ruff format .` (format)
- No `pyproject.toml` or `ruff.toml` present — Ruff runs with default settings

**Indentation:**
- 4 spaces (Python standard, enforced by Ruff)

**String Quotes:**
- Double quotes used consistently: `"AI: {response}"`, `"You: "`, `"Error: {e}"`, `"Welcome! ..."`
- f-strings used for interpolation: `f"AI: {response}"`, `f"Error: {e}"`

**Line Length:**
- Default Ruff limit (88 characters)

**Blank Lines:**
- Two blank lines between top-level function definitions (PEP 8, enforced by Ruff)

## Import Organization

**Order in `main.py`:**
1. Standard library: `os`
2. Third-party packages: `dotenv`, `langchain_core.*`, `langchain_google_genai`
3. Local modules: `from constants import SYSTEM_PROMPT`

**Style:**
- Explicit named imports (`from x import Y`) rather than wildcard imports
- No `__all__` defined
- One import per line

## Type Annotation Usage

**Partial — function signatures only:**
- `get_session_history(session_id: str)` — parameter annotated, return type omitted
- `chat_with_llm(user_prompt: str)` — parameter annotated, return type omitted
- `main()` — no annotation

**Variables:**
- No variable-level type annotations used anywhere

**Pattern:** Type hints applied to function parameters as a documentation aid, but not enforced comprehensively. Return types are not annotated.

## Comment and Docstring Style

**Comments:**
- No inline or block comments present in either file

**Docstrings:**
- No docstrings on any function or module

**String constants:**
- `SYSTEM_PROMPT` in `constants.py` is a multiline string (triple-quoted) serving as a structured LLM system prompt, not a docstring

## Error Handling

**Pattern:** Bare `except Exception as e` in the main loop (`main.py:66`), printing the error with `f"Error: {e}"`. No specific exception types are caught; no re-raising or logging.

## Module Design

**Exports:**
- `constants.py` exports `SYSTEM_PROMPT` as a bare module-level name (no `__all__`)
- `main.py` has no public API — it is an entry point only

**Entry Point Guard:**
- `if __name__ == "__main__": main()` pattern used in `main.py`

## Patterns Used Consistently

**LangChain chain composition:**
- Pipe operator (`|`) for chain construction: `chat_template_prompt | llm | parser`
- `RunnableWithMessageHistory` wraps the base chain; config passed via `RunnableConfig`

**Environment variables:**
- Loaded via `python-dotenv` (`load_dotenv(verbose=True)`)
- Accessed with `os.environ.get(...)` — returns `None` if missing (no hard failure at load time)

**Session management:**
- `history_state` is a module-level dict (`{}`); `get_session_history` performs lazy initialization
- Session ID hardcoded as `"1"` in `chat_with_llm`

---

*Convention analysis: 2026-06-06*
