"""Authentication for the REST API: JWT issuance and verification.

This is service-to-service auth, not a login system: there is no per-user identity
anywhere in this project. A client exchanges a pre-shared secret (the API_SECRET
env var) for a short-lived JWT via POST /auth/token, then presents that JWT as a
Bearer token on protected routes. JWT_SECRET_KEY (separate from API_SECRET) signs
the tokens.
"""

import logging
import os
import secrets
import time

import jwt
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from api.models import TokenRequest, TokenResponse
from api.rate_limit import limiter

logger = logging.getLogger(__name__)

JWT_ALGORITHM = "HS256"
JWT_EXPIRES_IN_SECONDS = 3600

# Minimum length (chars) for both API_SECRET and JWT_SECRET_KEY — see
# validate_secret_strength() below. `openssl rand -hex 32` produces exactly 64
# hex characters (32 bytes of entropy), well above this floor.
MIN_SECRET_LENGTH = 32

_security = HTTPBearer(auto_error=False)

router = APIRouter()


def validate_secret_strength() -> None:
    """Fail closed at process startup if API_SECRET/JWT_SECRET_KEY are missing,
    too short, or identical to each other.

    Called once from api/main.py's lifespan(), not lazily from a request handler:
    a weak/misconfigured signing key is a total auth-bypass risk (SEC-001) — an
    attacker who obtains one valid JWT can brute-force a short key offline and
    forge arbitrary tokens — and reusing the same value for both secrets
    collapses the two-layer pre-shared-secret / signing-key design into one
    (SEC-006): anyone who legitimately holds API_SECRET could sign their own
    JWTs directly. Matches this codebase's fail-fast style used elsewhere for
    env validation (e.g. main.py's CLI provider checks, CORS_ORIGINS in
    api/main.py) — raises RuntimeError rather than degrading or warning.
    """
    api_secret = os.environ.get("API_SECRET", "")
    jwt_secret = os.environ.get("JWT_SECRET_KEY", "")

    for name, value in (("API_SECRET", api_secret), ("JWT_SECRET_KEY", jwt_secret)):
        if len(value) < MIN_SECRET_LENGTH:
            raise RuntimeError(
                f"{name} must be at least {MIN_SECRET_LENGTH} characters long "
                "(use: openssl rand -hex 32)."
            )

    if api_secret == jwt_secret:
        raise RuntimeError(
            "API_SECRET and JWT_SECRET_KEY must not be equal — using the same "
            "value for both collapses the two-layer auth design (any client "
            "that knows API_SECRET could sign its own JWTs)."
        )


def _get_api_secret() -> str:
    value = os.environ.get("API_SECRET", "").strip()
    if not value:
        # Fail closed: if the operator never configured API_SECRET, no token can
        # ever be issued — this is a server misconfiguration, not a client error.
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication is not configured on this server.",
        )
    return value


def _get_jwt_secret() -> str:
    value = os.environ.get("JWT_SECRET_KEY", "").strip()
    if not value:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication is not configured on this server.",
        )
    return value


@router.post("/auth/token", response_model=TokenResponse)
@limiter.limit("5/minute")
def issue_token(
    request: Request, response: Response, body: TokenRequest
) -> TokenResponse:
    """Exchange the pre-shared API_SECRET for a short-lived JWT.

    Rate-limited (5/minute, keyed by client IP since no token exists yet) to slow
    down brute-forcing API_SECRET.

    The unused ``response`` parameter is required by slowapi: with
    ``headers_enabled=True`` it injects X-RateLimit-*/Retry-After headers into
    whatever ``Response`` object FastAPI passes into the endpoint's kwargs, which
    only happens if the endpoint declares one. Omitting it makes slowapi raise on
    every successful (not just rate-limited) request to this route.
    """
    expected_secret = _get_api_secret()

    # Constant-time comparison — timing-attack hygiene per project security rules.
    # Compare as bytes: secrets.compare_digest raises TypeError on non-ASCII str
    # input, which would otherwise let any anonymous client 500 this endpoint by
    # sending a non-ASCII api_secret.
    if not secrets.compare_digest(
        body.api_secret.encode("utf-8"), expected_secret.encode("utf-8")
    ):
        logger.warning("Rejected /auth/token request with an invalid api_secret.")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials.",
        )

    now = int(time.time())
    payload = {
        "sub": "api-client",
        "iat": now,
        "exp": now + JWT_EXPIRES_IN_SECONDS,
    }
    token = jwt.encode(payload, _get_jwt_secret(), algorithm=JWT_ALGORITHM)

    return TokenResponse(
        access_token=token,
        token_type="bearer",
        expires_in=JWT_EXPIRES_IN_SECONDS,
    )


def verify_token(
    credentials: HTTPAuthorizationCredentials | None = Depends(_security),
) -> str:
    """FastAPI dependency: verifies the Bearer JWT and returns the raw token string.

    Raises 401 with a generic message on any failure — missing header, malformed
    token, expired token, or bad signature all produce the same response, so a
    caller can't use the error to fingerprint which check failed.
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated.",
        )

    try:
        jwt.decode(
            credentials.credentials,
            _get_jwt_secret(),
            algorithms=[JWT_ALGORITHM],
            options={"require": ["exp"]},
        )
    except jwt.PyJWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token.",
        ) from None

    return credentials.credentials
