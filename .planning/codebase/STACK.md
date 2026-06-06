# Technology Stack

**Analysis Date:** 2026-06-06

## Languages

**Primary:**
- Python 3.x (system: 3.14.4) - All application logic

## Runtime

**Environment:**
- Python (CPython)

**Package Manager:**
- pip with `requirements.txt`
- Lockfile: `requirements.txt` (pinned versions)
- Virtual environment: `.venv/`

## Frameworks

**Core:**
- `langchain==1.3.3` - LLM orchestration, chain composition
- `langchain-core==1.4.0` - Prompts, output parsers, runnables, chat history
- `langchain-google-genai==4.2.4` - Google Gemini integration for LangChain
- `langgraph==1.2.4` - (installed, not yet used in `main.py`)

**Build/Dev:**
- `ruff==0.15.16` - Linting and formatting

## Key Dependencies

**Critical:**
- `langchain-google-genai==4.2.4` - Wraps Google Gemini API via LangChain interface
- `google-genai==2.7.0` - Underlying Google GenAI SDK
- `google-auth==2.53.0` - Google authentication library
- `python-dotenv==1.2.2` - Loads `.env` file into `os.environ`
- `pydantic==2.13.4` - Data validation used by LangChain internals
- `langsmith==0.8.8` - LangChain tracing/observability (installed, passive)

**Infrastructure:**
- `httpx==0.28.1` - Async HTTP client used by Google GenAI SDK
- `tenacity==9.1.4` - Retry logic for LLM calls
- `websockets==15.0.1` - WebSocket support (available, not directly used in CLI)

## Configuration

**Environment:**
- All secrets and model config loaded via `python-dotenv` from `.env` at startup (`load_dotenv(verbose=True)` in `main.py`)
- Template provided at `.env.example`
- Required variables:
  - `GEMINI_API_KEY` - Google Gemini API key
  - `GEMINI_LLM_MODEL` - Model name (default: `gemini-2.5-flash`)

**Build:**
- No build step; run directly with `python main.py`
- `ruff` available for linting/formatting (`ruff==0.15.16`)

## Application Structure

**Entry point:** `main.py`
**Constants:** `constants.py` (holds `SYSTEM_PROMPT`)
**Dependency list:** `requirements.txt`

## Platform Requirements

**Development:**
- Python 3.x
- `.env` file with `GEMINI_API_KEY` and `GEMINI_LLM_MODEL`

**Production:**
- CLI application; no web server or containerization detected

---

*Stack analysis: 2026-06-06*
