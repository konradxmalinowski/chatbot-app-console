# Codebase Concerns

**Analysis Date:** 2026-06-06

## Security Concerns

**API key loaded without validation:**
- Issue: `os.environ.get("GEMINI_API_KEY")` returns `None` silently if the key is missing; `None` is passed directly to `ChatGoogleGenerativeAI`, which will raise an uninformative error at runtime rather than a clear startup check.
- Files: `main.py` (line 13, 16)
- Severity: **medium**
- Effort to fix: **low**
- Suggested fix: Add a startup guard — `if not gemini_api_key: raise EnvironmentError("GEMINI_API_KEY is not set")`.

**No input sanitization or length limiting:**
- Issue: Raw user input from `input()` is passed directly to the LLM with no length cap, no stripping of control characters, and no prompt-injection mitigation beyond the guardrails text in `SYSTEM_PROMPT`.
- Files: `main.py` (line 59, 65)
- Severity: **medium**
- Effort to fix: **low**
- Suggested fix: Add `user_prompt = user_prompt.strip()[:4000]` and consider a basic injection-keyword filter for production use.

**`.env` exists in the repo working tree:**
- Issue: `.env` is properly listed in `.gitignore` and has never been committed, so no key is in git history. However, the file is present on disk alongside the repo, which is a risk if the directory is shared, archived, or accidentally force-added.
- Files: `.env`, `.gitignore`
- Severity: **low** (no leak yet)
- Effort to fix: **low**
- Suggested fix: Document in `.env.example` that `.env` must never be committed; optionally add a pre-commit hook that rejects `.env` additions.

---

## Reliability Concerns

**No retry logic for API failures:**
- Issue: A single `conversation_chain.invoke()` call is wrapped in a bare `except Exception` that prints the error and continues. Transient network errors or rate-limit responses from the Gemini API are not retried.
- Files: `main.py` (lines 64-67)
- Severity: **medium**
- Effort to fix: **low**
- Suggested fix: Use `tenacity` (already in `requirements.txt`) to add `@retry(stop=stop_after_attempt(3), wait=wait_exponential())` around `chat_with_llm`.

**Hardcoded session ID:**
- Issue: Every invocation uses `session_id: "1"` regardless of who is running the process. If multiple processes share state (or the code is refactored into a server), all conversations would collide.
- Files: `main.py` (line 48)
- Severity: **low** (single-user CLI today)
- Effort to fix: **low**
- Suggested fix: Generate a UUID session ID per process start — `session_id = str(uuid.uuid4())`.

**Silent model name fallback:**
- Issue: `os.environ.get("GEMINI_LLM_MODEL")` returns `None` if unset; `ChatGoogleGenerativeAI(model=None)` may silently use a default or raise a cryptic error.
- Files: `main.py` (line 14, 16)
- Severity: **low**
- Effort to fix: **low**
- Suggested fix: Provide an explicit default — `gemini_llm_model = os.environ.get("GEMINI_LLM_MODEL", "gemini-2.5-flash")`.

---

## Scalability / Architectural Limitations

**In-memory chat history lost on restart:**
- Issue: `history_state` is a plain module-level dict backed by `InMemoryChatMessageHistory`. Every process restart wipes all conversation history with no warning to the user.
- Files: `main.py` (line 30, 33-36)
- Severity: **medium**
- Effort to fix: **medium**
- Suggested fix: Replace `InMemoryChatMessageHistory` with a file-backed or SQLite-backed store using LangChain's `SQLChatMessageHistory`.

**No persistence layer:**
- Issue: There is no database, file store, or cache. Conversations, settings, and session state all live in process memory only.
- Files: `main.py`
- Severity: **low** (educational project scope)
- Effort to fix: **high**
- Suggested fix: For production evolution, introduce a lightweight SQLite persistence layer via `langchain-community` `SQLChatMessageHistory`.

