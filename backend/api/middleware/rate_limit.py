"""
Rate limiting via slowapi.

Per-IP token bucket. State lives in-process — fine for single-instance
deployments (Render free tier). For horizontal scaling, swap in
RedisStorageURI as the storage backend.

Usage in routes:
    from ..middleware.rate_limit import limiter

    @router.post("/foo")
    @limiter.limit("5/minute")
    async def foo(request: Request, ...):
        ...

The first argument MUST be `request: Request` (slowapi requirement).
"""
from __future__ import annotations

from fastapi import Request
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address


def _key_func(request: Request) -> str:
    # Honor X-Forwarded-For when behind a proxy (Render, Vercel, Cloudflare)
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    return get_remote_address(request)


limiter = Limiter(
    key_func=_key_func,
    default_limits=["60/minute"],   # default for any route without its own decorator
    headers_enabled=True,           # adds X-RateLimit-* headers to responses
)


async def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    return JSONResponse(
        status_code=429,
        content={
            "detail": "Too many requests",
            "limit": str(exc.detail) if exc else "rate limit exceeded",
            "retry_after_seconds": 60,
            "hint": "This endpoint is rate-limited per IP. Slow down and retry.",
        },
        headers={"Retry-After": "60"},
    )
