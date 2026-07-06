# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

See `PROJECT_RULES.md` for the standing collaboration rules (git authorship, commit vs.
push approval, English-only exceptions, GSD workflow) and a stack/process comparison
against this repo — read it at the start of every session, same as this file.

## Project

Educational CLI chatbot using LangChain, with a pluggable chat model backend (Gemini by
default; OpenAI, Anthropic, or local Ollama also supported — see "LLM provider selection"
below). Single-session, in-memory conversation history — history is lost on restart.
Optional RAG mode (`--rag`) retrieves context from local documents in `docs/` via a
ChromaDB vector store — see "RAG pipeline" below.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
pip install -r requirements-dev.txt   # dev tools: ruff, pytest
cp .env.example .env            # then fill in GEMINI_API_KEY (or another provider's key)
```

## Environment variables

`GEMINI_API_KEY`/`GEMINI_LLM_MODEL` are only required while `LLM_PROVIDER` is unset or
`gemini` (the default) — each provider validates only its own requirements at startup,
via `llm_provider.get_llm()` (see "LLM provider selection" below). The RAG variables are
only needed when running with `--rag` (or the REST API, which builds the RAG store at
startup regardless of a flag). The `API_SECRET` / `JWT_SECRET_KEY` / `CORS_ORIGINS`
variables are only needed to run the REST API (see below):

| Variable | Description |
|---|---|
| `LLM_PROVIDER` | `gemini` (default), `openai`, `anthropic`, or `ollama` — chat model backend |
| `GEMINI_API_KEY` | Required when `LLM_PROVIDER=gemini` — Google AI Studio API key |
| `GEMINI_LLM_MODEL` | Required when `LLM_PROVIDER=gemini`, unless `--model` is passed |
| `OPENAI_API_KEY` | Required when `LLM_PROVIDER=openai` or `EMBEDDINGS_PROVIDER=openai` — same key covers both |
| `ANTHROPIC_API_KEY` | Required when `LLM_PROVIDER=anthropic` |
| `EMBEDDINGS_PROVIDER` | `ollama` (default) or `openai` — embeddings backend for `--rag` (unrelated to `LLM_PROVIDER`) |
| `API_SECRET` | REST API only — pre-shared secret exchanged for a JWT via `POST /auth/token` |
| `JWT_SECRET_KEY` | REST API only — signs issued JWTs (HS256); must differ from `API_SECRET` |
| `CORS_ORIGINS` | REST API only — comma-separated allowed origins; unset/empty = none allowed (fail closed) |

## LLM provider selection

`llm_provider.py` mirrors `rag/embeddings.py`'s `EMBEDDINGS_PROVIDER` pattern for chat
models (a structurally similar but functionally separate concern — the two are not
interchangeable or merged):

- `get_llm(model_override=None)` reads `LLM_PROVIDER` (default `gemini`, preserving
  original single-provider behavior when unset) and dispatches to one
  `_get_<provider>_llm()` per provider, each validating only that provider's own
  requirements and failing fast (`console.print` + `sys.exit(1)`) with an actionable
  message if unmet.
- `gemini` — `ChatGoogleGenerativeAI`; the only provider with no hardcoded default
  model — requires `GEMINI_API_KEY` + (`--model` or `GEMINI_LLM_MODEL`).
- `openai` — `ChatOpenAI`; requires `OPENAI_API_KEY` (reused from RAG embeddings, not a
  separate key); default model `gpt-4o-mini`.
- `anthropic` — `ChatAnthropic` (new dependency: `langchain-anthropic`); requires
  `ANTHROPIC_API_KEY`; default model `claude-3-5-haiku-latest`.
- `ollama` — `ChatOllama`; no cloud key, but checks Ollama is reachable and the model
  is pulled (mirrors `rag/embeddings.py`'s `_get_ollama_embeddings()` exactly), failing
  fast with the exact `ollama pull <model>` fix if not; default model `llama3.2:3b`.
  At **invocation** time (not just this startup check), `ollama`/`langchain_ollama`
  raise builtin `ConnectionError` on an unreachable server and `ollama.ResponseError`
  on other API errors — both are caught explicitly in `main.py`/`api/main.py` alongside
  `openai.OpenAIError`/`anthropic.AnthropicError`, next to the pre-existing
  Gemini-specific catches, before the final generic `Exception` fallback.
- `--model` overrides the model name for whichever provider is active (previously
  Gemini-only). `--llm-provider` (CLI flag) overrides `LLM_PROVIDER` for the process.
- `chain_builder.py` no longer constructs the chat model directly — `build_llm()` was
  removed; `llm_provider.get_llm()` is the single code path for building it, called
  from `main.py`'s `build_chain()`/`build_agent_graph()` and `api/main.py`'s
  `lifespan()`.

## Run

```bash
python src/main.py                          # normal mode (Gemini by default)
python src/main.py --rag                    # RAG mode — retrieves context from docs/, cites sources
python src/main.py --agent                  # agent mode — tools with human-in-the-loop approval
python src/main.py --llm-provider ollama    # switch chat model provider at runtime
```

Exit the chat by submitting an empty prompt. `--agent` and `--rag` cannot be combined.

## REST API (Phase 3)

A FastAPI app in `api/` exposes the same chat/RAG functionality over HTTP, as an
additional entry point alongside the CLI (the CLI is unaffected by it):

```bash
uvicorn api.main:app --reload --app-dir src
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

