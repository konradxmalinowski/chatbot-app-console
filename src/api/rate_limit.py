"""Shared slowapi rate limiter for the REST API.

Keyed by the JWT's ``sub`` claim when a validly-signed bearer token is present (so
limits are enforced per service identity, as required — "20 req/min per token" —
not just per IP), and falling back to the client's remote address otherwise: for
routes with no token yet (POST /auth/token, which still needs its own rate limit
to slow down brute-forcing API_SECRET) as well as for a missing/invalid/expired
token.

SEC-002 fix: this used to key on the raw bearer token string. Every
POST /auth/token issues a *distinct* JWT (the iat/exp claims differ each second),
so each freshly minted token got its own independent bucket — an attacker could
harvest tokens (within /auth/token's own 5/min limit) and round-robin requests
across them to multiply the effective /chat rate limit far beyond 20/min. Since
every valid token shares the same ``sub`` ("api-client", this is single
shared-secret service auth — see api/auth.py), keying on ``sub`` instead makes all
tokens for that one identity share a single bucket, regardless of rotation. An
invalid/expired/forged token fails to decode and falls back to the IP bucket —
the same bucket a request with no token at all would use.
"""

import os

import jwt
from fastapi import Request
from slowapi import Limiter
from slowapi.util import get_remote_address

_BEARER_PREFIX = "Bearer "

# Mirrors api/auth.py's JWT_ALGORITHM. Not imported from there to avoid a circular
# import (api/auth.py imports `limiter` from this module).
_JWT_ALGORITHM = "HS256"


def _rate_limit_key(request: Request) -> str:
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith(_BEARER_PREFIX):
        return get_remote_address(request)

    token = auth_header[len(_BEARER_PREFIX) :]
    jwt_secret = os.environ.get("JWT_SECRET_KEY", "")
    try:
        payload = jwt.decode(
            token,
            jwt_secret,
            algorithms=[_JWT_ALGORITHM],
            options={"require": ["exp"]},
        )
    except jwt.PyJWTError:
        # Malformed/expired/forged/wrong-signature token: fall back to IP, same
        # bucket as an unauthenticated request. verify_token (api/auth.py) is the
        # actual auth gate — this key function only needs a *stable* bucket, it
        # does not need to reject the request itself.
        return get_remote_address(request)

    sub = payload.get("sub")
    if not sub:
        return get_remote_address(request)
    return f"sub:{sub}"


# headers_enabled=True is required for slowapi to attach the Retry-After header (and
# the X-RateLimit-* headers) to 429 responses — it defaults to False, which would
# otherwise leave 429s with no Retry-After, contrary to the API's error-handling spec.
#
# default_limits is enforced by SlowAPIMiddleware (see api/main.py) at the ASGI
# layer, before routing/dependency-injection runs. This is deliberately the *only*
# rate limit on /chat and /chat/rag (no per-route @limiter.limit(...) decorator on
# either): slowapi's middleware exempts any route that has its own decorator and
# defers entirely to it, but a decorator's check only runs *inside* the endpoint
# body — i.e. after FastAPI has already resolved Depends(verify_token). A request
# with no/invalid token never reaches the decorator's check at all, so it would go
# completely unrate-limited. default_limits, enforced by the middleware before
# Depends runs, closes that gap while still matching the spec's "20 req/min per
# token" via the same _rate_limit_key (JWT `sub` claim when present and valid,
# else IP). Do NOT revert to per-route decorators — see the reasoning above.
#
# /auth/token keeps its own @limiter.limit("5/minute") decorator instead: that
# route has no Depends that can fail before the decorator runs, so the bypass
# doesn't apply there, and it needs a stricter, distinct limit anyway.
limiter = Limiter(
    key_func=_rate_limit_key, headers_enabled=True, default_limits=["20/minute"]
)
