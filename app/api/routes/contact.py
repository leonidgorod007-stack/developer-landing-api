from __future__ import annotations

from fastapi import APIRouter, Depends, Request, status

from app.core.exceptions import RateLimitError
from app.dependencies import get_contact_service, get_rate_limiter
from app.models.schemas import ContactRequest, ContactResponse
from app.services.contact_service import ContactService
from app.services.rate_limiter import RateLimiter

router = APIRouter(tags=["contact"])


@router.post(
    "/contact",
    response_model=ContactResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit the contact form",
    responses={
        201: {"description": "Submission accepted and processed."},
        422: {"description": "Validation error."},
        429: {"description": "Rate limit exceeded."},
    },
)
async def submit_contact(
    payload: ContactRequest,
    request: Request,
    contact_service: ContactService = Depends(get_contact_service),
    rate_limiter: RateLimiter = Depends(get_rate_limiter),
) -> ContactResponse:
    client_ip = getattr(request.state, "client_ip", "unknown")

    allowed, retry_after = await rate_limiter.check(client_ip)
    if not allowed:
        raise RateLimitError(retry_after=retry_after)

    return await contact_service.handle_submission(payload, client_ip=client_ip)
