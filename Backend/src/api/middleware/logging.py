"""Request logging middleware."""

import time
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from structlog import get_logger

from src.utils.logging import get_logger as get_context_logger, set_request_id

logger = get_logger(__name__)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware for request/response logging."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Process request and log details.

        Args:
            request: HTTP request
            call_next: Next middleware/handler

        Returns:
            HTTP response
        """
        # Generate request ID
        request_id = set_request_id()

        # Get logger with context
        context_logger = get_context_logger()

        # Log request
        start_time = time.time()

        # Extract request details (excluding sensitive data)
        request_details = {
            "method": request.method,
            "path": request.url.path,
            "query_params": dict(request.query_params),
            "client": request.client.host if request.client else None,
        }

        # Remove sensitive query params
        sensitive_params = ["api_key", "token", "password"]
        request_details["query_params"] = {
            k: v if k not in sensitive_params else "***REDACTED***"
            for k, v in request_details["query_params"].items()
        }

        context_logger.info("Request received", **request_details)

        # Process request
        try:
            response = await call_next(request)
            process_time = time.time() - start_time

            # Log response
            context_logger.info(
                "Request completed",
                status_code=response.status_code,
                process_time_ms=round(process_time * 1000, 2),
            )

            # Add request ID to response headers
            response.headers["X-Request-ID"] = request_id

            return response

        except Exception as e:
            process_time = time.time() - start_time
            context_logger.error(
                "Request failed",
                error=str(e),
                error_type=type(e).__name__,
                process_time_ms=round(process_time * 1000, 2),
            )
            raise