## LangGraph agent (Phase 4)

`--agent` (CLI) and `POST /agent` + `POST /agent/{pending_id}/approve` + `POST
/agent/{pending_id}/reject` (API) run a LangGraph `StateGraph` with three tools —
`web_search` (DuckDuckGo, no API key), `calculator` (AST-restricted evaluator, no
`eval`/`exec`), `read_doc` (path-confined to `docs/`) — behind a **mandatory**
human-in-the-loop gate: no tool ever executes without explicit approval, in either
mode.

- `agent/graph.py`'s `AgentGraph` compiles the graph with a `MemorySaver`
  checkpointer and `interrupt_before=["tools"]`: execution pauses right before a
  tool call would run. `session_id` doubles as the LangGraph `thread_id` (same
  validated field as Phase 2/3, no new ID scheme).
- **CLI**: synchronous — when the graph pauses, it prints every proposed tool call
  (there can be more than one in a single turn — parallel tool calling) and prompts
  once with `[y/N]`; approval/rejection applies to the whole batch.
- **API**: two-step, by explicit design choice (an auto-approve-via-header
  alternative was considered and rejected as weakening the safety gate). `POST
  /agent` runs until it finishes or pauses; a pause returns `{"status":
  "pending_approval", "pending_id": <session_id>, "pending_tool_calls": [{"tool":
  str, "args": dict}, ...]}` — **every** pending call, not just one, so an approver
  can't unknowingly approve a call they never saw. `POST
  /agent/{pending_id}/approve` executes the batch and continues (executed calls
  logged to `logs/agent.jsonl` with a real result); `POST
  /agent/{pending_id}/reject` declines the whole batch instead — the agent must
  acknowledge it can't complete that step (enforced via
  `AGENT_SYSTEM_PROMPT_SUFFIX`), not silently retry. Neither route has a per-route
  `@limiter.limit(...)` decorator, for the same reason `/chat`/`/chat/rag` don't
  (see above) — `default_limits` covers them via the middleware.
- `calculator`'s AST evaluator bounds `ast.Pow`'s cost before computing (not just
  the grammar it accepts): Python ints are arbitrary-precision, so an
  innocuous-looking `9**9**9` would otherwise pin a CPU core computing a
  ~369-million-digit number. `_check_pow_cost` estimates the result's bit-length
  via `log2` and rejects anything over `_MAX_POW_RESULT_BITS` before evaluating.
- Every tool-call attempt (approved-and-executed, or rejected) is logged as one
  JSON line to `logs/agent.jsonl` (gitignored, like `sessions/`/`chroma_db/`):
  `{"timestamp", "session_id", "tool", "args", "result", "declined",
  "approved_by"}`. Tool results are truncated to 500 chars in the log only — the
  LLM/caller still receives the full result.
- Known, accepted limitations (not bugs): `MemorySaver` is in-memory, so a pending
  approval is lost if the API process restarts before `/approve`/`/reject` is
  called. `verify_token` authenticates one shared service secret, not a per-user
  identity, so any valid token holder can approve/reject any session's pending
  call — identical to the pre-existing `/chat` `session_id` trust model, not new
  to this phase.

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
- `--rag` is opt-in and additive: `python src/main.py` (no flag) behavior is unchanged. If
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

All application code lives under `src/` (moved there 2026-07-06; previously flat at
repo root). No `pyproject.toml`/packaging was introduced — internal imports (`from
constants import ...`, `from rag.loader import ...`, etc.) are unchanged, since
Python adds the running script's own directory to its module search path
automatically (`python src/main.py`) and `uvicorn ... --app-dir src` does the
equivalent for the API. Paths below are relative to `src/` unless noted otherwise.

- `main.py` — CLI entry point; runs the chat loop. `build_chain(model_override, rag_enabled)` switches between the plain chain and the RAG-augmented chain (see "RAG pipeline" above), delegating the actual LCEL/RAG-bootstrap construction to `chain_builder.py` / `rag/bootstrap.py`. `--agent` runs a separate loop (`run_agent_turn`) driving `agent.graph.AgentGraph` instead
- `api/` — REST API entry point (see "REST API (Phase 3)" and "LangGraph agent (Phase 4)" above): `api/main.py` (FastAPI app + lifespan startup), `api/auth.py` (JWT issuance/verification), `api/rate_limit.py` (shared slowapi `Limiter`), `api/models.py` (Pydantic request/response models)
- `agent/` — LangGraph agent module: `agent/tools.py` (`web_search`, `calculator`, `read_doc`), `agent/graph.py` (`AgentGraph` — graph construction, interrupt/checkpoint-based approval, shared by `main.py` and `api/main.py`); see "LangGraph agent (Phase 4)" above
- `chain_builder.py` — shared LCEL chain construction (prompt templates, RAG citation formatting) used by both `main.py` and `api/main.py`; the chat model itself is built by `llm_provider.get_llm()` (see "LLM provider selection" above), not by this module
- `llm_provider.py` — `LLM_PROVIDER` dispatch (gemini/openai/anthropic/ollama); see "LLM provider selection" above
- `rag/bootstrap.py` — shared RAG vector-store bootstrap (`build_rag_store()`) used by both entry points; embeddings-provider failures are fatal (`sys.exit`) for the CLI's opt-in `--rag`, but `api/main.py`'s lifespan catches that and degrades to `rag_store=None` instead, since `/chat` doesn't need embeddings at all
- `constants.py` — holds `SYSTEM_PROMPT` (Polish, bracketed placeholders like `[NAZWA FIRMY]` are intentional — customize before deploying) and the RAG-specific constants (`DOCS_DIR`, `CHROMA_PERSIST_DIR`, `RAG_TOP_K`, `RAG_SYSTEM_PROMPT_SUFFIX`)
- `rag/` — RAG pipeline module (loader, chunker, embeddings, store, retriever, bootstrap); see "RAG pipeline" above
- CLI session ID is hardcoded as `"1"` — no multi-user support there. The REST API supports real per-request `session_id`s (validated against a path-safe regex before it ever reaches `session_store.py`)
- Chat history lives in memory (`history_state` in the CLI, a per-session dict in the API); it does not persist between runs except via `sessions/*.json`, written on CLI exit / after every API turn

## No tests

There is no test suite yet. When adding tests, use pytest (installed via `requirements-dev.txt`).
