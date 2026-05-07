"""Approval + multimodal audit routes — Module III."""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile

from ...application.audit_service import AuditService
from ...domain.content import InvalidTransitionError
from ..dependencies import get_audit_service
from ..middleware.auth import AuthUser
from ..middleware.rate_limit import limiter
from ..middleware.rbac import require_roles
from ..schemas import AuditResponse, TextDecisionRequest, TextDecisionResponse

router = APIRouter(prefix="/api/v1/audit", tags=["audit"])


_ALLOWED_MIME = {"image/jpeg", "image/png", "image/webp", "image/jpg"}
_MAX_BYTES = 5 * 1024 * 1024  # 5 MB (tightened from 10 MB)


@router.patch("/text/{content_id}", response_model=TextDecisionResponse)
@limiter.limit("20/minute")
async def decide_text(
    request: Request,
    content_id: UUID,
    payload: TextDecisionRequest,
    user: AuthUser = Depends(require_roles("approver_a")),
    svc: AuditService = Depends(get_audit_service),
) -> TextDecisionResponse:
    try:
        result = await svc.decide_text(
            content_id=content_id,
            actor_id=user.user_id,
            decision=payload.decision,
            notes=payload.notes,
        )
    except InvalidTransitionError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return TextDecisionResponse(**result)


@router.post("/image/{content_id}", response_model=AuditResponse)
@limiter.limit("5/minute")
async def audit_image(
    request: Request,
    content_id: UUID,
    image: UploadFile = File(...),
    user: AuthUser = Depends(require_roles("approver_b")),
    svc: AuditService = Depends(get_audit_service),
) -> AuditResponse:
    if image.content_type not in _ALLOWED_MIME:
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported image type '{image.content_type}'. Allowed: {sorted(_ALLOWED_MIME)}",
        )
    payload = await image.read()
    if not payload:
        raise HTTPException(status_code=400, detail="Empty image payload")
    if len(payload) > _MAX_BYTES:
        raise HTTPException(status_code=413, detail="Image exceeds 5 MB")
    try:
        result = await svc.audit_image(
            content_id=content_id,
            actor_id=user.user_id,
            image_bytes=payload,
            mime_type=image.content_type,
        )
    except InvalidTransitionError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return AuditResponse(**result)
