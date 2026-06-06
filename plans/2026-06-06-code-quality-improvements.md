# Plan: Code Quality Improvements

**Date:** 2026-06-06
**Task slug:** code-quality-improvements

## Task Description

Improve code quality of the educational CLI chatbot without changing any features or user-facing behavior. All changes are structural/defensive improvements.

## Acceptance Criteria

- App exits with code 1 and a friendly message when env vars are missing
- All module-level initialization moved into `build_chain()` factory
- `chat_with_llm` catches specific Google API errors with targeted messages
- Session ID constant replaces magic string "1"
- SYSTEM_PROMPT placeholder validation warns if template not filled in
- `verbose=True` removed from `load_dotenv()`
- `chat_with_llm` has return type annotation and returns string; `print` moved to call site
- `MAX_INPUT_LENGTH = 2000` enforced before calling LLM
- Streaming output via `.stream()` replacing `.invoke()`
- `requirements-dev.txt` created with ruff + pytest; ruff removed from `requirements.txt`
- Unused packages removed from `requirements.txt`
- `CLAUDE.md` updated for dev dependencies and pytest location
- `ruff check --fix . && ruff format .` passes cleanly

## Files to Modify

- `main.py` — all structural changes (items 1-3, 6-9)
- `constants.py` — add `DEFAULT_SESSION_ID`, `MAX_INPUT_LENGTH` (items 4, 8)
- `requirements.txt` — remove unused packages and ruff (item 11)
- `CLAUDE.md` — update Setup and No tests sections (item 12)

## Files to Create

- `requirements-dev.txt` — ruff + pytest (item 10)
- `.env.example` — already exists, no change needed
- `plans/2026-06-06-code-quality-improvements.md` — this file

## Error Handling Strategy

- Missing env vars: `sys.exit(1)` with user-friendly message before any LLM init
- GoogleAPIError: catch with "API error" message using `logging.error()`
- PermissionDenied: catch with "API key invalid or quota exceeded" message
- Broad Exception fallback: `logging.error()` with full exception

## Edge Cases

- Empty/whitespace env vars must also be caught (not just missing)
- SYSTEM_PROMPT placeholder check is a warning, not a hard error
- Input too long: skip the call and print a warning, do not exit
- Streaming: must print trailing newline after stream completes
- `get_session_history` closure must still reference `history_state` from `build_chain` scope
