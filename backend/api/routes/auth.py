"""Auth routes. Login proxies to Supabase Auth (password grant) and resolves the app role."""

import logging
from typing import Optional

import httpx
from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import JSONResponse

from ...config import get_settings
from ..middleware.auth import _resolve_role_for_user
from ..middleware.rate_limit import limiter
from ..schemas import LoginRequest

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


async def _login_supabase(email: str, password: str) -> Optional[dict]:
    """
    Authenticate against Supabase Auth REST. Returns:
      {"token", "user_id", "email", "role"}
    or None if Supabase rejected the credentials.
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

    role = _resolve_role_for_user(user_id, user_email)
    if not role:
        logger.warning(f"User {user_email} ({user_id}) has no role in user_roles")
        return None

    return {
        "token": token,
        "user_id": user_id,
        "email": user_email,
        "role": role,
    }


@router.post("/login")
@limiter.limit("5/minute")
async def login(request: Request, payload: LoginRequest) -> JSONResponse:
    result = await _login_supabase(payload.email, payload.password)
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
