# Phase 1: Production Readiness & GitHub Cleanup — Context

**Gathered:** 2026-06-25
**Status:** Ready for planning
**Source:** Codebase analysis + user requirements

<domain>
## Phase Boundary

This phase takes the fully-implemented educational chatbot and makes it clean, secure, and professionally presentable on GitHub. It does NOT add features — it removes dev artifacts from tracking, fixes the `.gitignore`, hardens security posture, documents the project, and ensures the repository looks polished to any external reader.

Key problem areas identified:
- `__pycache__/constants.cpython-314.pyc` is currently tracked in git (shows as "modified" in `git status`)
- `.gitignore` is missing entries for `.idea/`, `plans/`, `.planning/`, `sessions/` (directory exists but not explicitly ignored)
- `rich` is unpinned in `requirements.txt` (`rich` without version)
- No `README.md` exists — the repository has no entry point documentation
- `plans/` directory contains internal planning docs that should not be visible externally
- `.planning/` directory contains codebase analysis that is developer-internal
- No pre-commit protection against accidentally committing `.env`
- Branch is 4 commits ahead of `origin/main` — pushing to remote needs to happen cleanly

</domain>

<decisions>
## Implementation Decisions

### D-01: Remove __pycache__ from git tracking
Remove `__pycache__/constants.cpython-314.pyc` (and any other tracked `.pyc` files) using `git rm --cached`. They are already in `.gitignore` but were committed before the rule was in place.

### D-02: Update .gitignore comprehensively
Add missing entries: `.idea/`, `plans/`, `.planning/`, `sessions/`. Keep all existing entries. Also add `*.pyo` (already there), `dist/`, `build/`, `*.egg-info/` (already there).

### D-03: Pre-commit protection for .env
Add a `.git/hooks/pre-commit` script that scans staged files and rejects any commit that attempts to add `.env`. The hook must be executable and documented in README.md setup section.

### D-04: Pin rich version in requirements.txt
Run `pip show rich` to get installed version, then replace the bare `rich` line with `rich==X.Y.Z`.

### D-05: Professional English README.md
Create `README.md` at project root. Sections: project description, features, prerequisites, installation, configuration (env vars table), usage, project structure, development setup, and license note. Tone: clear and professional for a portfolio/educational project.

### D-06: Exclude plans/ and .planning/ from git
These are developer-internal. Add to `.gitignore`. If `plans/` was ever committed, use `git rm --cached -r plans/` to remove from tracking. Note: `.planning/` will be created with ROADMAP.md etc. — those are fine as committed planning docs OR excluded; decision: keep `.planning/` tracked (it documents project evolution) but exclude `plans/` (raw internal notes).

### D-07: Verify git history for sensitive data
Run a scan of `git log -p` to confirm no API key or credential was ever committed. Document finding. This is an audit step, no code change unless leak is found.

### D-08: Update .env.example with warnings
Add inline comments and a clear `DO NOT COMMIT .env` banner to `.env.example`.

### Claude's Discretion
- Order of tasks: gitignore/tracking cleanup first, then security audit, then README last (README can reference the clean final structure)
- Whether to push to remote after cleanup: leave push to user (just get local repo clean)
- README license section: note as "MIT" or "Educational use" since no LICENSE file exists

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

- `main.py` — main application entry point (168 lines, fully implemented)
- `constants.py` — SYSTEM_PROMPT template with placeholder markers
- `session_store.py` — JSON session persistence utilities
- `.gitignore` — current exclusions (needs expansion)
- `requirements.txt` — dependencies (rich unpinned)
- `requirements-dev.txt` — dev deps (pytest, ruff)
- `.env.example` — environment variable template (needs warning banner)
- `.planning/codebase/CONCERNS.md` — full security and quality audit
- `.planning/codebase/ARCHITECTURE.md` — system architecture overview
- `plans/2026-06-06-feature-expansion.md` — untracked internal plan (should stay untracked)
- `docs/` — Polish-language stage documentation (KEEP, part of the project)

</canonical_refs>

<specifics>
## Specific Notes

### Current git status
- Modified (tracked): `__pycache__/constants.cpython-314.pyc`
- Untracked: `plans/2026-06-06-feature-expansion.md`
- Branch is 4 commits ahead of origin/main

### requirements.txt rich entry
Current: `rich` (no version)
Target: `rich==13.X.Y` (exact installed version from `pip show rich`)

### .env.example current state
```
GEMINI_API_KEY=your_google_gemini_api_key_here
GEMINI_LLM_MODEL=gemini-2.5-flash
```
Needs: header comment block warning against committing the actual `.env` file.

### README.md must cover
1. What is this project (educational chatbot)
2. Features (model selection, history persistence, rich output)
3. Prerequisites (Python 3.11+, Google AI Studio key)
4. Setup (clone, venv, install deps, copy .env)
5. Configuration table (GEMINI_API_KEY, GEMINI_LLM_MODEL)
6. Usage (`python main.py`, `python main.py --model <model>`, exit with empty input)
7. Project structure tree
8. Development (ruff lint/format commands)
9. Note on SYSTEM_PROMPT customization

</specifics>

<deferred>
## Deferred Ideas

- Adding tests (separate phase)
- Refactoring main.py into modules (llm.py, history.py, cli.py) — future phase
- Multi-session support / UUID session IDs — future phase
- Web interface / API layer — out of scope for educational CLI tool
- pyproject.toml migration — nice to have, not blocking production-readiness

</deferred>

---

*Phase: 01-production-readiness-github-cleanup*
*Context gathered: 2026-06-25*
