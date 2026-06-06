# External Integrations

**Analysis Date:** 2026-06-06

## APIs & External Services

**Generative AI:**
- Google Gemini - LLM inference for all chatbot responses
  - SDK/Client: `langchain-google-genai==4.2.4` (LangChain wrapper) + `google-genai==2.7.0` (underlying SDK)
  - Auth: `GEMINI_API_KEY` environment variable, passed directly to `ChatGoogleGenerativeAI(google_api_key=gemini_api_key)` in `main.py`
  - Model selected at runtime via `GEMINI_LLM_MODEL` env var (default configured as `gemini-2.5-flash` in `.env.example`)

## Data Storage

**Databases:**
- None — no external database

**In-memory state:**
- `InMemoryChatMessageHistory` (from `langchain-core`) stores conversation history per `session_id` in the `history_state` dict in `main.py`
- State is lost when the process exits

**File Storage:**
- Not applicable

**Caching:**
- None detected

## Authentication & Identity

**Auth Provider:**
- Google API key authentication only
- Key sourced from `GEMINI_API_KEY` env var, loaded via `python-dotenv`

## Monitoring & Observability

**Error Tracking:**
- None — errors caught with bare `except Exception as e` in `main.py`, printed to stdout

**LangSmith (Tracing):**
- `langsmith==0.8.8` is installed as a transitive dependency of LangChain
- Not explicitly configured; will activate if `LANGCHAIN_TRACING_V2` and `LANGCHAIN_API_KEY` env vars are set

**Logs:**
- `print()` statements only; no structured logging

## CI/CD & Deployment

**Hosting:**
- Not applicable — local CLI application

**CI Pipeline:**
- None detected

## Environment Configuration

**Required env vars:**
- `GEMINI_API_KEY` - Google Gemini API key (required for LLM calls)
- `GEMINI_LLM_MODEL` - Model identifier string, e.g. `gemini-2.5-flash`

**Secrets location:**
- `.env` file (git-ignored); template at `.env.example`

## Webhooks & Callbacks

**Incoming:**
- None

**Outgoing:**
- None — all communication is request/response via Google Gemini REST API through the SDK

## Rate Limits & Cost Notes

- Model `gemini-2.5-flash` is Google's cost-efficient tier; no explicit rate-limit handling implemented in application code
- `tenacity==9.1.4` is available (installed as LangChain dependency) and may handle retries at the SDK level automatically

---

*Integration audit: 2026-06-06*
