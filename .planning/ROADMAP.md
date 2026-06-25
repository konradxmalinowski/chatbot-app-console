# Roadmap — chatbot-app

**Project:** Educational CLI Chatbot (LangChain + Google Gemini)
**Created:** 2026-06-25
**Status:** Active

---

## Milestone 1: Production & GitHub Readiness

> Goal: Take the fully-featured educational chatbot to a clean, professional, production-ready state suitable for public GitHub.

---

### Phase 1: Production Readiness & GitHub Cleanup

**Goal:** Make the chatbot repository clean, secure, and professional for public consumption on GitHub. This includes removing development/internal files from tracking, hardening security, improving the `.gitignore`, creating a professional English README, and ensuring the codebase meets production quality standards.

**Status:** Pending

**Plans:** 3 plans

**Deliverables:**
- Updated `.gitignore` covering all dev/internal artifacts
- `__pycache__` and `.pyc` files removed from git tracking
- `plans/` and `.planning/` directories excluded from public repo
- Pre-commit hook or `.env` guard preventing accidental key commits
- Pinned `rich` version in `requirements.txt`
- Professional `README.md` in English
- `sessions/` directory excluded and `.gitkeep` if needed
- Clean `git log` with no dev-only artifacts tracked

**Requirements:**
- REQ-01: Remove all `__pycache__` and `.pyc` files from git tracking
- REQ-02: Update `.gitignore` to exclude dev/IDE/internal files (`.idea/`, `plans/`, `.planning/`, `sessions/`)
- REQ-03: Add safeguard against committing `.env` (pre-commit hook or documentation)
- REQ-04: Pin `rich` to an exact version in `requirements.txt`
- REQ-05: Create professional `README.md` in English with setup instructions, usage, configuration, and project structure
- REQ-06: Remove or exclude internal `plans/` planning documents from git history/tracking
- REQ-07: Verify no sensitive data exists in git history
- REQ-08: Ensure `.env.example` is complete and accurate

**Depends on:** (none)

Plans:
- [ ] 01-01-PLAN.md — Git tracking cleanup: untrack __pycache__ and plans/, expand .gitignore (REQ-01, REQ-02, REQ-06)
- [ ] 01-02-PLAN.md — Security hardening: pin rich, pre-commit hook, .env.example warning, history audit (REQ-03, REQ-04, REQ-07, REQ-08)
- [ ] 01-03-PLAN.md — Professional README.md in English (REQ-05)
