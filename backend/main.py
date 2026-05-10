"""Content Suite — FastAPI entry point.

Run locally:
    uvicorn backend.main:app --reload --port 8000
"""

import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded

from .config import get_settings
from .api.middleware.exception_handlers import register_provider_handlers
from .api.middleware.rate_limit import limiter, rate_limit_exceeded_handler
from .api.routes import auth as auth_routes
from .api.routes import brand as brand_routes
from .api.routes import content as content_routes
from .api.routes import audit as audit_routes
from .api.routes import health as health_routes
from .infrastructure.langfuse_client import get_tracer

settings = get_settings()
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)
access_log = logging.getLogger("access")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Content Suite booted (env=%s).", settings.environment)
    yield
    # Shutdown (no-op for now; reserved for graceful provider client teardown)


app = FastAPI(
    title="Content Suite — Alicorp IAGen",
    description=(
        "Brand-aware content generation with RAG, multimodal audit and full "
        "Langfuse observability."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# ── Rate limiter ─────────────────────────────────────────────────
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)

# ── Upstream provider exception handlers ────────────────────────
# Maps Groq/Gemini/Supabase/httpx exceptions to proper HTTP statuses
# (429 for quota exhausted, 503 for connectivity, etc.) so the
# frontend humanizer can show specific messages instead of "500".
register_provider_handlers(app)

# ── CORS ────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Security headers + access log + Langfuse flush ──────────────
@app.middleware("http")
async def security_and_logging(request: Request, call_next):
    t0 = time.time()
    response = await call_next(request)
    elapsed_ms = int((time.time() - t0) * 1000)

    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "same-origin"
    response.headers["X-XSS-Protection"] = "1; mode=block"

    fwd = request.headers.get("x-forwarded-for", "")
    ip = (fwd.split(",")[0].strip() if fwd else (request.client.host if request.client else "?"))
    access_log.info(
        "%s %s -> %s in %dms ip=%s",
        request.method,
        request.url.path,
        response.status_code,
        elapsed_ms,
        ip,
    )

    try:
        get_tracer().flush()
    except Exception as e:  # pragma: no cover
        logger.debug(f"Langfuse flush noop: {e}")
    return response


# ── Routers ─────────────────────────────────────────────────────
app.include_router(health_routes.router)
app.include_router(auth_routes.router)
app.include_router(brand_routes.router)
app.include_router(content_routes.router)
app.include_router(audit_routes.router)


async def _unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception(f"Unhandled error on {request.url.path}: {exc}")
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )


app.add_exception_handler(Exception, _unhandled_exception_handler)


@app.get("/")
async def root():
    return {
        "name": "Content Suite",
        "module": "Alicorp IAGen",
        "docs": "/docs",
        "health": "/api/v1/health",
        "environment": settings.environment,
    }
