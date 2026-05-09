"""Maps upstream provider exceptions (Groq, Gemini, Supabase, httpx) to HTTP statuses."""


import logging
from typing import Type

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────
def _resp(status_code: int, detail: str) -> JSONResponse:
    return JSONResponse(status_code=status_code, content={"detail": detail})


def _exception_class(qualified_name: str) -> Type[BaseException] | None:
    """Lookup an exception class by dotted path, returning None if unimportable."""
    try:
        module_path, class_name = qualified_name.rsplit(".", 1)
        module = __import__(module_path, fromlist=[class_name])
        return getattr(module, class_name, None)
    except Exception:
        return None


# ─────────────────────────────────────────────────────────────────────
# Provider-specific handlers
# ─────────────────────────────────────────────────────────────────────
def register_provider_handlers(app: FastAPI) -> None:
    """Wire exception handlers for every upstream provider we depend on."""

    # ── Groq SDK (groq.RateLimitError, groq.APIError, ...) ───────────
    groq_rate = _exception_class("groq.RateLimitError")
    if groq_rate is not None:
        @app.exception_handler(groq_rate)
        async def _h(request: Request, exc):  # type: ignore[no-redef]
            logger.warning(f"Groq rate limit on {request.url.path}: {exc}")
            return _resp(429, "Groq rate limit reached. Try again in a moment.")

    groq_auth = _exception_class("groq.AuthenticationError")
    if groq_auth is not None:
        @app.exception_handler(groq_auth)
        async def _h(request: Request, exc):  # type: ignore[no-redef]
            logger.error(f"Groq auth error on {request.url.path}: {exc}")
            return _resp(503, "Upstream LLM authentication failed. Check the server credentials.")

    groq_conn = _exception_class("groq.APIConnectionError")
    if groq_conn is not None:
        @app.exception_handler(groq_conn)
        async def _h(request: Request, exc):  # type: ignore[no-redef]
            logger.warning(f"Groq connection error on {request.url.path}: {exc}")
            return _resp(503, "Cannot reach the LLM provider right now. Try again in a few seconds.")

    # ── Google Generative AI (google.api_core.exceptions.*) ─────────
    google_quota = _exception_class("google.api_core.exceptions.ResourceExhausted")
    if google_quota is not None:
        @app.exception_handler(google_quota)
        async def _h(request: Request, exc):  # type: ignore[no-redef]
            logger.warning(f"Gemini quota exhausted on {request.url.path}: {exc}")
            return _resp(429, "Gemini free-tier quota reached. Quotas reset daily — try again later.")

    google_perm = _exception_class("google.api_core.exceptions.PermissionDenied")
    if google_perm is not None:
        @app.exception_handler(google_perm)
        async def _h(request: Request, exc):  # type: ignore[no-redef]
            logger.error(f"Gemini permission denied on {request.url.path}: {exc}")
            return _resp(403, "Content blocked by Gemini safety filters or invalid API key.")

    google_invalid = _exception_class("google.api_core.exceptions.InvalidArgument")
    if google_invalid is not None:
        @app.exception_handler(google_invalid)
        async def _h(request: Request, exc):  # type: ignore[no-redef]
            logger.warning(f"Gemini invalid argument on {request.url.path}: {exc}")
            return _resp(400, "The request was rejected by the LLM (invalid input or unsupported format).")

    google_notfound = _exception_class("google.api_core.exceptions.NotFound")
    if google_notfound is not None:
        @app.exception_handler(google_notfound)
        async def _h(request: Request, exc):  # type: ignore[no-redef]
            logger.error(f"Gemini model not found on {request.url.path}: {exc}")
            return _resp(503, "The configured model is not available. Server admin must update GEMINI_*_MODEL.")

    google_timeout = _exception_class("google.api_core.exceptions.DeadlineExceeded")
    if google_timeout is not None:
        @app.exception_handler(google_timeout)
        async def _h(request: Request, exc):  # type: ignore[no-redef]
            logger.warning(f"Gemini timeout on {request.url.path}: {exc}")
            return _resp(408, "The LLM took too long to respond. Try again.")

    # ── httpx (used by /auth/login) ──────────────────────────────────
    httpx_status = _exception_class("httpx.HTTPStatusError")
    if httpx_status is not None:
        @app.exception_handler(httpx_status)
        async def _h(request: Request, exc):  # type: ignore[no-redef]
            code = getattr(getattr(exc, "response", None), "status_code", 502)
            logger.warning(f"Upstream HTTP {code} on {request.url.path}: {exc}")
            mapped = code if 400 <= code < 600 else 502
            return _resp(mapped, f"Upstream provider returned HTTP {code}.")

    httpx_conn = _exception_class("httpx.ConnectError")
    if httpx_conn is not None:
        @app.exception_handler(httpx_conn)
        async def _h(request: Request, exc):  # type: ignore[no-redef]
            logger.warning(f"httpx connection error on {request.url.path}: {exc}")
            return _resp(503, "Cannot reach the upstream provider right now.")

    httpx_timeout = _exception_class("httpx.TimeoutException")
    if httpx_timeout is not None:
        @app.exception_handler(httpx_timeout)
        async def _h(request: Request, exc):  # type: ignore[no-redef]
            logger.warning(f"httpx timeout on {request.url.path}: {exc}")
            return _resp(408, "Upstream provider timed out. Try again.")

    # ── Supabase / postgrest ────────────────────────────────────────
    postgrest_err = _exception_class("postgrest.exceptions.APIError")
    if postgrest_err is not None:
        @app.exception_handler(postgrest_err)
        async def _h(request: Request, exc):  # type: ignore[no-redef]
            code_str = str(getattr(exc, "code", "") or "")
            logger.error(f"Supabase API error on {request.url.path}: code={code_str} {exc}")
            # Postgres "23505" = unique violation, "23503" = FK violation, etc.
            if code_str in {"23505"}:
                return _resp(409, "This record already exists.")
            if code_str in {"23503"}:
                return _resp(409, "Referenced record does not exist.")
            return _resp(502, "Database operation failed.")
