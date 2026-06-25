# Requirements — chatbot-app Production Readiness

**Version:** 1.0
**Date:** 2026-06-25

---

## Phase 1: Production Readiness & GitHub Cleanup

### REQ-01: Remove cached bytecode from git tracking
**Priority:** High  
The `__pycache__/` directory and `.pyc` files are currently tracked in git (modified state visible in `git status`). They must be removed from tracking via `git rm --cached` and stay excluded via `.gitignore`.

**Acceptance:** `git ls-files __pycache__` returns empty; `git status` shows no pyc files.

---

### REQ-02: Update `.gitignore` comprehensively
**Priority:** High  
Current `.gitignore` does not exclude: `.idea/` (IDE config), `plans/` (internal planning docs), `.planning/` (GSD internal), `sessions/` (runtime conversation data).

**Acceptance:** All above directories are listed in `.gitignore`; `git status` confirms none are tracked.

---

### REQ-03: Add safeguard against `.env` commits
**Priority:** High  
`.env` must never be committed. Add a pre-commit hook or documented git alias that rejects any commit attempting to add `.env`. Update `.env.example` with a clear warning comment.

**Acceptance:** Attempting `git add .env` then commit is blocked or clearly warned; `.env.example` has a `DO NOT COMMIT` warning.

---

### REQ-04: Pin `rich` version in `requirements.txt`
**Priority:** Medium  
`rich` is listed without a version pin (`rich` only). For reproducible installs, it must be pinned to the current installed version.

**Acceptance:** `requirements.txt` contains `rich==X.Y.Z` where X.Y.Z is the installed version.

---

### REQ-05: Create professional README.md in English
**Priority:** High  
No README.md exists. A professional README is the entry point for any GitHub visitor.

**Acceptance:** `README.md` exists at project root covering: project description, features, prerequisites, setup, usage, environment variables, project structure, and contributing/license notes.

---

### REQ-06: Exclude internal planning/development documents
**Priority:** Medium  
`plans/` directory contains internal planning documents (not useful to external users). These should either be removed from git history or kept only locally via `.gitignore`.

**Acceptance:** `plans/` and `.planning/` do not appear in `git ls-files`; `.gitignore` excludes them.

---

### REQ-07: Verify no sensitive data in git history
**Priority:** High  
Audit git history to confirm no API keys, passwords, or `.env` content was ever committed.

**Acceptance:** `git log -p | grep -i "api_key\|GEMINI_API_KEY=" | grep -v "example\|your_"` returns empty.

---

### REQ-08: Ensure `.env.example` is complete and accurate
**Priority:** Medium  
`.env.example` should reflect all required environment variables with clear descriptions.

**Acceptance:** `.env.example` documents every variable used in `main.py` and `constants.py` with placeholder values and inline comments explaining each.
