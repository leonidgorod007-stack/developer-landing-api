"""
Request logging middleware.

Logs every incoming HTTP request to the file/console configured in
`logging_config`, including method, path, status code, duration and the
client IP. A per-request id is attached so a single request can be traced
across log lines and returned to the client via the `X-Request-ID` header.
"""
from __future__ import annotations

import logging
import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger("app.requests")


def client_ip(request: Request) -> str:
    """Best-effort client IP, honouring a reverse proxy's X-Forwarded-For."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = uuid.uuid4().hex[:12]
        request.state.request_id = request_id
        request.state.client_ip = client_ip(request)

        start = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            # The global exception handler builds the response; we still log timing.
            elapsed_ms = (time.perf_counter() - start) * 1000
            logger.error(
                'id=%s ip=%s "%s %s" -> ERROR %.1fms',
                request_id, request.state.client_ip,
                request.method, request.url.path, elapsed_ms,
            )
            raise

        elapsed_ms = (time.perf_counter() - start) * 1000
        logger.info(
            'id=%s ip=%s "%s %s" -> %d %.1fms',
            request_id, request.state.client_ip,
            request.method, request.url.path, response.status_code, elapsed_ms,
        )
        response.headers["X-Request-ID"] = request_id
        return response
