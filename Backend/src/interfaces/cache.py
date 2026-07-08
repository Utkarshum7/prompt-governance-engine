"""Abstract interface for caching providers."""

from abc import ABC, abstractmethod
from typing import Any, Optional


class ICache(ABC):
    """ICache defines the interface for key-value caching layers."""

    @abstractmethod
    async def get(self, key: str) -> Optional[Any]:
        """Get value from cache."""
        pass

    @abstractmethod
    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """Set value in cache with optional TTL."""
        pass

    @abstractmethod
    async def delete(self, key: str) -> bool:
        """Delete key from cache."""
        pass

    @abstractmethod
    async def exists(self, key: str) -> bool:
        """Check if key exists in cache."""
        pass

    @abstractmethod
    async def ping(self) -> bool:
        """Ping the cache provider for health check."""
        pass

    @abstractmethod
    async def close(self):
        """Close cache connection."""
        pass
