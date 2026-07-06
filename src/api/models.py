"""Pydantic v2 request/response models for the REST API."""

from typing import Literal

from pydantic import BaseModel, Field, field_validator

from constants import MAX_INPUT_LENGTH

# session_id is client-controlled over HTTP (unlike the CLI's hardcoded "1") and is
# used to build a filesystem path in session_store.py (sessions/<session_id>.json)
# with no sanitization there. This pattern is the mandatory fix for that
# path-traversal vector — anything outside it must be rejected with a 422 before it
# ever reaches session_store.py.
SESSION_ID_PATTERN = r"^[a-zA-Z0-9_-]{1,64}$"


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=MAX_INPUT_LENGTH)
    session_id: str = Field(..., pattern=SESSION_ID_PATTERN)

    @field_validator("message")
    @classmethod
    def message_must_not_be_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("message must not be blank")
        return value


class ChatResponse(BaseModel):
    response: str


class SourceCitation(BaseModel):
    file: str
    chunk: str


class RagChatResponse(BaseModel):
    response: str
    sources: list[SourceCitation]


class TokenRequest(BaseModel):
    api_secret: str = Field(..., min_length=1)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str
    expires_in: int


class HealthResponse(BaseModel):
    status: str
    vector_store: str


class AgentRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=MAX_INPUT_LENGTH)
    session_id: str = Field(..., pattern=SESSION_ID_PATTERN)

    @field_validator("message")
    @classmethod
    def message_must_not_be_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("message must not be blank")
        return value


class PendingToolCallModel(BaseModel):
    tool: str
    args: dict


class AgentPendingResponse(BaseModel):
    status: Literal["pending_approval"] = "pending_approval"
    pending_id: str
    # Every tool call the agent wants to run this step, not just one — approving
    # or rejecting is all-or-nothing for the whole batch (LangGraph's parallel
    # tool-calling semantics), so the caller must see everything they're
    # approving, not just a representative first call.
    pending_tool_calls: list[PendingToolCallModel]


class AgentCompleteResponse(BaseModel):
    status: Literal["complete"] = "complete"
    response: str
