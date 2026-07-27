"""GET /api/health — liveness + dependency status."""
from __future__ import annotations

import time

from fastapi import APIRouter, Request

from app import __version__
from app.dependencies import get_container
from app.models.schemas import HealthResponse

router = APIRouter(tags=["system"])

_STARTED_AT = time.time()


@router.get("/health", response_model=HealthResponse, summary="Service health check")
async def health(request: Request) -> HealthResponse:
    container = get_container(request)
    s = container.settings
    return HealthResponse(
        app=s.app_name,
        version=__version__,
        uptime_seconds=round(time.time() - _STARTED_AT, 1),
        dependencies={
            "ai": "live" if container.ai_service.available else "fallback",
            "email": "smtp" if s.email_configured else "console",
        },
    )
