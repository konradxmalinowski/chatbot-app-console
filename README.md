# chatbot-app

An educational CLI chatbot built with [LangChain](https://python.langchain.com/)
and Google Gemini (`gemini-2.5-flash`). Demonstrates LangChain LCEL pipelines,
conversation history management, and terminal output with Rich.

## Features

- **Model selection** — choose any Gemini model at runtime via `--model`
- **Session persistence** — conversation history saved to `sessions/` as JSON and
  restored on next run
- **Rich terminal output** — colored prompts via the `rich` library
- **Input validation** — rejects inputs exceeding 2 000 characters
- **Startup checks** — clear error messages when `GEMINI_API_KEY` is missing or
  when `SYSTEM_PROMPT` still contains unfilled placeholders

## Prerequisites

- Python 3.11 or higher
- A [Google AI Studio](https://aistudio.google.com/app/apikey) API key

## Setup

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
# Edit .env and set your GEMINI_API_KEY
```

> **Security note:** A pre-commit hook is included in `.git/hooks/pre-commit`
> that prevents accidentally committing the `.env` file. It is installed
> automatically when you clone the repository and activate the hook directory.
> If you need to install it manually: `chmod +x .git/hooks/pre-commit`.

## Configuration

| Variable | Required | Description |
|----------|----------|-------------|
| `GEMINI_API_KEY` | Yes | Google AI Studio API key |
| `GEMINI_LLM_MODEL` | Yes | Gemini model name (e.g. `gemini-2.5-flash`) |

Copy `.env.example` to `.env` and fill in both values. Never commit `.env`.

## Usage

```bash
# Start the chatbot with the model from .env
python main.py

# Override the model at runtime
python main.py --model gemini-1.5-pro
```

Exit the chat by submitting an empty line (press Enter on a blank prompt).

## Project Structure

```
chatbot-app/
├── main.py            # Entry point — CLI loop, LangChain chain, session wiring
├── constants.py       # SYSTEM_PROMPT, DEFAULT_SESSION_ID, MAX_INPUT_LENGTH
├── session_store.py   # JSON session persistence utilities
├── requirements.txt   # Pinned runtime dependencies
├── requirements-dev.txt  # Dev tools: pytest, ruff
├── .env.example       # Environment variable template (safe to commit)
├── docs/              # Polish-language stage documentation
└── sessions/          # Runtime session files (git-ignored)
```

## Customising the System Prompt

`constants.py` contains `SYSTEM_PROMPT`, a Polish-language chatbot persona
template. It includes bracketed placeholders such as `[NAZWA FIRMY / PROJEKTU]`
and `[GŁÓWNY CEL BOTA]` that must be replaced with real values before deploying
the bot for any specific use case.

Open `constants.py` and substitute every `[...]` placeholder with your project's
name, goal, contact information, and topic areas.

## Development

```bash
# Install dev tools
pip install -r requirements-dev.txt

# Lint and auto-fix
ruff check --fix .

# Format
ruff format .
```

## License

Educational use. No license file is included — treat this as a learning reference,
not production software.
