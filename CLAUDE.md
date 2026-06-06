# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

Educational CLI chatbot using LangChain + Google Gemini (`gemini-2.5-flash`). Single-session, in-memory conversation history — history is lost on restart.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env            # then fill in GEMINI_API_KEY
```

## Environment variables

Both must be present in `.env`:

| Variable | Description |
|---|---|
| `GEMINI_API_KEY` | Google AI Studio API key |
| `GEMINI_LLM_MODEL` | Model name, e.g. `gemini-2.5-flash` |

## Run

```bash
python main.py
```

Exit the chat by submitting an empty prompt.

## Linting and formatting

Uses **Ruff** for both linting and formatting:

```bash
ruff check --fix .   # lint + auto-fix
ruff format .        # format
```

## Architecture notes

- `main.py` — entry point; builds the LangChain chain and runs the chat loop
- `constants.py` — holds `SYSTEM_PROMPT`; the bracketed placeholders (`[NAZWA FIRMY]`, `[GŁÓWNY CEL BOTA]`, etc.) are intentional and should be customized before deploying
- Session ID is hardcoded as `"1"` — there is no multi-user support
- Chat history lives in `history_state` dict in memory; it does not persist between runs

## No tests

There is no test suite yet. When adding tests, use pytest.
