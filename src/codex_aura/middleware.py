"""Middleware for codex-aura FastAPI application."""

import time
from typing import Callable
from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from .logging import RequestContext, get_logger

logger = get_logger(__name__)


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Middleware to add request ID to all requests."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Add request ID to request context and response headers."""
        from .logging import generate_request_id

        request_id = generate_request_id()

        # Add to request state for access in handlers
        request.state.request_id = request_id

        # Set in response headers
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id

        return response


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware to log requests with structured logging."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Log request and response details."""
        start_time = time.time()

        # Get request ID from state (set by RequestIDMiddleware)
        request_id = getattr(request.state, 'request_id', 'unknown')

        with RequestContext(request_id):
            logger.info(
                "request_started",
                method=request.method,
                url=str(request.url),
                headers=dict(request.headers),
                client_ip=request.client.host if request.client else None,
            )

            try:
                response = await call_next(request)

                duration_ms = int((time.time() - start_time) * 1000)

                logger.info(
                    "request_completed",
                    status_code=response.status_code,
                    duration_ms=duration_ms,
                    response_headers=dict(response.headers),
                )

                return response

            except Exception as e:
                duration_ms = int((time.time() - start_time) * 1000)

                logger.error(
                    "request_failed",
                    error=str(e),
                    error_type=type(e).__name__,
                    duration_ms=duration_ms,
                )

                # Re-raise the exception
                raise