---
name: setup-env
description: First-time project setup — creates .env, activates venv, and installs dependencies. Use when onboarding to this project or after cloning.
disable-model-invocation: true
---

Guide the user through setting up the chatbot-app environment from scratch:

1. **Create the virtual environment** (if `.venv` doesn't exist):
   ```bash
   python -m venv .venv
   ```

2. **Activate the virtual environment**:
   - macOS/Linux: `source .venv/bin/activate`
   - Windows: `.venv\Scripts\activate`

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Create the `.env` file** (if it doesn't exist):
   ```bash
   cp .env.example .env
   ```
   Then open `.env` and fill in:
   - `GEMINI_API_KEY` — get from [Google AI Studio](https://aistudio.google.com/apikey)
   - `GEMINI_LLM_MODEL` — use `gemini-2.5-flash` (already set in `.env.example`)

5. **Run the chatbot** to verify everything works:
   ```bash
   python main.py
   ```
   Type any message and confirm you get a response. Submit an empty line to exit.

If any step fails, check the error and report it — common issues are Python version mismatch (requires 3.10+) or an invalid API key.
