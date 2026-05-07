"""Auth routes — login + (optionally) demo users."""

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import JSONResponse

from ...config import get_settings
from ..middleware.auth import issue_mock_token
from ..middleware.rate_limit import limiter
from ..schemas import LoginRequest

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


@router.post("/login")
@limiter.limit("5/minute")
async def login(request: Request, payload: LoginRequest) -> JSONResponse:
    result = issue_mock_token(payload.email, payload.password)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )
    return JSONResponse(content={
        "access_token": result["token"],
        "token_type": "bearer",
        "user_id": str(result["user_id"]),
        "email": result["email"],
        "role": result["role"],
    })


@router.get("/demo-users")
@limiter.limit("30/minute")
async def demo_users(request: Request) -> JSONResponse:
    """Demo accounts — hidden in production+real-mode."""
    settings = get_settings()
    if settings.environment.lower() == "production" and not settings.supabase_mocked:
        raise HTTPException(status_code=404, detail="Not found")
    from ...infrastructure.supabase_client import DEMO_USERS

    return JSONResponse(content={
        "users": [
            {"email": u["email"], "password": u["password"], "role": u["role"]}
            for u in DEMO_USERS.values()
        ],
        "note": "These accounts work in mock mode.",
    })