**CLI-only interface:**
- Issue: All I/O is via `input()`/`print()`. Migrating to a web or API interface would require significant refactoring because the chat logic is entangled with the CLI loop.
- Files: `main.py` (lines 55-71)
- Severity: **low** (intentional for learning project)
- Effort to fix: **medium**
- Suggested fix: Extract `chat_with_llm` into a pure function that takes and returns strings; keep CLI loop as a thin wrapper so the core is interface-agnostic.

---

## Maintainability Concerns

**`SYSTEM_PROMPT` contains unfilled placeholder text:**
- Issue: The prompt contains bracketed placeholders such as `[NAZWA FIRMY / PROJEKTU]`, `[GŁÓWNY CEL BOTA]`, and `[EMAIL/LINK]`. These are sent verbatim to the LLM on every request, producing confusing or generic responses.
- Files: `constants.py` (lines 3-4, 14)
- Severity: **high** (breaks intended bot behavior)
- Effort to fix: **low**
- Suggested fix: Replace every `[...]` placeholder with real values before using the project for anything beyond initial exploration.

**No tests:**
- Issue: There are zero test files. No unit tests for `get_session_history`, `chat_with_llm`, or prompt construction. No integration tests.
- Files: entire project
- Severity: **medium**
- Effort to fix: **medium**
- Suggested fix: Add `pytest` and at least one unit test for `get_session_history` and one mock-based test for `chat_with_llm` to establish a baseline.

**All logic in a single file:**
- Issue: `main.py` contains LLM initialization, prompt construction, history management, the chat function, and the CLI entry point — 71 lines today but will become hard to navigate as features are added.
- Files: `main.py`
- Severity: **low** (manageable at current size)
- Effort to fix: **low**
- Suggested fix: Split into `llm.py` (model/chain setup), `history.py` (session management), and `cli.py` (entry point) when the file exceeds ~150 lines.

**No type annotations on public functions:**
- Issue: `get_session_history` and `chat_with_llm` lack return type annotations. `chat_with_llm` prints output rather than returning it, making it untestable without capturing stdout.
- Files: `main.py` (lines 33, 47)
- Severity: **low**
- Effort to fix: **low**
- Suggested fix: Add return type hints and refactor `chat_with_llm` to `return response` instead of `print(...)`.

---

## Dependency Concerns

**Very new LangChain versions — potential instability:**
- Issue: `langchain==1.3.3` and `langchain-core==1.4.0` are very recent releases. The LangChain ecosystem has a history of breaking API changes between minor versions. `langchain-google-genai==4.2.4` is also a major-version bump from commonly documented examples.
- Files: `requirements.txt` (lines 17-18)
- Severity: **medium**
- Effort to fix: **low**
- Suggested fix: Pin dependencies in `requirements.txt` to exact versions (already done via `pip freeze`) and document the tested Python version in a `.python-version` file or `pyproject.toml`.

**`requirements.txt` is a full `pip freeze` dump, not curated:**
- Issue: 47 packages are pinned, including transitive dependencies like `xxhash`, `zstandard`, `ormsgpack`, and `orjson` that the application code does not import directly. This creates unnecessary upgrade noise and makes it hard to identify the actual direct dependencies.
- Files: `requirements.txt`
- Severity: **low**
- Effort to fix: **low**
- Suggested fix: Maintain a slim `requirements.in` with direct dependencies only and generate `requirements.txt` with `pip-compile` (pip-tools).

**`ruff` listed as a runtime dependency:**
- Issue: `ruff==0.15.16` appears in `requirements.txt`, meaning it is installed into the application virtual environment. Linting tools should be dev-only dependencies, not shipped with production code.
- Files: `requirements.txt` (line 38)
- Severity: **low**
- Effort to fix: **low**
- Suggested fix: Move `ruff` to a separate `requirements-dev.txt` or a `[tool.ruff]` entry in `pyproject.toml` with dev dependency management.

---

*Concerns audit: 2026-06-06*
