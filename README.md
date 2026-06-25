<h1 align="center">chatbot-app</h1>
<p align="center">
  <img src="https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white" alt="Python 3.11+">
  <img src="https://img.shields.io/badge/LangChain-LCEL-1C3C3C?logo=langchain&logoColor=white" alt="LangChain">
  <img src="https://img.shields.io/badge/Google_Gemini-2.5_flash-4285F4?logo=google&logoColor=white" alt="Google Gemini">
  <img src="https://img.shields.io/badge/license-MIT-blue" alt="License MIT">
</p>
<p align="center">
  An educational CLI chatbot built with LangChain LCEL pipelines and Google Gemini — demonstrating conversation history management, session persistence, and Rich terminal output.
</p>

---

## Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Requirements](#requirements)
- [Getting Started](#getting-started)
- [Configuration](#configuration)
- [Usage](#usage)
- [Customizing the System Prompt](#customizing-the-system-prompt)
- [Project Structure](#project-structure)
- [Development](#development)
- [License](#license)

---

## Overview

`chatbot-app` is a learning-oriented project that demonstrates how to wire a production-style conversational AI using LangChain's LCEL (LangChain Expression Language) with Google Gemini as the LLM backend. Conversation history is persisted between sessions as JSON, the model can be swapped at runtime via a CLI flag, and the terminal UX is handled by `rich`.

---

## Features

- **Model selection** — choose any Gemini model at runtime via `--model`; default is read from `.env`
- **Session persistence** — conversation history is saved to `sessions/` as JSON and automatically restored on next run
- **Rich terminal output** — colored prompts and formatted responses via the `rich` library
- **Input validation** — rejects inputs exceeding 2 000 characters with a clear error message
- **Startup checks** — fails fast with descriptive errors when `GEMINI_API_KEY` is missing or `SYSTEM_PROMPT` still contains unfilled placeholders

---

## Requirements

- Python 3.11+
- A [Google AI Studio](https://aistudio.google.com/app/apikey) API key (`gemini-2.5-flash` or any Gemini model)

---

## Getting Started

```bash
# 1. Clone the repository
git clone <repository-url>
cd chatbot-app

# 2. Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment variables
cp .env.example .env
# Edit .env and set GEMINI_API_KEY and GEMINI_LLM_MODEL
```

> **Security:** A pre-commit hook in `.git/hooks/pre-commit` blocks accidental commits of `.env`. It is installed automatically on clone. To install manually: `chmod +x .git/hooks/pre-commit`.

---

## Configuration

| Variable | Required | Description |
|---|---|---|
| `GEMINI_API_KEY` | Yes | Google AI Studio API key |
| `GEMINI_LLM_MODEL` | Yes | Gemini model name (e.g. `gemini-2.5-flash`) |

Copy `.env.example` to `.env` and fill in both values. Never commit `.env`.

---

## Usage

```bash
# Start the chatbot with the model defined in .env
python main.py

# Override the model at runtime
python main.py --model gemini-1.5-pro
```

Exit the chat by submitting an empty line (press Enter on a blank prompt).

---

## Customizing the System Prompt

`constants.py` contains `SYSTEM_PROMPT` — a chatbot persona template with bracketed placeholders such as `[NAZWA FIRMY / PROJEKTU]` and `[GŁÓWNY CEL BOTA]`. Replace every `[...]` placeholder with your project's name, goal, contact information, and topic scope before deploying for any specific use case. The startup check will refuse to run if any placeholder remains unfilled.

---

## Project Structure

```
chatbot-app/
├── main.py               # Entry point — CLI loop, LangChain chain, session wiring
├── constants.py          # SYSTEM_PROMPT, DEFAULT_SESSION_ID, MAX_INPUT_LENGTH
├── session_store.py      # JSON session persistence utilities
├── requirements.txt      # Pinned runtime dependencies
├── requirements-dev.txt  # Dev tools: pytest, ruff
├── .env.example          # Environment variable template (safe to commit)
├── docs/                 # Stage documentation
└── sessions/             # Runtime session files (git-ignored)
```

---

## Development

```bash
pip install -r requirements-dev.txt

# Lint and auto-fix
ruff check --fix .

# Format
ruff format .
```

---

## License

MIT — see [`LICENSE`](LICENSE) for details.
