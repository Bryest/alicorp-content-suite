"""Health + system info."""


from datetime import datetime, timezone

from fastapi import APIRouter

from ...config import get_settings
from ..schemas import HealthResponse

router = APIRouter(prefix="/api/v1", tags=["system"])


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    settings = get_settings()
    return HealthResponse(
        status="ok",
        version="1.0.0",
        timestamp=datetime.now(timezone.utc).isoformat(),
        environment=settings.environment,
    )
