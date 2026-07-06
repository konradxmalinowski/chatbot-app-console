# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

See `PROJECT_RULES.md` for the standing collaboration rules (git authorship, commit vs.
push approval, English-only exceptions, GSD workflow) and a stack/process comparison
against this repo — read it at the start of every session, same as this file.

## Project

Educational CLI chatbot using LangChain + Google Gemini (`gemini-2.5-flash`). Single-session, in-memory conversation history — history is lost on restart. Optional RAG mode (`--rag`) retrieves context from local documents in `docs/` via a ChromaDB vector store — see "RAG pipeline" below.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
pip install -r requirements-dev.txt   # dev tools: ruff, pytest
cp .env.example .env            # then fill in GEMINI_API_KEY
```

## Environment variables

`GEMINI_API_KEY` and `GEMINI_LLM_MODEL` must be present in `.env`. The RAG variables are
only needed when running with `--rag` (or the REST API, which builds the RAG store at
startup regardless of a flag). The `API_SECRET` / `JWT_SECRET_KEY` / `CORS_ORIGINS`
variables are only needed to run the REST API (see below):

| Variable | Description |
|---|---|
| `GEMINI_API_KEY` | Google AI Studio API key |
| `GEMINI_LLM_MODEL` | Model name, e.g. `gemini-2.5-flash` |
| `EMBEDDINGS_PROVIDER` | `ollama` (default) or `openai` — embeddings backend for `--rag` |
| `OPENAI_API_KEY` | Only required when `EMBEDDINGS_PROVIDER=openai` |
| `API_SECRET` | REST API only — pre-shared secret exchanged for a JWT via `POST /auth/token` |
| `JWT_SECRET_KEY` | REST API only — signs issued JWTs (HS256); must differ from `API_SECRET` |
| `CORS_ORIGINS` | REST API only — comma-separated allowed origins; unset/empty = none allowed (fail closed) |

## Run

```bash
python main.py         # normal mode
python main.py --rag   # RAG mode — retrieves context from docs/, cites sources
```

Exit the chat by submitting an empty prompt.

## REST API (Phase 3)

A FastAPI app in `api/` exposes the same chat/RAG functionality over HTTP, as an
additional entry point alongside the CLI (the CLI is unaffected by it):

```bash
uvicorn api.main:app --reload
```

- `GET /docs` — Swagger UI (automatic).
- `POST /auth/token` — exchange `API_SECRET` for a short-lived (1h) JWT. This is
  service-to-service auth (pre-shared secret), not a per-user login system. Rate
  limited (5/min) to slow down brute-forcing `API_SECRET`.
- `POST /chat` / `POST /chat/rag` — Bearer-authenticated (`Authorization: Bearer
  <jwt>`), rate limited 20/min per token. Body: `{"message": str, "session_id": str}`;
  `session_id` is constrained to `^[a-zA-Z0-9_-]{1,64}$` (it becomes part of a file
  path in `session_store.py`, so this is a mandatory path-traversal guard, not just
  input hygiene). `/chat/rag` additionally returns `sources` (file + truncated chunk)
  and responds `503` if the RAG vector store never initialized.
- `GET /health` — no auth; reports `vector_store: "ready" | "not_initialized"`;
  exempt from rate limiting (`@limiter.exempt`) since it's a monitoring endpoint.
- Multi-session history: unlike the CLI's single hardcoded `session_id="1"`, the API
  keeps one `InMemoryChatMessageHistory` per `session_id` per process, lazily loaded
  from `sessions/<session_id>.json` on first use and saved back after every turn.
  `/chat` and `/chat/rag` share the **same** history store keyed by `session_id` —
  a session is one continuous conversation regardless of which endpoint served a
  given turn; two separate stores were tried first and silently lost turns when a
  client interleaved calls to both endpoints with the same `session_id`.
- `chain_builder.py` and `rag/bootstrap.py` hold the LCEL chain construction and RAG
  vector-store bootstrap logic shared between `main.py` and `api/main.py` — see their
  docstrings before changing either entry point's chat behavior.
- Rate limiting on `/chat` and `/chat/rag` has **no per-route `@limiter.limit(...)`
  decorator** — deliberately. slowapi's `SlowAPIMiddleware` (`api/rate_limit.py`)
  enforces `default_limits` at the ASGI layer, before FastAPI resolves
  `Depends(verify_token)`; a per-route decorator's check only runs *inside* the
  endpoint body, so a request with no/invalid token would never reach it and would
  go completely unrate-limited. `/auth/token` keeps its own decorator since it has
  no auth dependency that can fail first. See `api/rate_limit.py`'s comments before
  changing either mechanism.

## RAG pipeline

- `rag/loader.py` — loads `.pdf` / `.txt` / `.md` files from `docs/` (unsupported
  extensions and unreadable files are skipped with a logged warning, not fatal).
- `rag/chunker.py` — splits documents into overlapping chunks (`RecursiveCharacterTextSplitter`,
  1000 chars / 200 overlap), tagging each with `source` and `chunk_index` metadata.
- `rag/embeddings.py` — `get_embeddings_provider()` reads `EMBEDDINGS_PROVIDER` (default
  `ollama`, model `nomic-embed-text` — requires `ollama pull nomic-embed-text` locally).
  `openai` uses `text-embedding-3-small` and requires `OPENAI_API_KEY`. Invalid/missing
  configuration fails fast at startup with a clear message, matching `_validate_env()`'s
  style in `main.py`.
- `rag/store.py` — `build_or_load()` wraps `langchain_chroma.Chroma`, persisted to
  `chroma_db/` (gitignored). Idempotent: if the collection already has data, it's loaded
  instead of re-embedded.
- `rag/retriever.py` — `retrieve(store, query, k=3)` returns the top-k chunks.
- `--rag` is opt-in and additive: `python main.py` (no flag) behavior is unchanged. If
  `docs/` has no usable content, `--rag` prints a warning and falls back to normal mode
  rather than crashing.
- `constants.RAG_SYSTEM_PROMPT_SUFFIX` is appended to (never replaces) `SYSTEM_PROMPT` in
  RAG mode; it instructs the model to cite retrieved chunks as `[source: <filename>]` and
  to say it doesn't know rather than inventing a citation when nothing relevant was
  retrieved.
- `docs/` is the RAG corpus directory — currently seeded with a placeholder
  `docs/sample-faq.md`. Replace/supplement with real documents as needed.

## Linting and formatting

Uses **Ruff** for both linting and formatting:

```bash
ruff check --fix .   # lint + auto-fix
ruff format .        # format
```

## Architecture notes

- `main.py` — CLI entry point; runs the chat loop. `build_chain(model_override, rag_enabled)` switches between the plain chain and the RAG-augmented chain (see "RAG pipeline" above), delegating the actual LCEL/RAG-bootstrap construction to `chain_builder.py` / `rag/bootstrap.py`
- `api/` — REST API entry point (see "REST API (Phase 3)" above): `api/main.py` (FastAPI app + lifespan startup), `api/auth.py` (JWT issuance/verification), `api/rate_limit.py` (shared slowapi `Limiter`), `api/models.py` (Pydantic request/response models)
- `chain_builder.py` — shared LCEL chain construction (Gemini model constructor, prompt templates, RAG citation formatting) used by both `main.py` and `api/main.py`
- `rag/bootstrap.py` — shared RAG vector-store bootstrap (`build_rag_store()`) used by both entry points; embeddings-provider failures are fatal (`sys.exit`) for the CLI's opt-in `--rag`, but `api/main.py`'s lifespan catches that and degrades to `rag_store=None` instead, since `/chat` doesn't need embeddings at all
- `constants.py` — holds `SYSTEM_PROMPT` (Polish, bracketed placeholders like `[NAZWA FIRMY]` are intentional — customize before deploying) and the RAG-specific constants (`DOCS_DIR`, `CHROMA_PERSIST_DIR`, `RAG_TOP_K`, `RAG_SYSTEM_PROMPT_SUFFIX`)
- `rag/` — RAG pipeline module (loader, chunker, embeddings, store, retriever, bootstrap); see "RAG pipeline" above
- CLI session ID is hardcoded as `"1"` — no multi-user support there. The REST API supports real per-request `session_id`s (validated against a path-safe regex before it ever reaches `session_store.py`)
- Chat history lives in memory (`history_state` in the CLI, a per-session dict in the API); it does not persist between runs except via `sessions/*.json`, written on CLI exit / after every API turn

## No tests

There is no test suite yet. When adding tests, use pytest (installed via `requirements-dev.txt`).
