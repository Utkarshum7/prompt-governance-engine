"""Redis client wrapper for caching."""

import json
from typing import Any, Optional

from redis.asyncio import Redis
from structlog import get_logger

from src.config.settings import get_settings

logger = get_logger(__name__)


class RedisClient:
    """Redis client wrapper for caching operations."""

    def __init__(self, redis_client: Optional[Redis] = None):
        """
        Initialize Redis client.

        Args:
            redis_client: Optional Redis instance. If None, creates a new one.
        """
        self._client: Optional[Redis] = redis_client
        self._settings = get_settings()

    async def _get_client(self) -> Redis:
        """Get or create Redis client."""
        if self._client is None:
            redis_config = self._settings.database.redis
            self._client = Redis.from_url(
                f"redis://{redis_config.host}:{redis_config.port}",
                password=redis_config.password or None,
                db=redis_config.db,
                decode_responses=redis_config.decode_responses,
            )
            logger.info("Redis client initialized", host=redis_config.host, port=redis_config.port)
        return self._client

    async def get(self, key: str) -> Optional[Any]:
        """
        Get value from Redis.

        Args:
            key: Cache key

        Returns:
            Cached value or None if not found
        """
        try:
            client = await self._get_client()
            value = await client.get(key)
            if value is None:
                logger.debug("Cache miss", key=key)
                return None

            logger.debug("Cache hit", key=key)
            # Try to parse as JSON, fallback to string
            try:
                return json.loads(value)
            except (json.JSONDecodeError, TypeError):
                return value

        except Exception as e:
            logger.error("Redis get error", key=key, error=str(e))
            return None

    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """
        Set value in Redis.

        Args:
            key: Cache key
            value: Value to cache
            ttl: Time to live in seconds

        Returns:
            True if successful, False otherwise
        """
        try:
            client = await self._get_client()
            # Serialize value to JSON if it's not a string
            if not isinstance(value, str):
                serialized_value = json.dumps(value)
            else:
                serialized_value = value

            if ttl:
                result = await client.setex(key, ttl, serialized_value)
            else:
                result = await client.set(key, serialized_value)

            logger.debug("Cache set", key=key, ttl=ttl)
            return bool(result)

        except Exception as e:
            logger.error("Redis set error", key=key, error=str(e))
            return False

    async def delete(self, key: str) -> bool:
        """
        Delete key from Redis.

        Args:
            key: Cache key

        Returns:
            True if successful, False otherwise
        """
        try:
            client = await self._get_client()
            result = await client.delete(key)
            logger.debug("Cache delete", key=key)
            return bool(result)

        except Exception as e:
            logger.error("Redis delete error", key=key, error=str(e))
            return False

    async def exists(self, key: str) -> bool:
        """
        Check if key exists in Redis.

        Args:
            key: Cache key

        Returns:
            True if key exists, False otherwise
        """
        try:
            client = await self._get_client()
            result = await client.exists(key)
            return bool(result)

        except Exception as e:
            logger.error("Redis exists error", key=key, error=str(e))
            return False

    async def ping(self) -> bool:
        """
        Ping Redis server.

        Returns:
            True if Redis is reachable
        """
        try:
            client = await self._get_client()
            result = await client.ping()
            return bool(result)
        except Exception as e:
            logger.error("Redis ping error", error=str(e))
            return False

    async def close(self):
        """Close Redis connection."""
        if self._client:
            await self._client.aclose()
            self._client = None
            logger.info("Redis client closed")


# Global Redis client instance
_redis_client: Optional[RedisClient] = None


def get_redis_client() -> RedisClient:
    """
    Get global Redis client instance.

    Returns:
        RedisClient instance
    """
    global _redis_client
    if _redis_client is None:
        _redis_client = RedisClient()
    return _redis_client
