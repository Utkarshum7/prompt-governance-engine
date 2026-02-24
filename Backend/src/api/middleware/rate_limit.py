"""Rate limiting middleware using Redis."""

import time
from typing import Optional

from fastapi import HTTPException, Request, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
from structlog import get_logger

from src.clients.redis import RedisClient, get_redis_client
from src.config.settings import get_settings

logger = get_logger(__name__)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Middleware for rate limiting using Redis."""

    def __init__(self, app, redis_client: Optional[RedisClient] = None):
        """
        Initialize rate limiting middleware.

        Args:
            app: ASGI application
            redis_client: Optional RedisClient instance
        """
        super().__init__(app)
        self.redis_client = redis_client or get_redis_client()
        settings = get_settings()
        self.default_limit = settings.app.api.rate_limit_per_minute

    def _get_rate_limit_key(self, identifier: str, endpoint: str) -> str:
        """
        Generate rate limit key.

        Args:
            identifier: API key or IP address
            endpoint: Endpoint path

        Returns:
            Redis key for rate limit
        """
        return f"rate_limit:{identifier}:{endpoint}"

    async def dispatch(self, request: Request, call_next):
        """
        Process request and enforce rate limits.

        Args:
            request: HTTP request
            call_next: Next middleware/handler

        Returns:
            HTTP response with rate limit headers

        Raises:
            HTTPException: If rate limit exceeded
        """
        # Skip rate limiting for health checks and docs
        if request.url.path in ["/health", "/health/ready", "/docs", "/redoc", "/openapi.json", "/"]:
            return await call_next(request)

        # Get identifier (IP address)
        identifier = request.client.host
        endpoint = request.url.path

        # Get rate limit key
        rate_limit_key = self._get_rate_limit_key(identifier, endpoint)

        # Get current count
        current_count = await self.redis_client.get(rate_limit_key)

        if current_count is None:
            # First request, set counter
            await self.redis_client.set(rate_limit_key, 1, ttl=60)  # 1 minute window
            remaining = self.default_limit - 1
        else:
            count = int(current_count) if isinstance(current_count, (int, str)) else 0

            if count >= self.default_limit:
                logger.warning(
                    "Rate limit exceeded",
                    identifier=identifier[:8] + "..." if len(identifier) > 8 else identifier,
                    endpoint=endpoint,
                    count=count,
                )
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail={
                        "error": "Rate limit exceeded",
                        "limit": self.default_limit,
                        "window": "1 minute",
                    },
                    headers={
                        "X-RateLimit-Limit": str(self.default_limit),
                        "X-RateLimit-Remaining": "0",
                        "Retry-After": "60",
                    },
                )

            # Increment counter
            await self.redis_client.set(rate_limit_key, count + 1, ttl=60)
            remaining = self.default_limit - count - 1

        # Process request
        response = await call_next(request)

        # Add rate limit headers
        response.headers["X-RateLimit-Limit"] = str(self.default_limit)
        response.headers["X-RateLimit-Remaining"] = str(remaining)

        return response

