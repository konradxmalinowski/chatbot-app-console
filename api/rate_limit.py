"""Shared slowapi rate limiter for the REST API.

Keyed by the bearer token when one is present (so limits are enforced per
token-holder, as required — "20 req/min per token" — not just per IP), and falling
back to the client's remote address for routes with no token yet, namely
POST /auth/token, which still needs its own rate limit to slow down brute-forcing
API_SECRET.
"""

from fastapi import Request
from slowapi import Limiter
from slowapi.util import get_remote_address

_BEARER_PREFIX = "Bearer "


def _rate_limit_key(request: Request) -> str:
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith(_BEARER_PREFIX):
        return auth_header[len(_BEARER_PREFIX) :]
    return get_remote_address(request)


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
# token" via the same _rate_limit_key (bearer token when present, else IP).
#
# /auth/token keeps its own @limiter.limit("5/minute") decorator instead: that
# route has no Depends that can fail before the decorator runs, so the bypass
# doesn't apply there, and it needs a stricter, distinct limit anyway.
limiter = Limiter(
    key_func=_rate_limit_key, headers_enabled=True, default_limits=["20/minute"]
)
