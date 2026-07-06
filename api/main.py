"""FastAPI REST API for chatbot-app (Phase 3).

Run with: uvicorn api.main:app

Separate entry point from the CLI (main.py) — the CLI is untouched by this module.
The LLM and (optionally) the RAG vector store are built once at startup (FastAPI
lifespan), not per-request. Conversation history is kept in memory per session_id
(a dict-of-dicts scoped to this process), lazily loaded from sessions/<id>.json on
first use of a given session_id and persisted back after every turn.
"""

import logging
import os
import sys
from contextlib import asynccontextmanager

from dotenv import load_dotenv

# Must run before any module-level env reads below (this project's .env is not
# loaded automatically otherwise, matching main.py's own load_dotenv() call).
load_dotenv()

from fastapi import Depends, FastAPI, HTTPException, Request, Response, status  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from google.api_core.exceptions import GoogleAPIError, PermissionDenied  # noqa: E402
from langchain_core.chat_history import InMemoryChatMessageHistory  # noqa: E402
from langchain_google_genai.chat_models import ChatGoogleGenerativeAIError  # noqa: E402
from langchain_core.runnables import RunnableConfig  # noqa: E402
from langchain_core.runnables.history import RunnableWithMessageHistory  # noqa: E402
from slowapi import _rate_limit_exceeded_handler  # noqa: E402
from slowapi.errors import RateLimitExceeded  # noqa: E402
from slowapi.middleware import SlowAPIMiddleware  # noqa: E402

from api.auth import verify_token  # noqa: E402
from api.auth import router as auth_router  # noqa: E402
from api.models import (  # noqa: E402
    ChatRequest,
    ChatResponse,
    HealthResponse,
    RagChatResponse,
    SourceCitation,
)
from api.rate_limit import limiter  # noqa: E402
from chain_builder import build_base_chain, build_llm, build_rag_answer_chain  # noqa: E402
from chain_builder import format_retrieved_context  # noqa: E402
from constants import RAG_TOP_K, SESSIONS_DIR  # noqa: E402
from rag.bootstrap import build_rag_store  # noqa: E402
from session_store import load_session, save_session  # noqa: E402

logger = logging.getLogger("chatbot_api")
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

# Populated once at startup by the lifespan handler below; read (never mutated as a
# whole) by request handlers. "history" is safe to mutate per-session-id at request
# time — it is a single store shared by both /chat and /chat/rag, since a
# session_id represents one continuous conversation regardless of which endpoint
# served a given turn. Two separate per-endpoint stores would each lazily load
# sessions/<id>.json independently and both write back to the same file, silently
# losing turns when a client interleaves calls to both endpoints with one session_id.
_state: dict = {
    "rag_store": None,
    "non_rag_chain": None,
    "rag_chain": None,
    "history": {},
}


def _validate_env() -> tuple[str, str]:
    """Read and validate required environment variables. Exits on failure, matching
    main.py's fail-fast style for a missing Gemini API key/model.
    """
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    model = os.environ.get("GEMINI_LLM_MODEL", "").strip()

    if not api_key or not model:
        logger.error(
            "Missing required env var(s): GEMINI_API_KEY and/or GEMINI_LLM_MODEL. "
            "Copy .env.example to .env and fill them in."
        )
        sys.exit(1)

    return api_key, model


def _get_or_create_history(
    session_id: str, history_state: dict[str, InMemoryChatMessageHistory]
) -> InMemoryChatMessageHistory:
    """Return the in-memory history for session_id, lazily loading it from disk
    (sessions/<session_id>.json) the first time this process sees this session_id.
    """
    if session_id not in history_state:
        history = InMemoryChatMessageHistory()
        prior_messages = load_session(session_id, SESSIONS_DIR)
        if prior_messages:
            history.add_messages(prior_messages)
        history_state[session_id] = history
    return history_state[session_id]


def _make_conversation_chain(
    base_chain, history_state: dict
) -> RunnableWithMessageHistory:
    def get_session_history(session_id: str) -> InMemoryChatMessageHistory:
        return _get_or_create_history(session_id, history_state)

    return RunnableWithMessageHistory(
        runnable=base_chain,
        get_session_history=get_session_history,
        input_messages_key="input",
        history_messages_key="chat_history",
    )


def _invoke_chain_safely(chain, chain_input: dict, session_id: str) -> str:
    """Invoke an LCEL chain, mapping Gemini/network failures to JSON error responses
    instead of a raw traceback or an unhandled 500.
    """
    config = RunnableConfig({"configurable": {"session_id": session_id}})
    try:
        return chain.invoke(chain_input, config=config)
    except PermissionDenied:
        logger.error("Gemini API key invalid or quota exceeded.")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Upstream LLM authentication or quota error.",
        ) from None
    except GoogleAPIError:
        logger.error("Gemini API network error.")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Upstream LLM network error.",
        ) from None
    except ChatGoogleGenerativeAIError as exc:
        # langchain-google-genai wraps Gemini API errors (incl. 429 quota/rate-limit
        # responses) in its own exception type rather than google.api_core's
        # GoogleAPIError hierarchy, so it needs its own branch here.
        logger.error("Gemini API error: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Upstream LLM error — the model provider rejected the request.",
        ) from None
    except Exception:
        logger.exception("Unexpected error during chat turn.")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error.",
        ) from None


