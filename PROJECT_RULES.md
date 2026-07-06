# Project Rules & Conventions

A single reference for how this project (`chatbot-app-console`) is run day to day: standing
rules for working with Claude on this repo, the environment/tech stack, the contribution
workflow, and what parts of a typical project rules doc simply don't apply here yet.

This file is adapted from a sibling project's `PROJECT_RULES.md` (`llm-security-scanner`) —
sections that described that project's PyPI release pipeline, OSS/SaaS split, and public
site have been replaced with "Not applicable" notes rather than kept verbatim, since none
of it exists in this repo.

---

## 1. Standing rules for Claude

These apply to every session, every file, every commit, regardless of what the specific
task is.

- **English only** for source code, comments, commit messages, PR descriptions, and
  project docs — **with one deliberate exception**: `constants.py`'s `SYSTEM_PROMPT` is
  intentionally written in Polish (a customizable template for a Polish-speaking
  business). Don't "fix" it to English — see `CLAUDE.md`. (The `docs/etap-*.md` Polish
  course notes that used to share this exception were removed 2026-07-06 when `docs/`
  became the RAG corpus directory — see Section 8.)
- **No emojis, anywhere.** Not in code, Markdown, commit messages, PR comments. Currently
  followed — no emojis found in the repo as of 2026-07-06.
- **Konrad is the sole git author.** Never add a `Co-Authored-By: Claude` (or any
  Claude/Anthropic) trailer to commit messages. Note: 3 early commits
  (`9e321f3`, `0b88577`, `67f842f`, dated 2026-06-06 and 2026-06-25) predate this rule and
  do carry the trailer — don't rewrite that history, just don't repeat it going forward.
- **Commit approval is not push approval.** Being told to commit does not imply being
  told to push. Each `git push` needs its own explicit go-ahead, every time — this applies
  doubly when delegating to a subagent: state explicitly that it may commit but must
  never push on its own.
- **Don't run long, unattended background agents (verifier/reviewer) once context is
  above ~60%.** They can wake up later and start implementing unauthorized work. Either
  `/clear` and restart, or run verification inline instead.
- **GSD workflow for file edits.** Non-trivial repo edits should go through a GSD entry
  point (`/gsd-quick`, `/gsd-debug`, `/gsd-execute-phase`) rather than ad hoc `Edit`/`Write`
  calls, unless Konrad explicitly says to bypass it. Already in active use here — see
  `.planning/` (phases, plans, state tracking).
- **`.planning/`, `.claude/`, and `plans/` never get committed or pushed to this public
  remote.** They're gitignored (2026-07-06). `.planning/` and `.claude/` were tracked and
  pushed before that date — untracked going forward via `git rm --cached`, but not purged
  from existing git history/the `v1.0.0` tag (a deliberate choice: history rewrite +
  force-push was considered and declined as too disruptive for a public repo with an
  existing release). Keep working in these directories locally; just never `git add` them.

---

## 2. Repo layout

**Not applicable.** This is a single, personal educational repository
(`konradxmalinowski/chatbot-app-console`) — no OSS/SaaS split, no sibling private repo.

---

## 3. Environment & tech stack

| Area | Choice | Notes |
|---|---|---|
| Language | Python 3.11+ | per `CLAUDE.md` |
| LLM framework | LangChain (`langchain`, `langchain-core`) | LCEL pipeline in `main.py` |
| Model backend | Pluggable via `LLM_PROVIDER` (`llm_provider.py`) | `gemini` (default, `langchain-google-genai`, model from `GEMINI_LLM_MODEL`), `openai` (`langchain-openai`), `anthropic` (`langchain-anthropic`, added 2026-07-06), or `ollama` (`langchain-ollama`, local, no cloud key) |
| Env loading | `python-dotenv` | `.env` holds `GEMINI_API_KEY` + `GEMINI_LLM_MODEL` |
| Terminal UI | `rich` (pinned `==15.0.0`) | colored prompts/output |
| Data models | Pydantic v2 | transitive dependency via LangChain |
| YAML | PyYAML | transitive dependency, not used directly by app code |
| Package/venv manager | `pip` + stdlib `venv` | no `uv`, no `pyproject.toml` |
| Test runner | pytest | in `requirements-dev.txt`; **no test suite exists yet** |
| Lint/format | Ruff `0.11.13` | `ruff check --fix .` / `ruff format .`; no bandit (`S`) ruleset configured |

**Constraints:**
- Single hardcoded session id (`"1"`) — no multi-user support.
- Conversation history lives in memory during the session and is persisted to
  `sessions/*.json` via `session_store.py`; it does not survive without that file.
- Cloud LLM calls are the default here (opposite of `llm-security-scanner`, which is
  offline-first) — `GEMINI_API_KEY` (default provider) talks to Google's hosted API on
  every turn. `LLM_PROVIDER=ollama` (added 2026-07-06) is the one fully local/offline
  option, requiring no cloud key.

---

## 4. Contribution workflow

No `CONTRIBUTING.md` exists yet. Current practice, per `CLAUDE.md`:

```bash
ruff check --fix .
ruff format .
```

- No test suite exists yet — when tests are added, use pytest (already in
  `requirements-dev.txt`).
- No payload/schema conventions apply (that's specific to `llm-security-scanner`).

---

## 5. Release process

**Not applicable.** No package is published (no `pyproject.toml`, no PyPI target). The
app is run directly via `python main.py`; there is no versioning or release pipeline.

---

## 6. CI/CD

**Not applicable yet.** No `.github/workflows/` directory exists in this repo — no
automated lint/test on push, no dependency scanning, no security scanning configured.

---

## 7. Public site / gh-pages

**Not applicable.** No marketing page or public documentation site for this project.

---

## 8. Writing style: README & docs

Distilled from what `README.md` actually does (updated 2026-07-06 — an earlier version
of this section described an older README revision that predated badges/TOC being
added; corrected to match the current file):

- Centered `<h1>` title + a row of shield.io badges (stack/license) + a one-paragraph
  centered tagline, then a `---` rule before the Table of Contents.
- A `## Table of Contents` linking every top-level section — this repo's README does
  use one, unlike the sibling project's convention this file was originally adapted
  from.
- Feature list as bullets with **bolded lead phrase** — short benefit, not marketing copy.
- Prerequisites as a plain list (Python version, API key requirement).
- Setup as a single numbered `bash` code block with inline `#` comments per step, not
  prose describing commands.
- Config/env vars as a table (`Variable | Required | Description`), not a bulleted list.
- `---` horizontal rules between every top-level section.
- A "Project Structure" section with a fenced tree diagram and one-line inline
  comments per entry.
- `docs/` is the RAG corpus directory (Phase 2) — `.pdf`/`.txt`/`.md` files indexed by
  `--rag`, currently seeded with a placeholder `docs/sample-faq.md`. The old
  `docs/etap-*.md` Polish course-progression notes this section previously referenced
  were removed 2026-07-06 (see [[feedback_no_internal_dirs_in_repo]] — unrelated
  directories, but same cleanup session) and are no longer part of this project;
  the English-only exception in Section 1 for those files no longer applies to
  anything in the current tree.
