"""Brand DNA routes — Module I."""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse

from ...application.brand_service import BrandService
from ..dependencies import get_brand_service
from ..middleware.auth import AuthUser
from ..middleware.rate_limit import limiter
from ..middleware.rbac import require_roles
from ..schemas import BrandDNARequest

router = APIRouter(prefix="/api/v1", tags=["brand"])


@router.post("/brand-dna")
@limiter.limit("5/minute")
async def create_brand_dna(
    request: Request,
    payload: BrandDNARequest,
    user: AuthUser = Depends(require_roles("creator")),
    svc: BrandService = Depends(get_brand_service),
) -> JSONResponse:
    result = await svc.create_brand_manual(
        user_id=user.user_id,
        payload=payload.model_dump(),
    )
    return JSONResponse(content=result)


@router.get("/brands")
@limiter.limit("60/minute")
async def list_brands(
    request: Request,
    user: AuthUser = Depends(require_roles("creator")),
    svc: BrandService = Depends(get_brand_service),
) -> JSONResponse:
    items = await svc.list_brands(user.user_id)
    return JSONResponse(content=items)


@router.get("/brands/{brand_id}")
@limiter.limit("60/minute")
async def get_brand(
    request: Request,
    brand_id: UUID,
    user: AuthUser = Depends(require_roles("creator")),
    svc: BrandService = Depends(get_brand_service),
) -> JSONResponse:
    brand = await svc.get_brand(user_id=user.user_id, brand_id=brand_id)
    if brand is None:
        raise HTTPException(status_code=404, detail="Brand not found")
    return JSONResponse(content=brand)