@asynccontextmanager
async def lifespan(app: FastAPI):
    api_key, model = _validate_env()
    llm = build_llm(api_key, model)

    # RAG store initialization can fail fast (sys.exit) on a broken embeddings
    # backend (see rag/embeddings.py) — appropriate for the CLI's opt-in --rag flag,
    # but here /chat doesn't depend on embeddings at all, so a broken RAG backend
    # must not take the whole API down. Deliberate deviation from the CLI's
    # fail-fast style: catch it and degrade to rag_store=None (/chat/rag then
    # reports 503, everything else keeps working).
    try:
        rag_store, message = build_rag_store()
    except SystemExit:
        rag_store, message = None, "RAG store initialization failed — see logs above."

    logger.info(message)

    _state["rag_store"] = rag_store
    _state["non_rag_chain"] = _make_conversation_chain(
        build_base_chain(llm, rag_store=None), _state["history"]
    )

    if rag_store is not None:
        rag_answer_chain = build_rag_answer_chain(llm)
        _state["rag_chain"] = _make_conversation_chain(
            rag_answer_chain, _state["history"]
        )
    else:
        _state["rag_chain"] = None

    logger.info(
        "API startup complete. Vector store: %s",
        "ready" if rag_store is not None else "not_initialized",
    )
    yield
    _state["non_rag_chain"] = None
    _state["rag_chain"] = None
    _state["rag_store"] = None


app = FastAPI(title="chatbot-app API", lifespan=lifespan)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
# SlowAPIMiddleware enforces limiter.default_limits at the ASGI layer, before
# routing/Depends runs — closes the gap where @limiter.limit(...) decorators alone
# only fire *inside* the endpoint body, so requests that fail Depends(verify_token)
# (missing/invalid token) never reach the decorator and were never rate-limited at
# all. See api/rate_limit.py for the full explanation.
app.add_middleware(SlowAPIMiddleware)

# CORS: fail closed. CORS_ORIGINS unset/empty means no origin is allowed — never
# fall back to "*". A literal "*" is rejected at startup rather than silently
# accepted, since allow_origins=["*"] combined with allow_credentials=True below
# would make Starlette reflect the caller's real Origin header — the opposite of
# fail-closed.
_cors_origins = [
    origin.strip()
    for origin in os.environ.get("CORS_ORIGINS", "").split(",")
    if origin.strip()
]
if "*" in _cors_origins:
    raise RuntimeError(
        "CORS_ORIGINS must not contain '*' — list explicit allowed origins, "
        "comma-separated, or leave it unset to allow none."
    )
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)


@app.post("/chat", response_model=ChatResponse)
def chat(
    request: Request,
    response: Response,
    body: ChatRequest,
    token: str = Depends(verify_token),
) -> ChatResponse:
    # No @limiter.limit(...) decorator here deliberately: slowapi's SlowAPIMiddleware
    # (see api/rate_limit.py's default_limits) exempts any route that has its own
    # decorator and defers entirely to it — but a decorator's check only runs
    # *inside* the endpoint body, after Depends(verify_token) has already resolved.
    # A request with no/invalid token never reaches the decorator at all, so it
    # would go completely unrate-limited. Relying on default_limits instead means
    # the ASGI-layer middleware enforces the limit before Depends runs, closing that
    # gap. `response` is still required by slowapi's header injection (headers_enabled=True).
    result = _invoke_chain_safely(
        _state["non_rag_chain"], {"input": body.message}, body.session_id
    )
    history = _state["history"][body.session_id]
    save_session(body.session_id, history.messages, SESSIONS_DIR)
    return ChatResponse(response=result)


@app.post("/chat/rag", response_model=RagChatResponse)
def chat_rag(
    request: Request,
    response: Response,
    body: ChatRequest,
    token: str = Depends(verify_token),
) -> RagChatResponse:
    # See chat()'s comment above: no per-route decorator, relies on
    # default_limits + SlowAPIMiddleware so failed auth is still rate-limited.
    rag_store = _state["rag_store"]
    if rag_store is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "RAG is not available: the vector store has not been initialized. "
                "Add documents to docs/ and restart the server."
            ),
        )

    from rag.retriever import retrieve

    chunks = retrieve(rag_store, body.message, k=RAG_TOP_K)
    context = format_retrieved_context(chunks)

    result = _invoke_chain_safely(
        _state["rag_chain"],
        {"input": body.message, "context": context},
        body.session_id,
    )
    history = _state["history"][body.session_id]
    save_session(body.session_id, history.messages, SESSIONS_DIR)

    sources = [
        SourceCitation(
            file=chunk.metadata.get("source", "unknown"), chunk=chunk.page_content[:200]
        )
        for chunk in chunks
    ]
    return RagChatResponse(response=result, sources=sources)


@app.get("/health", response_model=HealthResponse)
@limiter.exempt
def health() -> HealthResponse:
    vector_store_status = (
        "ready" if _state["rag_store"] is not None else "not_initialized"
    )
    return HealthResponse(status="ok", vector_store=vector_store_status)
