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
- **Retrieval-augmented generation** — optional `--rag` mode answers questions grounded in local documents (`.pdf`, `.txt`, `.md`) with source citations, backed by a local ChromaDB vector store
- **REST API** — the same chat/RAG functionality exposed over HTTP via FastAPI, with JWT auth, per-token rate limiting, and Swagger docs

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
| `EMBEDDINGS_PROVIDER` | No | Embeddings backend for `--rag`: `ollama` (default, local) or `openai` |
| `OPENAI_API_KEY` | Only if `EMBEDDINGS_PROVIDER=openai` | OpenAI API key for embeddings |
| `API_SECRET` | Only for the REST API | Pre-shared secret exchanged for a JWT via `POST /auth/token` |
| `JWT_SECRET_KEY` | Only for the REST API | Signs issued JWTs (HS256); must differ from `API_SECRET` |
| `CORS_ORIGINS` | Only for the REST API | Comma-separated allowed origins; unset = none allowed (fail closed) |

Copy `.env.example` to `.env` and fill in the values you need. Never commit `.env`. Generate secrets with `openssl rand -hex 32`.

---

## Usage

```bash
# Start the chatbot with the model defined in .env
python main.py

# Override the model at runtime
python main.py --model gemini-1.5-pro

# Enable RAG mode — answers are grounded in docs/, with source citations
python main.py --rag
```

Exit the chat by submitting an empty line (press Enter on a blank prompt).

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

## Customizing the System Prompt

`constants.py` contains `SYSTEM_PROMPT` — a chatbot persona template with bracketed placeholders such as `[NAZWA FIRMY / PROJEKTU]` and `[GŁÓWNY CEL BOTA]`. Replace every `[...]` placeholder with your project's name, goal, contact information, and topic scope before deploying for any specific use case. The startup check will refuse to run if any placeholder remains unfilled.

---

## Project Structure

```
chatbot-app/
├── main.py               # CLI entry point — chat loop, session wiring
├── api/                  # REST API entry point: FastAPI app, JWT auth, rate limiting
├── chain_builder.py      # LCEL chain construction shared by main.py and api/
├── constants.py          # SYSTEM_PROMPT, DEFAULT_SESSION_ID, MAX_INPUT_LENGTH, RAG constants
├── session_store.py      # JSON session persistence utilities
├── rag/                  # RAG pipeline: loader, chunker, embeddings, store, retriever, bootstrap
├── requirements.txt      # Pinned runtime dependencies
├── requirements-dev.txt  # Dev tools: pytest, ruff
├── .env.example          # Environment variable template (safe to commit)
├── docs/                 # RAG corpus — .pdf/.txt/.md documents indexed by --rag
├── chroma_db/            # ChromaDB persistence (git-ignored, created on first --rag run)
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
