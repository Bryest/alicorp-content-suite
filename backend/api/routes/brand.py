"""Brand DNA routes — Module I."""

from fastapi import APIRouter, Depends, Request

from ...application.brand_service import BrandService
from ..dependencies import get_brand_service
from ..middleware.auth import AuthUser
from ..middleware.rate_limit import limiter
from ..middleware.rbac import require_roles
from ..schemas import BrandDNARequest, BrandDNAResponse, BrandSummary

router = APIRouter(prefix="/api/v1", tags=["brand"])


@router.post("/brand-dna", response_model=BrandDNAResponse)
@limiter.limit("5/minute")
async def create_brand_dna(
    request: Request,
    payload: BrandDNARequest,
    user: AuthUser = Depends(require_roles("creator")),
    svc: BrandService = Depends(get_brand_service),
) -> BrandDNAResponse:
    result = await svc.create_brand_manual(
        user_id=user.user_id,
        payload=payload.model_dump(),
    )
    return BrandDNAResponse(**result)


@router.get("/brands", response_model=list[BrandSummary])
@limiter.limit("60/minute")
async def list_brands(
    request: Request,
    user: AuthUser = Depends(require_roles("creator")),
    svc: BrandService = Depends(get_brand_service),
) -> list[BrandSummary]:
    items = await svc.list_brands(user.user_id)
    return [BrandSummary(**i) for i in items]
