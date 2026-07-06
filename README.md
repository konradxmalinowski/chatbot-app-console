<h1 align="center">chatbot-app</h1>
<p align="center">
  <img src="https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white" alt="Python 3.11+">
  <img src="https://img.shields.io/badge/LangChain-LCEL-1C3C3C" alt="LangChain LCEL">
  <img src="https://img.shields.io/badge/FastAPI-REST-009688?logo=fastapi&logoColor=white" alt="FastAPI REST API">
  <img src="https://img.shields.io/badge/license-MIT-blue" alt="MIT license">
</p>
<p align="center">
  A multi-provider conversational AI reference app with a CLI, REST API, local RAG, persistent sessions, and approval-gated tools.
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
- [Limitations](#limitations)
- [License](#license)

---

## Overview

`chatbot-app` demonstrates a complete conversational AI stack built with LangChain and LangGraph. It supports Gemini, OpenAI, Anthropic, and Ollama chat models through one interface. The same core chains power an interactive terminal client and a FastAPI service.

The project includes optional retrieval over local documents, JSON-backed conversation history, JWT-protected HTTP endpoints, rate limiting, and an agent whose tool calls require explicit human approval.

---

## Features

- **Multiple model providers** — select Gemini, OpenAI, Anthropic, or local Ollama at startup.
- **Runtime model overrides** — pass any model supported by the active provider with `--model`.
- **Persistent conversations** — save and restore chat history from `sessions/*.json`.
- **Local-document RAG** — index PDF, Markdown, and text files in ChromaDB and return source-aware answers.
- **Two application interfaces** — use the Rich-powered CLI or the FastAPI REST API.
- **Approval-gated agent tools** — review every web search, calculation, or document read before execution.
- **API safeguards** — JWT authentication, request validation, explicit CORS configuration, and rate limiting.
- **Fail-fast configuration** — surface missing keys, unavailable local models, and incomplete prompt placeholders at startup.

---

## Requirements

- Python 3.11 or later
- `pip` and the standard-library `venv` module
- Credentials for one cloud model provider, or a local [Ollama](https://ollama.com/download) installation
- Ollama with `nomic-embed-text` when using the default local RAG embeddings

---

## Getting Started

```bash
# 1. Clone the repository
git clone <repository-url>
cd chatbot-app

# 2. Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate
# Windows PowerShell: .venv\Scripts\Activate.ps1

# 3. Install runtime dependencies
python -m pip install -r requirements.txt

# 4. Create local configuration
cp .env.example .env
# Edit .env and configure one LLM provider.

# 5. Replace every placeholder in src/constants.py SYSTEM_PROMPT

# 6. Start the CLI
python src/main.py
```

The example configuration uses Gemini. To run fully locally, set `LLM_PROVIDER=ollama`, start Ollama, and pull the default chat model:

```bash
ollama pull llama3.2:3b
python src/main.py
```

Keep `.env` out of version control. The file is git-ignored, but you should still review staged changes before every commit.

---

## Configuration

| Variable | Required | Default | Description |
|---|---|---|---|
| `LLM_PROVIDER` | No | `gemini` | Chat provider: `gemini`, `openai`, `anthropic`, or `ollama`. |
| `GEMINI_API_KEY` | For Gemini | None | Google AI Studio API key. |
| `GEMINI_LLM_MODEL` | For Gemini unless `--model` is set | None | Gemini chat model name. |
| `OPENAI_API_KEY` | For OpenAI chat or embeddings | None | Shared by the OpenAI chat and RAG integrations. |
| `ANTHROPIC_API_KEY` | For Anthropic | None | Anthropic API key. |
| `EMBEDDINGS_PROVIDER` | No | `ollama` | RAG embeddings provider: `ollama` or `openai`. |
| `API_SECRET` | For token issuance | None | Pre-shared secret accepted by `POST /auth/token`. |
| `JWT_SECRET_KEY` | For the REST API | None | Separate secret used to sign HS256 JWTs. |
| `CORS_ORIGINS` | No | Empty | Comma-separated allowed origins. Wildcards are rejected. |

Provider defaults when `--model` is omitted:

| Provider | Model source |
|---|---|
| Gemini | `GEMINI_LLM_MODEL` |
| OpenAI | `gpt-4o-mini` |
| Anthropic | `claude-3-5-haiku-latest` |
| Ollama | `llama3.2:3b` |

Generate independent values with `openssl rand -hex 32`; do not reuse `API_SECRET` as `JWT_SECRET_KEY`.

---

## Usage

```bash
# Use the provider and model configured in .env
python src/main.py

# Select a provider and optionally override its model
python src/main.py --llm-provider openai --model gpt-4o-mini
python src/main.py --llm-provider anthropic
python src/main.py --llm-provider ollama

# Ground answers in documents from docs/
python src/main.py --rag

# Enable approval-gated tools
python src/main.py --agent

# Show all CLI options
python src/main.py --help
```

Submit an empty line to exit. The CLI uses the fixed session ID `1`; normal and RAG conversations are persisted in `sessions/1.json`. Agent mode keeps its graph state in memory. `--rag` and `--agent` cannot be combined.

---

## RAG Pipeline

RAG mode retrieves relevant passages from local files and adds them to the model prompt.

- **Corpus** — add `.pdf`, `.md`, or UTF-8 `.txt` files directly to `docs/`.
- **Chunking** — documents are split before indexing and retain their source filenames.
- **Embeddings** — Ollama uses `nomic-embed-text`; OpenAI uses `text-embedding-3-small`.
- **Storage** — ChromaDB persists its collection in the git-ignored `chroma_db/` directory.
- **Retrieval** — each request retrieves the three most relevant chunks.
- **Citations** — the prompt instructs the model to cite grounded claims as `[source: filename]`.
- **Fallback** — the CLI continues without RAG when no readable documents are available; the API returns `503` from `/chat/rag` when its vector store is unavailable.

Prepare the default local embedding model before enabling RAG:

```bash
ollama pull nomic-embed-text
python src/main.py --rag
```

Delete `chroma_db/` and restart the app when you need to rebuild the persisted index after changing the corpus.

---

## REST API

Start the API from the repository root:

```bash
uvicorn api.main:app --app-dir src --reload
```

Interactive OpenAPI documentation is available at `http://127.0.0.1:8000/docs`.

| Endpoint | Auth | Description |
|---|---|---|
| `POST /auth/token` | `API_SECRET` in the request body | Issues a Bearer JWT valid for one hour; limited to 5 requests per minute. |
| `POST /chat` | Bearer JWT | Runs a standard conversation turn. |
| `POST /chat/rag` | Bearer JWT | Runs a grounded turn and returns retrieved source excerpts. |
| `POST /agent` | Bearer JWT | Starts or continues an agent turn until completion or approval is required. |
| `POST /agent/{pending_id}/approve` | Bearer JWT | Executes all pending tool calls and resumes the agent. |
| `POST /agent/{pending_id}/reject` | Bearer JWT | Rejects all pending tool calls and resumes without them. |
| `GET /health` | None | Reports service and vector-store readiness. |

Protected chat and agent routes are limited to 20 requests per minute. A `session_id` must contain 1–64 letters, digits, underscores, or hyphens. Messages must contain 1–2,000 characters and cannot be blank.

```bash
# Exchange the pre-shared secret for a JWT.
TOKEN=$(curl --silent --request POST http://127.0.0.1:8000/auth/token \
  --header "Content-Type: application/json" \
  --data '{"api_secret":"replace-with-api-secret"}' \
  | python -c "import json,sys; print(json.load(sys.stdin)['access_token'])")

# Send a chat message.
curl --request POST http://127.0.0.1:8000/chat \
  --header "Authorization: Bearer $TOKEN" \
  --header "Content-Type: application/json" \
  --data '{"message":"Hello","session_id":"demo"}'
```

This authentication scheme is intended for service-to-service use. It does not provide individual user accounts or session ownership.

---

## LangGraph Agent

Agent mode exposes three tools:

- `web_search` searches the web through DuckDuckGo.
- `calculator` evaluates a restricted set of arithmetic expressions without `eval` or `exec`.
- `read_doc` reads supported files only from `docs/`.

No tool runs automatically. The CLI prompts `Approve tool call? [y/N]:`. The API returns `status: "pending_approval"` with a `pending_id` and the complete list of proposed calls; the client must then call the approve or reject endpoint.

Every approval decision is appended to the git-ignored `logs/agent.jsonl` file. Pending API approvals and agent state are stored in memory and are lost when the server restarts.

---

## Customizing the System Prompt

Edit `SYSTEM_PROMPT` in `src/constants.py` before running the app. Replace every bracketed placeholder, including the project name, assistant goal, supported topics, contact path, and preferred form of address.

The Polish prompt is an intentional project exception to the English-only documentation rule. Startup validation stops the app while any placeholder remains unresolved.

---

## Project Structure

```text
chatbot-app/
├── src/
│   ├── main.py             # CLI entry point and interactive loops
│   ├── chain_builder.py    # Shared standard and RAG LCEL chains
│   ├── constants.py        # Prompt, paths, and application limits
│   ├── llm_provider.py     # Gemini, OpenAI, Anthropic, and Ollama adapters
│   ├── session_store.py    # JSON conversation persistence
│   ├── api/                # FastAPI routes, models, auth, and rate limits
│   ├── agent/              # LangGraph workflow and approval-gated tools
│   └── rag/                # Loading, chunking, embeddings, retrieval, and storage
├── docs/                   # Source documents for RAG and read_doc
├── reports/                # Project reports
├── .env.example            # Safe configuration template
├── requirements.txt        # Pinned runtime dependencies
├── requirements-dev.txt    # Pytest and Ruff
├── PROJECT_RULES.md        # Repository conventions
└── LICENSE                 # MIT license
```

Runtime data is written to `sessions/`, `chroma_db/`, and `logs/`. These directories are excluded from version control.

---

## Development

```bash
# Install development tools after runtime dependencies.
python -m pip install -r requirements-dev.txt

# Check and automatically fix lint issues.
ruff check --fix .

# Format Python files.
ruff format .

# Run tests when a test suite is added.
pytest
```

The repository does not currently include automated tests or CI. Run the CLI and relevant API requests manually after changes.

---

## Limitations

- The CLI uses one hardcoded session ID and is not a multi-user client.
- API authentication identifies one shared service client, not individual users.
- Any valid API token can address any valid `session_id` or `pending_id`.
- The local JSON session store is not designed for concurrent distributed workers.
- Agent checkpoints and pending approvals do not survive process restarts.
- RAG indexing is local and requires an explicit index rebuild after corpus changes.

---

## License

This project is licensed under the MIT License. See [`LICENSE`](LICENSE).
