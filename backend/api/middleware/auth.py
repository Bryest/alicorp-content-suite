"""
JWT auth middleware.

Two modes, transparent to routes:

  REAL Supabase mode
    - SUPABASE_JWT_SECRET set
    - We verify the JWT using the supabase HS256 secret
    - User role comes from the public.user_roles table

  MOCK mode (no Supabase keys)
    - We issue our own HS256 JWTs from POST /api/v1/auth/login against
      the static DEMO_USERS dictionary
    - Role is encoded as a custom claim 'role' on the token

`get_current_user` is the single dependency used by routes; routes
never see which mode is active.
"""

from __future__ import annotations

import logging
import time
from typing import Optional
from uuid import UUID

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import PyJWKClient

from ...config import get_settings
from ...infrastructure.supabase_client import DEMO_USERS

logger = logging.getLogger(__name__)


bearer_scheme = HTTPBearer(auto_error=False)

# Cache PyJWKClient instances per Supabase URL — they internally cache
# the JWKS response and refresh on signing-key rotation.
_jwks_cache: dict[str, PyJWKClient] = {}


def _jwks_client_for(supabase_url: str) -> PyJWKClient:
    if supabase_url not in _jwks_cache:
        url = f"{supabase_url.rstrip('/')}/auth/v1/.well-known/jwks.json"
        _jwks_cache[supabase_url] = PyJWKClient(url)
    return _jwks_cache[supabase_url]


class AuthUser:
    __slots__ = ("user_id", "email", "role")

    def __init__(self, user_id: UUID, email: str, role: str):
        self.user_id = user_id
        self.email = email
        self.role = role

    def __repr__(self) -> str:  # pragma: no cover
        return f"AuthUser(user_id={self.user_id}, email={self.email}, role={self.role})"


def issue_mock_token(email: str, password: str) -> Optional[dict]:
    """Validate a demo login and return (token, user_record) or None."""
    user = DEMO_USERS.get(email.lower())
    if not user or user["password"] != password:
        return None
    settings = get_settings()
    payload = {
        "sub": str(user["id"]),
        "email": user["email"],
        "role": user["role"],
        "iat": int(time.time()),
        "exp": int(time.time()) + 60 * 60 * 8,  # 8 hours
        "iss": "alicorp-content-suite-mock",
    }
    token = jwt.encode(payload, settings.mock_jwt_secret, algorithm="HS256")
    return {
        "token": token,
        "user_id": user["id"],
        "email": user["email"],
        "role": user["role"],
    }


_ASYMMETRIC_ALGS = {"ES256", "ES384", "ES512", "RS256", "RS384", "RS512", "EdDSA"}


def _decode(token: str) -> dict:
    settings = get_settings()
    last_err: Optional[Exception] = None

    # 1) Sniff the JWT header to pick the right verification path.
    try:
        header = jwt.get_unverified_header(token)
        alg = header.get("alg") or "HS256"
    except Exception as e:
        alg = "HS256"
        last_err = e

    # 2) Asymmetric tokens (modern Supabase = ES256 by default) verified via JWKS.
    if alg in _ASYMMETRIC_ALGS and settings.supabase_url:
        try:
            jwks = _jwks_client_for(settings.supabase_url)
            signing_key = jwks.get_signing_key_from_jwt(token).key
            return jwt.decode(
                token,
                signing_key,
                algorithms=[alg],
                options={"verify_aud": False},
            )
        except Exception as e:
            last_err = e
            logger.warning(f"JWKS verify failed (alg={alg}): {e}")

    # 3) Symmetric tokens — mock JWTs and Supabase legacy HS256 (if anyone
    # ever rotates back). We try Supabase legacy secret first, then mock.
    candidates: list[str] = []
    if settings.supabase_jwt_secret:
        candidates.append(settings.supabase_jwt_secret)
    candidates.append(settings.mock_jwt_secret)

    for secret in candidates:
        try:
            return jwt.decode(
                token,
                secret,
                algorithms=["HS256"],
                options={"verify_aud": False},
            )
        except Exception as e:
            last_err = e
            continue

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=f"Invalid or expired token ({last_err})",
    )


async def get_current_user(
    creds: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
) -> AuthUser:
    if creds is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing bearer token",
        )
    payload = _decode(creds.credentials)
    sub = payload.get("sub")
    if not sub:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token missing subject",
        )
    role = payload.get("role")
    email = payload.get("email", "")
    # Supabase JWTs carry role="authenticated" by default — that's not one of
    # our app roles. Treat it (and any non-app value) as missing and look up
    # the real role in user_roles.
    APP_ROLES = {"creator", "approver_a", "approver_b"}
    if role not in APP_ROLES:
        role = _resolve_role_for_user(sub, email)
    try:
        user_id = UUID(sub)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid subject",
        )
    return AuthUser(user_id=user_id, email=email, role=role or "creator")


def _resolve_role_for_user(user_id: str, email: str) -> Optional[str]:
    settings = get_settings()
    if settings.supabase_mocked:
        u = DEMO_USERS.get((email or "").lower())
        return u["role"] if u else None
    try:
        from supabase import create_client

        client = create_client(settings.supabase_url, settings.supabase_service_role_key)
        resp = (
            client.table("user_roles")
            .select("role")
            .eq("user_id", user_id)
            .limit(1)
            .execute()
        )
        if resp.data:
            return resp.data[0]["role"]
    except Exception as e:  # pragma: no cover
        logger.warning(f"Role lookup failed: {e}")
    return None
