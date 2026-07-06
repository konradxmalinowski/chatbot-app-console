"""Integration tests for the FastAPI app (api/main.py).

Every endpoint gets at least one happy path and one error case. The LLM, RAG store,
and retriever are all mocked (see conftest's client fixtures); no real network call
is ever made. The rate-limit regression tests below specifically guard the
ASGI-middleware design that keeps failed-auth traffic rate-limited.
"""

VALID_SESSION = "sess-1"


# --- POST /auth/token --------------------------------------------------------
class TestAuthToken:
    def test_correct_secret_returns_jwt(self, client, api_secret):
        resp = client.post("/auth/token", json={"api_secret": api_secret})
        assert resp.status_code == 200
        body = resp.json()
        assert body["token_type"] == "bearer"
        assert isinstance(body["access_token"], str) and body["access_token"]

    def test_wrong_secret_returns_401(self, client):
        resp = client.post("/auth/token", json={"api_secret": "wrong-secret"})
        assert resp.status_code == 401


# --- POST /chat --------------------------------------------------------------
class TestChat:
    def test_valid_token_returns_200(self, client, auth_headers):
        resp = client.post(
            "/chat",
            json={"message": "Hello there", "session_id": VALID_SESSION},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["response"]

    def test_missing_token_returns_401(self, client):
        resp = client.post(
            "/chat", json={"message": "Hello", "session_id": VALID_SESSION}
        )
        assert resp.status_code == 401

    def test_invalid_token_returns_401(self, client):
        resp = client.post(
            "/chat",
            json={"message": "Hello", "session_id": VALID_SESSION},
            headers={"Authorization": "Bearer not-a-real-jwt"},
        )
        assert resp.status_code == 401

    def test_message_too_long_returns_422(self, client, auth_headers):
        resp = client.post(
            "/chat",
            json={"message": "x" * 5000, "session_id": VALID_SESSION},
            headers=auth_headers,
        )
        assert resp.status_code == 422

    def test_malformed_session_id_returns_422(self, client, auth_headers):
        resp = client.post(
            "/chat",
            json={"message": "Hello", "session_id": "../etc/passwd"},
            headers=auth_headers,
        )
        assert resp.status_code == 422


# --- POST /chat/rag ----------------------------------------------------------
class TestChatRag:
    def test_returns_sources_when_store_has_content(self, client, auth_headers):
        resp = client.post(
            "/chat/rag",
            json={"message": "What is the refund window?", "session_id": VALID_SESSION},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["response"]
        assert len(body["sources"]) >= 1
        assert body["sources"][0]["file"] == "faq.md"

    def test_returns_503_when_store_unavailable(self, client_no_rag, auth_headers):
        resp = client_no_rag.post(
            "/chat/rag",
            json={"message": "anything", "session_id": VALID_SESSION},
            headers=auth_headers,
        )
        assert resp.status_code == 503


# --- GET /health -------------------------------------------------------------
class TestHealth:
    def test_health_ok_without_auth(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    def test_health_is_not_rate_limited(self, client):
        # /health is @limiter.exempt: hammering it well past the 20/min default
        # limit must never produce a 429.
        statuses = {client.get("/health").status_code for _ in range(30)}
        assert statuses == {200}


# --- POST /agent -------------------------------------------------------------
class TestAgent:
    def test_complete_response_for_non_tool_turn(self, client, auth_headers):
        resp = client.post(
            "/agent",
            json={"message": "just say hello", "session_id": "agent-complete"},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "complete"
        assert body["response"]

    def test_pending_approval_for_tool_turn(self, client, auth_headers):
        resp = client.post(
            "/agent",
            json={"message": "please calc 2+2", "session_id": "agent-pending"},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "pending_approval"
        assert body["pending_id"] == "agent-pending"
        assert len(body["pending_tool_calls"]) == 1
        assert body["pending_tool_calls"][0]["tool"] == "calculator"

    def test_agent_requires_auth(self, client):
        resp = client.post("/agent", json={"message": "hi", "session_id": "no-auth"})
        assert resp.status_code == 401


# --- POST /agent/{pending_id}/approve and /reject ----------------------------
class TestAgentApproveReject:
    def _create_pending(self, client, auth_headers, session_id):
        resp = client.post(
            "/agent",
            json={"message": "please calc 2+2", "session_id": session_id},
            headers=auth_headers,
        )
        assert resp.json()["status"] == "pending_approval"

    def test_approve_resumes_to_completion(self, client, auth_headers):
        session_id = "approve-flow"
        self._create_pending(client, auth_headers, session_id)

        resp = client.post(f"/agent/{session_id}/approve", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["status"] == "complete"

    def test_reject_resumes_to_completion(self, client, auth_headers):
        session_id = "reject-flow"
        self._create_pending(client, auth_headers, session_id)

        resp = client.post(f"/agent/{session_id}/reject", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["status"] == "complete"

    def test_approve_without_pending_returns_404(self, client, auth_headers):
        resp = client.post("/agent/no-such-pending/approve", headers=auth_headers)
        assert resp.status_code == 404

    def test_reject_without_pending_returns_404(self, client, auth_headers):
        resp = client.post("/agent/no-such-pending/reject", headers=auth_headers)
        assert resp.status_code == 404


# --- Rate limiting regression -----------------------------------------------
class TestRateLimitingRegression:
    """The core regression this suite must protect: requests that FAIL auth
    (no/invalid token) are still rate-limited, because the limit is enforced by
    SlowAPIMiddleware at the ASGI layer BEFORE Depends(verify_token) runs. If a
    future change moves the limit into a per-route decorator, failed-auth traffic
    would go unlimited and these tests would fail.
    """

    def test_unauthenticated_chat_flood_gets_429(self, client):
        statuses = [
            client.post(
                "/chat", json={"message": "spam", "session_id": VALID_SESSION}
            ).status_code
            for _ in range(30)
        ]
        # Before the limit: 401 (auth fails). After 20/min: 429 from the middleware.
        assert 429 in statuses
        assert 401 in statuses

    def test_unauthenticated_agent_flood_gets_429(self, client):
        statuses = [
            client.post(
                "/agent", json={"message": "spam", "session_id": VALID_SESSION}
            ).status_code
            for _ in range(30)
        ]
        assert 429 in statuses
