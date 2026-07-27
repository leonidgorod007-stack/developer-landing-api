"""GET /api/metrics — aggregate submission statistics (read from file)."""
from __future__ import annotations

from fastapi import APIRouter, Depends

from app.dependencies import get_metrics_repository
from app.models.schemas import MetricsResponse
from app.repositories.metrics_repository import MetricsRepository

router = APIRouter(tags=["system"])


@router.get("/metrics", response_model=MetricsResponse, summary="Submission statistics")
async def metrics(
    repo: MetricsRepository = Depends(get_metrics_repository),
) -> MetricsResponse:
    data = await repo.read()
    return MetricsResponse(**data)
