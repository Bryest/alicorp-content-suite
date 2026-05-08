"""Auth routes — login + (optionally) demo users.

Two login modes (transparent to the frontend):

  REAL Supabase mode (SUPABASE_URL + SUPABASE_ANON_KEY set)
    - Validates password against Supabase Auth via /auth/v1/token
    - Returns the user-scoped JWT issued by Supabase itself
    - Looks up the role from the public.user_roles table

  MOCK mode (no Supabase keys, OR Supabase rejected)
    - Validates against the static DEMO_USERS dict
    - Issues a locally-signed HS256 JWT with the role baked in
"""

import logging
from typing import Optional

import httpx
from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import JSONResponse

from ...config import get_settings
from ..middleware.auth import _resolve_role_for_user, issue_mock_token
from ..middleware.rate_limit import limiter
from ..schemas import LoginRequest

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


async def _login_supabase(email: str, password: str) -> Optional[dict]:
    """
    Authenticate against Supabase Auth REST. Returns the same shape as
    issue_mock_token so the route stays uniform.
    """
    settings = get_settings()
    if not (settings.supabase_url and settings.supabase_anon_key):
        return None
    url = f"{settings.supabase_url}/auth/v1/token?grant_type=password"
    headers = {
        "apikey": settings.supabase_anon_key,
        "Content-Type": "application/json",
    }
    body = {"email": email, "password": password}
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(url, headers=headers, json=body)
        if resp.status_code != 200:
            logger.info(
                f"Supabase auth rejected {email}: {resp.status_code} {resp.text[:120]}"
            )
            return None
        data = resp.json()
    except Exception as e:  # pragma: no cover
        logger.warning(f"Supabase auth call failed: {e}")
        return None

    token = data.get("access_token")
    user = data.get("user") or {}
    user_id = user.get("id")
    user_email = user.get("email") or email
    if not (token and user_id):
        return None

    role = _resolve_role_for_user(user_id, user_email) or "creator"
    return {
        "token": token,
        "user_id": user_id,
        "email": user_email,
        "role": role,
    }


@router.post("/login")
@limiter.limit("5/minute")
async def login(request: Request, payload: LoginRequest) -> JSONResponse:
    settings = get_settings()
    result: Optional[dict] = None
    if not settings.supabase_mocked:
        result = await _login_supabase(payload.email, payload.password)
    if result is None:
        # Mock mode, OR Supabase rejected — fall through to the in-memory
        # demo accounts so dev environments without keys still work.
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
