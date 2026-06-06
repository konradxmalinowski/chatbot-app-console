<!-- refreshed: 2026-06-06 -->
# Architecture

**Analysis Date:** 2026-06-06

## System Overview

```text
┌─────────────────────────────────────────────────────────────┐
│                        CLI Entry Point                       │
│                          `main.py`                           │
│              main() → input loop → chat_with_llm()           │
└───────────────────────────┬─────────────────────────────────┘
                            │ user_prompt (str)
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                  conversation_chain                          │
│          RunnableWithMessageHistory  (`main.py:39`)          │
│   - injects chat_history from InMemoryChatMessageHistory     │
│   - wraps base_chain                                         │
└──────────┬──────────────────────────────────────────────────┘
           │ {"input": str, "chat_history": [messages]}
           ▼
┌─────────────────────────────────────────────────────────────┐
│                        base_chain                            │
│   ChatPromptTemplate | ChatGoogleGenerativeAI | StrOutputParser
│   (`main.py:28`)                                             │
│                                                              │
│  [SYSTEM_PROMPT]  ← `constants.py`                          │
│  [chat_history]   ← MessagesPlaceholder                     │
│  [human input]    ← "{input}"                               │
└──────────┬──────────────────────────────────────────────────┘
           │ formatted prompt
           ▼
┌─────────────────────────────────────────────────────────────┐
│             Google Gemini API (gemini-2.5-flash)             │
│             via langchain-google-genai                        │
└──────────┬──────────────────────────────────────────────────┘
           │ raw LLM response
           ▼
┌─────────────────────────────────────────────────────────────┐
│              StrOutputParser → plain string                  │
│              printed to stdout: `print(f"AI: {response}")`  │
└─────────────────────────────────────────────────────────────┘
```

## Component Responsibilities

| Component | Responsibility | File |
|-----------|----------------|------|
| `main()` | CLI loop: reads stdin, dispatches to `chat_with_llm`, handles empty-input exit | `main.py:55` |
| `chat_with_llm()` | Invokes `conversation_chain` with hardcoded session_id `"1"`, prints response | `main.py:47` |
| `conversation_chain` | `RunnableWithMessageHistory` wrapper; injects and persists per-session history | `main.py:39` |
| `base_chain` | LangChain LCEL pipeline: prompt → LLM → parser | `main.py:28` |
| `chat_template_prompt` | `ChatPromptTemplate` with system prompt, history placeholder, and human turn | `main.py:20` |
| `llm` | `ChatGoogleGenerativeAI` instance; model name and API key loaded from env | `main.py:16` |
| `parser` | `StrOutputParser`; converts `AIMessage` to plain string | `main.py:18` |
| `get_session_history()` | Factory: lazily creates `InMemoryChatMessageHistory` keyed by `session_id` | `main.py:33` |
| `history_state` | Module-level dict mapping session_id → `InMemoryChatMessageHistory` | `main.py:30` |
| `SYSTEM_PROMPT` | Polish-language system prompt defining bot persona, constraints, output format | `constants.py:1` |

## Pattern Overview

**Overall:** Linear pipeline (LCEL chain) with stateful message history wrapper.

**Key Characteristics:**
- LangChain Expression Language (LCEL) `|` operator wires prompt → LLM → parser into `base_chain`
- `RunnableWithMessageHistory` decorates `base_chain`, transparently reading/writing history before/after each invoke
- All state lives in a module-level Python dict (`history_state`); no external storage
- Single-session design: `session_id` is always `"1"` (hardcoded in `chat_with_llm`)

## Layers

**CLI Layer:**
- Purpose: User I/O — reads from stdin, prints to stdout
- Location: `main.py:55-71`
- Contains: `main()` loop and basic exception handling
- Depends on: `chat_with_llm()`
- Used by: Python interpreter (`__main__` guard at line 70)

**Chain Orchestration Layer:**
- Purpose: Manages conversation state and routes requests through the LLM chain
- Location: `main.py:30-51`
- Contains: `history_state`, `get_session_history()`, `conversation_chain`, `chat_with_llm()`
- Depends on: `base_chain`, LangChain history primitives
- Used by: CLI layer

**Chain Definition Layer:**
- Purpose: Declares the prompt structure and LLM pipeline
- Location: `main.py:16-28`
- Contains: `llm`, `parser`, `chat_template_prompt`, `base_chain`
- Depends on: `constants.SYSTEM_PROMPT`, env vars, `langchain-google-genai`
- Used by: Chain orchestration layer

**Constants Layer:**
- Purpose: Externalises the system prompt so it can be edited independently of chain wiring
- Location: `constants.py`
- Contains: `SYSTEM_PROMPT` string
- Depends on: nothing
- Used by: Chain definition layer

