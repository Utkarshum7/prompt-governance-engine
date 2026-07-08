"""Abstract interface for vector database providers."""

from abc import ABC, abstractmethod
from typing import Any, List, Optional


class IVectorDBProvider(ABC):
    """IVectorDBProvider defines the interface for vector operations (Qdrant, Pinecone, etc.)."""

    @abstractmethod
    async def ensure_collection(self) -> bool:
        """Ensure the vector collection/index exists."""
        pass

    @abstractmethod
    async def get_collection_info(self) -> Optional[dict]:
        """Retrieve index/collection statistics."""
        pass

    @abstractmethod
    async def upsert_points(self, points: List[Any]) -> bool:
        """Upsert vectors into index."""
        pass

    @abstractmethod
    async def search(
        self,
        query_vector: List[float],
        limit: int = 10,
        score_threshold: Optional[float] = None,
    ) -> List[dict]:
        """Search similar vectors in the index."""
        pass

    @abstractmethod
    async def delete_points(self, point_ids: List[str]) -> bool:
        """Delete vectors from index."""
        pass
