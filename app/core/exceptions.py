"""
Domain exceptions and the global error handlers.

Business logic raises these typed exceptions; the handlers registered in
`register_exception_handlers` translate them into consistent JSON error
responses with the right HTTP status code. This keeps status-code decisions
out of the service layer and guarantees a uniform error envelope.
"""
from __future__ import annotations

import logging

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger("app.errors")


class AppError(Exception):
    """Base class for all expected, handled application errors."""

    status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR
    error_code: str = "internal_error"
    message: str = "An unexpected error occurred."

    def __init__(self, message: str | None = None, *, details: object | None = None):
        super().__init__(message or self.message)
        if message:
            self.message = message
        self.details = details


class RateLimitError(AppError):
    status_code = status.HTTP_429_TOO_MANY_REQUESTS
    error_code = "rate_limited"
    message = "Too many requests. Please try again later."

    def __init__(self, retry_after: int, message: str | None = None):
        super().__init__(message)
        self.retry_after = retry_after


class EmailDeliveryError(AppError):
    status_code = status.HTTP_502_BAD_GATEWAY
    error_code = "email_delivery_failed"
    message = "The message was accepted but the notification email could not be sent."


def _error_body(error_code: str, message: str, details: object | None = None) -> dict:
    body: dict = {"error": {"code": error_code, "message": message}}
    if details is not None:
        body["error"]["details"] = details
    return body


def register_exception_handlers(app: FastAPI) -> None:
    """Attach global handlers so every error path returns a uniform envelope."""

    @app.exception_handler(AppError)
    async def _app_error_handler(request: Request, exc: AppError) -> JSONResponse:
        logger.warning(
            "AppError [%s] on %s %s: %s",
            exc.error_code, request.method, request.url.path, exc.message,
        )
        headers = {}
        if isinstance(exc, RateLimitError):
            headers["Retry-After"] = str(exc.retry_after)
        return JSONResponse(
            status_code=exc.status_code,
            content=_error_body(exc.error_code, exc.message, exc.details),
            headers=headers,
        )

    @app.exception_handler(RequestValidationError)
    async def _validation_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        # Flatten pydantic errors into a compact, client-friendly list.
        details = [
            {
                "field": ".".join(str(p) for p in err["loc"] if p != "body"),
                "message": err["msg"],
            }
            for err in exc.errors()
        ]
        logger.info("Validation error on %s %s: %s", request.method, request.url.path, details)
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=_error_body(
                "validation_error", "One or more fields are invalid.", details
            ),
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http_handler(
        request: Request, exc: StarletteHTTPException
    ) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=_error_body("http_error", str(exc.detail)),
        )

    @app.exception_handler(Exception)
    async def _unhandled_handler(request: Request, exc: Exception) -> JSONResponse:
        # Last line of defence: never leak a stack trace to the client.
        logger.exception(
            "Unhandled error on %s %s", request.method, request.url.path
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=_error_body("internal_error", "An unexpected error occurred."),
        )
