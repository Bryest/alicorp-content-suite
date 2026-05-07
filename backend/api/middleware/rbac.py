"""
Role-based access control.

`require_roles(*roles)` returns a FastAPI dependency that enforces the
caller's role is in the permitted set. Combined with the JWT dependency
this gives us a 403 on any cross-role attempt — the database RLS layer
is the second defense.
"""

from __future__ import annotations

from fastapi import Depends, HTTPException, status

from .auth import AuthUser, get_current_user


def require_roles(*allowed: str):
    allowed_set = set(allowed)

    async def _dep(user: AuthUser = Depends(get_current_user)) -> AuthUser:
        if user.role not in allowed_set:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{user.role}' not in allowed roles {sorted(allowed_set)}",
            )
        return user

    return _dep
