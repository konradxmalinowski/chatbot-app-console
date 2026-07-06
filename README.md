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
- [RAG Pipeline](#rag-pipeline)
- [REST API](#rest-api)
- [LangGraph Agent](#langgraph-agent)
- [Customizing the System Prompt](#customizing-the-system-prompt)
- [Project Structure](#project-structure)
- [Development](#development)
- [License](#license)

---

## Overview

`chatbot-app` is a learning-oriented project that demonstrates how to wire a production-style conversational AI using LangChain's LCEL (LangChain Expression Language). The LLM backend defaults to Google Gemini but is pluggable — OpenAI, Anthropic, and local Ollama are also supported via `--llm-provider`/`LLM_PROVIDER`. Conversation history is persisted between sessions as JSON, the model can be swapped at runtime via a CLI flag, and the terminal UX is handled by `rich`.

---

## Features

- **Multi-provider LLM selection** — choose the chat model backend at runtime via `--llm-provider` (or the `LLM_PROVIDER` env var): Gemini (default), OpenAI, Anthropic, or local Ollama
- **Model selection** — choose any model at runtime via `--model` (works with whichever provider is active); default is read from `.env`
- **Session persistence** — conversation history is saved to `sessions/` as JSON and automatically restored on next run
- **Rich terminal output** — colored prompts and formatted responses via the `rich` library
- **Input validation** — rejects inputs exceeding 2 000 characters with a clear error message
- **Startup checks** — fails fast with descriptive errors when `GEMINI_API_KEY` is missing or `SYSTEM_PROMPT` still contains unfilled placeholders
- **Retrieval-augmented generation** — optional `--rag` mode answers questions grounded in local documents (`.pdf`, `.txt`, `.md`) with source citations, backed by a local ChromaDB vector store
- **REST API** — the same chat/RAG functionality exposed over HTTP via FastAPI, with JWT auth, per-token rate limiting, and Swagger docs
- **Agent with tools** — optional `--agent` mode adds web search, a calculator, and a document reader behind a mandatory human-in-the-loop approval gate (CLI `[y/N]` prompt, or a two-step approve/reject flow over the API)

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
| `LLM_PROVIDER` | No | Chat model backend: `gemini` (default), `openai`, `anthropic`, or `ollama` |
| `GEMINI_API_KEY` | Only if `LLM_PROVIDER=gemini` (the default) | Google AI Studio API key |
| `GEMINI_LLM_MODEL` | Only if `LLM_PROVIDER=gemini`, unless `--model` is passed | Gemini model name (e.g. `gemini-2.5-flash`) |
| `OPENAI_API_KEY` | Only if `LLM_PROVIDER=openai` or `EMBEDDINGS_PROVIDER=openai` | OpenAI API key — shared by chat and RAG embeddings |
| `ANTHROPIC_API_KEY` | Only if `LLM_PROVIDER=anthropic` | Anthropic API key |
| `EMBEDDINGS_PROVIDER` | No | Embeddings backend for `--rag`: `ollama` (default, local) or `openai` |
| `API_SECRET` | Only for the REST API | Pre-shared secret exchanged for a JWT via `POST /auth/token` |
| `JWT_SECRET_KEY` | Only for the REST API | Signs issued JWTs (HS256); must differ from `API_SECRET` |
| `CORS_ORIGINS` | Only for the REST API | Comma-separated allowed origins; unset = none allowed (fail closed) |

Copy `.env.example` to `.env` and fill in the values you need. Never commit `.env`. Generate secrets with `openssl rand -hex 32`.

Ollama (`LLM_PROVIDER=ollama` or `EMBEDDINGS_PROVIDER=ollama`) requires no cloud key, but does require [Ollama](https://ollama.com/download) running locally with the relevant model pulled — the app fails fast with the exact `ollama pull <model>` command if it isn't.

---

## Usage

```bash
# Start the chatbot with the provider/model defined in .env (defaults to Gemini)
python main.py

# Override the model at runtime (works with whichever provider is active)
python main.py --model gemini-1.5-pro

# Switch LLM provider at runtime (overrides LLM_PROVIDER)
python main.py --llm-provider ollama
python main.py --llm-provider openai --model gpt-4o-mini
python main.py --llm-provider anthropic --model claude-3-5-haiku-latest

# Enable RAG mode — answers are grounded in docs/, with source citations
python main.py --rag

# Enable agent mode — tools with a [y/N] approval prompt before every call
python main.py --agent
```

Exit the chat by submitting an empty line (press Enter on a blank prompt). `--agent` and `--rag` cannot be combined.

---

## RAG Pipeline

`--rag` retrieves relevant chunks from local documents and injects them into the prompt, with the model instructed to cite its sources.

- **Corpus** — place `.pdf`, `.txt`, or `.md` files in `docs/`. A placeholder `docs/sample-faq.md` is included so the feature works out of the box; replace or supplement it with your own documents.
- **Embeddings** — set `EMBEDDINGS_PROVIDER` in `.env`:
  - `ollama` (default) — runs locally, no cloud key needed. Requires [Ollama](https://ollama.com/download) running with the embedding model pulled: `ollama pull nomic-embed-text`.
  - `openai` — uses `text-embedding-3-small`, requires `OPENAI_API_KEY`.
- **Vector store** — [ChromaDB](https://www.trychroma.com/), persisted to `chroma_db/` (git-ignored). Documents are only embedded once; subsequent runs load the existing collection.
- **Citations** — responses reference sources inline as `[source: filename]`. If nothing relevant was retrieved, the model says so instead of guessing.
- **Fallback** — if `docs/` has no usable content, `--rag` prints a warning and continues in normal (non-RAG) mode rather than failing.

Without `--rag`, behavior is unchanged from the base chatbot.

---

## REST API

The same chat/RAG functionality is available over HTTP via FastAPI (`api/`), as an additional entry point alongside the CLI:

```bash
pip install -r requirements.txt   # includes fastapi, uvicorn, pyjwt, slowapi
uvicorn api.main:app --reload
```

- **`GET /docs`** — Swagger UI (automatic).
- **`POST /auth/token`** — exchange `API_SECRET` for a short-lived (1h) JWT. Service-to-service auth (pre-shared secret), not a per-user login system. Rate limited 5/min to slow down brute-forcing `API_SECRET`.
- **`POST /chat`** / **`POST /chat/rag`** — Bearer-authenticated, rate limited 20/min per token (or per IP for unauthenticated requests, so failed-auth traffic is throttled too). Body: `{"message": str, "session_id": str}`. `/chat/rag` also returns `sources` and responds `503` if the vector store isn't ready.
- **`GET /health`** — no auth required, not rate limited. Reports `{"status": "ok", "vector_store": "ready" | "not_initialized"}`.
- **CORS** fails closed: set `CORS_ORIGINS` to an explicit comma-separated list, or nothing is allowed.

Example:

```bash
# Get a token
TOKEN=$(curl -s -X POST localhost:8000/auth/token \
  -H "Content-Type: application/json" \
  -d '{"api_secret":"<your API_SECRET>"}' | python3 -c "import sys,json;print(json.load(sys.stdin)['access_token'])")

# Chat
curl -X POST localhost:8000/chat \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"message":"Hello!","session_id":"my-session"}'
```

---

## LangGraph Agent

`--agent` (CLI) and `POST /agent` (API) run a LangGraph agent with three tools — web search (DuckDuckGo, no API key), a calculator (safe, no `eval`), and a document reader scoped to `docs/` — behind a **mandatory** human-in-the-loop approval gate: no tool ever runs without explicit approval.

- **CLI** — when the agent wants to use a tool, it prints the proposed call(s) and prompts `Approve tool call? [y/N]:` before running anything.
- **API** — a two-step flow, since there's no terminal to prompt in:
  1. `POST /agent` `{"message": str, "session_id": str}` runs the agent. If it wants to call a tool, the response is `{"status": "pending_approval", "pending_id": str, "pending_tool_calls": [{"tool": str, "args": dict}, ...]}` — every proposed call, not just one.
  2. `POST /agent/{pending_id}/approve` executes the pending call(s) and continues (may pause again on a further tool call, or return `{"status": "complete", "response": str}`).
  3. `POST /agent/{pending_id}/reject` declines instead — the agent acknowledges it can't complete that step rather than retrying.
- **Logging** — every tool-call attempt (approved or declined) is appended to `logs/agent.jsonl` (git-ignored).
- **Safety** — the calculator can't execute arbitrary code (AST-based, not `eval`/`exec`) and rejects expressions whose result would be too large to compute cheaply; the document reader can't read outside `docs/`.

Example (API):

```bash
PENDING=$(curl -s -X POST localhost:8000/agent \
  -H "Content-Type: application/json" -H "Authorization: Bearer $TOKEN" \
  -d '{"message":"What is 47 times 89?","session_id":"my-session"}')
echo "$PENDING"   # {"status":"pending_approval","pending_id":"my-session",...}

curl -X POST localhost:8000/agent/my-session/approve \
  -H "Authorization: Bearer $TOKEN"
```

---

## Customizing the System Prompt

`constants.py` contains `SYSTEM_PROMPT` — a chatbot persona template with bracketed placeholders such as `[NAZWA FIRMY / PROJEKTU]` and `[GŁÓWNY CEL BOTA]`. Replace every `[...]` placeholder with your project's name, goal, contact information, and topic scope before deploying for any specific use case. The startup check will refuse to run if any placeholder remains unfilled.

---

## Project Structure

```
chatbot-app/
├── main.py               # CLI entry point — chat loop, session wiring
├── api/                  # REST API entry point: FastAPI app, JWT auth, rate limiting
├── agent/                # LangGraph agent: tools (web search, calculator, read_doc), graph
├── chain_builder.py      # LCEL chain construction shared by main.py and api/
├── llm_provider.py       # LLM_PROVIDER dispatch: gemini/openai/anthropic/ollama chat model construction
├── constants.py          # SYSTEM_PROMPT, DEFAULT_SESSION_ID, MAX_INPUT_LENGTH, RAG/agent constants
├── session_store.py      # JSON session persistence utilities
├── rag/                  # RAG pipeline: loader, chunker, embeddings, store, retriever, bootstrap
├── requirements.txt      # Pinned runtime dependencies
├── requirements-dev.txt  # Dev tools: pytest, ruff
├── .env.example          # Environment variable template (safe to commit)
├── docs/                 # RAG corpus — .pdf/.txt/.md documents indexed by --rag
├── chroma_db/            # ChromaDB persistence (git-ignored, created on first --rag run)
├── logs/                 # Agent tool-call logs (git-ignored, created on first --agent run)
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