## Data Flow

### Primary Request Path

1. User types message → `input("You: ")` captures string (`main.py:59`)
2. `chat_with_llm(user_prompt)` called with that string (`main.py:65`)
3. `RunnableConfig` created with `{"configurable": {"session_id": "1"}}` (`main.py:48`)
4. `conversation_chain.invoke({"input": user_prompt}, config)` called (`main.py:50`)
5. `RunnableWithMessageHistory` calls `get_session_history("1")`, retrieves `InMemoryChatMessageHistory` (`main.py:33`)
6. History messages injected into `{"chat_history": [...]}` and merged with `{"input": user_prompt}`
7. `chat_template_prompt` formats: system prompt + prior messages + new human turn (`main.py:20`)
8. Formatted prompt sent to `ChatGoogleGenerativeAI` (Gemini API call) (`main.py:16`)
9. `StrOutputParser` converts `AIMessage` → plain string (`main.py:18`)
10. `RunnableWithMessageHistory` appends human message + AI response to history store
11. Response string returned to `chat_with_llm()`, printed: `print(f"AI: {response}")` (`main.py:52`)

### Session Initialisation

1. First call with `session_id="1"` → `get_session_history` finds no entry in `history_state`
2. New `InMemoryChatMessageHistory()` created and stored under key `"1"` (`main.py:35`)
3. Subsequent calls reuse the same object; history grows across turns

**State Management:**
- Chat history stored in `history_state: dict` at module scope (`main.py:30`)
- Keyed by `session_id` string; only key ever used is `"1"`
- `InMemoryChatMessageHistory` holds an ordered list of `HumanMessage` / `AIMessage` objects
- History is never persisted to disk; it is lost when the process exits
- No pruning or token-limit enforcement on history length

## Key Abstractions

**RunnableWithMessageHistory:**
- Purpose: Transparently injects conversation history into any LCEL runnable without modifying the chain
- Example: `main.py:39-44`
- Pattern: Decorator/wrapper — wraps `base_chain`, intercepts invoke, reads history before and writes after

**ChatPromptTemplate with MessagesPlaceholder:**
- Purpose: Separates prompt structure (system + history slot + human turn) from runtime values
- Example: `main.py:20-26`
- Pattern: Template — variable substitution at invoke time

## Entry Points

**`main.py` (CLI):**
- Location: `main.py:70` (`if __name__ == "__main__": main()`)
- Triggers: `python main.py` from the shell
- Responsibilities: Loads `.env`, initialises all module-level objects (LLM, chain, history store), runs the I/O loop

## Architectural Constraints

- **Threading:** Single-threaded blocking I/O loop; no async, no concurrency
- **Global state:** `history_state` dict and all chain objects are module-level singletons (`main.py:16-44`)
- **Session isolation:** Only one session (`"1"`) is ever created; multiple simultaneous users would share history
- **History persistence:** In-memory only — history is lost on process restart
- **Model selection:** Both model name and API key are runtime env vars (`GEMINI_LLM_MODEL`, `GEMINI_API_KEY`); no fallback if unset (evaluates to `None`)
- **Error handling:** Bare `except Exception as e` in `main()` — prints error and continues loop; no retry logic

## Anti-Patterns

### Hardcoded session_id

**What happens:** `chat_with_llm` always passes `session_id="1"` (`main.py:48`)
**Why it's wrong:** Makes multi-user or multi-session use impossible without code changes; the `get_session_history` abstraction is wasted
**Do this instead:** Accept `session_id` as a parameter to `chat_with_llm` or generate a UUID per process run

### Module-level chain initialisation with no guard

**What happens:** `llm`, `base_chain`, and `conversation_chain` are constructed at import time (`main.py:16-44`), before `load_dotenv()` is confirmed to have populated the env
**Why it's wrong:** `load_dotenv()` is called at line 11 but the env vars are read at lines 13-14 immediately after — if `.env` is missing or malformed the LLM is constructed with `model=None`
**Do this instead:** Move chain construction inside `main()` or add explicit validation after `load_dotenv()`

## Error Handling

**Strategy:** Single try/except in the CLI loop; all chain errors surfaced as printed messages

**Patterns:**
- `try/except Exception as e` wraps `chat_with_llm()` call (`main.py:63-66`)
- No custom exception types
- No retry on transient API failures

## Cross-Cutting Concerns

**Logging:** None — only `print()` statements to stdout
**Validation:** Empty/whitespace input breaks the loop (`main.py:61-62`); no other input validation
**Authentication:** Google API key passed directly to `ChatGoogleGenerativeAI` constructor from env var

---

*Architecture analysis: 2026-06-06*
