# Codebase Structure

**Analysis Date:** 2026-06-06

## Directory Layout

```
chatbot-app/
├── main.py              # Entry point: CLI loop + full chain construction
├── constants.py         # SYSTEM_PROMPT constant
├── requirements.txt     # Pinned Python dependencies
├── .env                 # Secret env vars (not committed) — GEMINI_API_KEY, GEMINI_LLM_MODEL
├── .env.example         # Template showing required env var names (committed)
├── .gitignore           # Excludes .env, .venv, __pycache__, .idea, .ruff_cache
├── .venv/               # Python virtual environment (not committed)
├── .ruff_cache/         # Ruff linter cache (not committed)
├── .claude/             # Claude Code configuration
│   ├── settings.json    # Claude Code project settings
│   └── skills/
│       └── setup-env/
│           └── SKILL.md # Claude skill: environment setup instructions
├── .idea/               # JetBrains IDE project files (committed)
└── .planning/           # GSD planning artefacts (generated, not runtime code)
    └── codebase/
        ├── ARCHITECTURE.md
        └── STRUCTURE.md
```

## Directory Purposes

**Root (source files):**
- Purpose: All application source code — the project has a flat source layout with no subdirectories
- Contains: `main.py`, `constants.py`, `requirements.txt`, config dotfiles
- Key files: `main.py` (entire application logic), `constants.py` (system prompt)

**`.venv/`:**
- Purpose: Isolated Python virtual environment
- Generated: Yes (by `python -m venv .venv` or equivalent)
- Committed: No (listed in `.gitignore`)

**`.claude/`:**
- Purpose: Claude Code agent configuration and skills
- Contains: `settings.json` (tool permissions/settings), `skills/setup-env/SKILL.md` (reusable env-setup instructions for Claude)
- Committed: Yes

**`.planning/codebase/`:**
- Purpose: Codebase map documents written by GSD mapper agents; consumed by `/gsd-plan-phase` and `/gsd-execute-phase`
- Generated: Yes (by Claude agents)
- Committed: Recommended (serves as living documentation)

**`.idea/`:**
- Purpose: JetBrains PyCharm project metadata
- Committed: Yes (team IDE sharing)

## Key File Locations

**Entry Point:**
- `main.py`: `if __name__ == "__main__": main()` at line 70 — run with `python main.py`

**Application Logic:**
- `main.py`: Complete application — env loading, LLM instantiation, prompt template, chain wiring, history management, CLI loop (72 lines total)

**Constants / Configuration:**
- `constants.py`: Single export `SYSTEM_PROMPT` — the Polish-language bot persona and guardrails prompt
- `.env`: Runtime secrets (`GEMINI_API_KEY`, `GEMINI_LLM_MODEL`); never commit
- `.env.example`: Documents required env var names without values

**Dependencies:**
- `requirements.txt`: Pinned full dependency tree (48 packages); used for `pip install -r requirements.txt`

**Claude Agent Config:**
- `.claude/settings.json`: Claude Code project-level settings
- `.claude/skills/setup-env/SKILL.md`: Skill definition for environment setup

## Module Boundaries and Dependencies

```
main.py
  ├── imports constants.py          (SYSTEM_PROMPT)
  ├── imports python-dotenv         (load_dotenv)
  ├── imports langchain-core        (ChatPromptTemplate, MessagesPlaceholder,
  │                                  StrOutputParser, RunnableConfig,
  │                                  InMemoryChatMessageHistory,
  │                                  RunnableWithMessageHistory)
  └── imports langchain-google-genai (ChatGoogleGenerativeAI)

constants.py
  └── no imports (pure data)
```

There are no circular dependencies. `constants.py` is a pure data module with zero imports.

## Naming Conventions

**Files:**
- `snake_case.py` for all Python source files

**Variables / functions:**
- `snake_case` throughout (`chat_with_llm`, `get_session_history`, `history_state`, `gemini_api_key`)

**Constants:**
- `UPPER_SNAKE_CASE` (`SYSTEM_PROMPT`, `GEMINI_API_KEY`)

## Where to Add New Code

**New prompt logic or persona changes:**
- Edit `constants.py` — add new constants alongside `SYSTEM_PROMPT` or replace it

**New chain components (e.g., retriever, tool):**
- Add to `main.py` between the `llm`/`parser` definitions (lines 16-28) and wire into `base_chain`

**New conversation features (e.g., multi-session support, streaming):**
- Modify `chat_with_llm()` and `conversation_chain` in `main.py:39-51`

**Splitting into multiple modules (when complexity grows):**
- Suggested layout:
  - `chain.py` — chain construction (`base_chain`, `conversation_chain`)
  - `history.py` — `get_session_history`, `history_state`
  - `cli.py` — `main()`, `chat_with_llm()`
  - `constants.py` — prompts and static config (already exists)

**New dependencies:**
- Add to `.venv` with `pip install <pkg>`, then regenerate `requirements.txt` with `pip freeze > requirements.txt`

**New environment variables:**
- Add to `.env` (local, never commit) and document the name in `.env.example`

## Special Directories

**`.venv/`:** Python virtual environment — generated, not committed, recreated via `pip install -r requirements.txt` inside a fresh venv

**`.ruff_cache/`:** Ruff linter artefacts — generated, not committed

**`.planning/`:** GSD planning documents — generated by Claude agents, should be committed as living project documentation

---

*Structure analysis: 2026-06-06*
