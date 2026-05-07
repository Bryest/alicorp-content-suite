"""Content generation + listing routes — Module II + read paths."""
from __future__ import annotations

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from ...application.content_service import ContentService
from ...domain.content import ApprovalStatus, ContentType
from ..dependencies import get_content_service
from ..middleware.auth import AuthUser, get_current_user
from ..middleware.rate_limit import limiter
from ..middleware.rbac import require_roles
from ..schemas import ContentDetail, GenerateRequest, GenerateResponse

router = APIRouter(prefix="/api/v1", tags=["content"])


@router.post("/generate", response_model=GenerateResponse)
@limiter.limit("5/minute")
async def generate_content(
    request: Request,
    payload: GenerateRequest,
    user: AuthUser = Depends(require_roles("creator")),
    svc: ContentService = Depends(get_content_service),
) -> GenerateResponse:
    try:
        ct = ContentType(payload.content_type)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown content_type '{payload.content_type}'. "
            f"Allowed: {[c.value for c in ContentType]}",
        )
    result = await svc.generate(
        creator_id=user.user_id,
        brand_id=payload.brand_id,
        content_type=ct,
        request=payload.request,
    )
    return GenerateResponse(**result)


@router.get("/content", response_model=list[ContentDetail])
@limiter.limit("60/minute")
async def list_content(
    request: Request,
    status: Optional[str] = Query(None),
    brand_id: Optional[UUID] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    user: AuthUser = Depends(get_current_user),
    svc: ContentService = Depends(get_content_service),
) -> list[ContentDetail]:
    status_enum = None
    if status:
        try:
            status_enum = ApprovalStatus(status)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Unknown status '{status}'")
    items = await svc.list_for_user(
        user_id=user.user_id,
        role=user.role,
        status=status_enum,
        brand_id=brand_id,
        limit=limit,
        offset=offset,
    )
    return [ContentDetail(**i) for i in items]


@router.get("/content/{content_id}", response_model=ContentDetail)
@limiter.limit("60/minute")
async def get_content(
    request: Request,
    content_id: UUID,
    user: AuthUser = Depends(get_current_user),
    svc: ContentService = Depends(get_content_service),
) -> ContentDetail:
    item = await svc.get(content_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Content item not found")
    if user.role == "creator" and item["creator_id"] != str(user.user_id):
        raise HTTPException(status_code=403, detail="Forbidden — not the creator of this item")
    return ContentDetail(**item)
