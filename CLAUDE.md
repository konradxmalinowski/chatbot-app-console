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
only needed when running with `--rag`:

| Variable | Description |
|---|---|
| `GEMINI_API_KEY` | Google AI Studio API key |
| `GEMINI_LLM_MODEL` | Model name, e.g. `gemini-2.5-flash` |
| `EMBEDDINGS_PROVIDER` | `ollama` (default) or `openai` — embeddings backend for `--rag` |
| `OPENAI_API_KEY` | Only required when `EMBEDDINGS_PROVIDER=openai` |

## Run

```bash
python main.py         # normal mode
python main.py --rag   # RAG mode — retrieves context from docs/, cites sources
```

Exit the chat by submitting an empty prompt.

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

- `main.py` — entry point; builds the LangChain chain and runs the chat loop. `build_chain(model_override, rag_enabled)` switches between the plain chain and the RAG-augmented chain (see "RAG pipeline" above)
- `constants.py` — holds `SYSTEM_PROMPT` (Polish, bracketed placeholders like `[NAZWA FIRMY]` are intentional — customize before deploying) and the RAG-specific constants (`DOCS_DIR`, `CHROMA_PERSIST_DIR`, `RAG_TOP_K`, `RAG_SYSTEM_PROMPT_SUFFIX`)
- `rag/` — RAG pipeline module (loader, chunker, embeddings, store, retriever); see "RAG pipeline" above
- Session ID is hardcoded as `"1"` — there is no multi-user support
- Chat history lives in `history_state` dict in memory; it does not persist between runs (except via `sessions/*.json`, written on exit)

## No tests

There is no test suite yet. When adding tests, use pytest (installed via `requirements-dev.txt`).
