"""Qdrant client wrapper for vector database operations."""

import asyncio
from typing import List, Optional

import requests
from qdrant_client.models import PointStruct
from structlog import get_logger

from src.config.settings import get_settings

logger = get_logger(__name__)

# Collection configuration
COLLECTION_NAME = "prompt_embeddings"
VECTOR_SIZE = 1536  # text-embedding-3-small dimension


# Synchronous Qdrant client wrapper removed - using HTTP requests instead
class AsyncQdrantClientWrapper:
    """Async wrapper for Qdrant client using HTTP requests."""

    def __init__(self):
        """Initialize async Qdrant client wrapper using HTTP requests."""
        settings = get_settings()
        qdrant_config = settings.database.vector_db.qdrant

        if not qdrant_config:
            raise ValueError("Qdrant configuration not found")

        # Use IP address directly to avoid DNS resolution issues
        host = qdrant_config.host
        if host == "127.0.0.1" or host == "localhost":
            host = "127.0.0.1"  # Force IPv4
        self.base_url = f"http://{host}:{qdrant_config.port}"
        self.api_key = qdrant_config.api_key
        self.session = requests.Session()
        self.session.timeout = 30.0

        logger.info(
            "Async Qdrant HTTP client initialized",
            base_url=self.base_url,
        )

    async def ensure_collection(self) -> bool:
        """
        Ensure collection exists with correct configuration.

        Returns:
            True if collection exists or was created, False otherwise
        """
        max_retries = 3
        for attempt in range(max_retries):
            try:
                # Check if collection exists
                headers = {}
                if self.api_key:
                    headers["api-key"] = self.api_key

                response = await asyncio.to_thread(
                    self.session.get,
                    f"{self.base_url}/collections/{COLLECTION_NAME}",
                    headers=headers
                )
                if response.status_code == 200:
                    logger.info("Collection already exists", collection=COLLECTION_NAME)
                    return True

                # Create collection
                logger.info("Creating collection", collection=COLLECTION_NAME, attempt=attempt+1)

                collection_config = {
                    "vectors": {
                        "size": VECTOR_SIZE,
                        "distance": "Cosine"
                    },
                    "hnsw_config": {
                        "m": 16,
                        "ef_construct": 100
                    },
                    "optimizers_config": {
                        "indexing_threshold": 10000
                    }
                }

                headers = {"Content-Type": "application/json"}
                if self.api_key:
                    headers["api-key"] = self.api_key

                response = await asyncio.to_thread(
                    self.session.put,
                    f"{self.base_url}/collections/{COLLECTION_NAME}",
                    json=collection_config,
                    headers=headers
                )

                if response.status_code in [200, 201]:
                    logger.info("Collection created successfully", collection=COLLECTION_NAME)
                    return True
                else:
                    logger.error("Failed to create collection", status=response.status_code, response=response.text)

            except Exception as e:
                logger.warning("Error ensuring collection", error=str(e), collection=COLLECTION_NAME, attempt=attempt+1)
                if attempt < max_retries - 1:
                    await asyncio.sleep(2)  # Wait before retry
                else:
                    logger.error("Failed to ensure collection after retries", error=str(e), collection=COLLECTION_NAME)
                    return False

        return False

    async def get_collection_info(self) -> Optional[dict]:
        """
        Get collection information.

        Returns:
            Collection info dictionary or None if collection doesn't exist
        """
        try:
            info = await self.client.get_collection(COLLECTION_NAME)
            return {
                "name": info.name,
                "vectors_count": info.vectors_count,
                "points_count": info.points_count,
                "status": info.status,
            }
        except Exception as e:
            logger.error("Error getting collection info", error=str(e))
            return None

    async def upsert_points(self, points: List[PointStruct]) -> bool:
        """
        Upsert points into collection.

        Args:
            points: List of PointStruct objects

        Returns:
            True if successful, False otherwise
        """
        try:
            # Ensure collection exists before upserting
            await self.ensure_collection()

            # Convert points to dict format for HTTP API
            points_data = []
            for point in points:
                if isinstance(point, dict):
                    # Already in dict format
                    points_data.append(point)
                else:
                    # Handle PointStruct or other formats
                    point_id = getattr(point, 'id', None)
                    vector = getattr(point, 'vector', None)
                    payload = getattr(point, 'payload', None) or {}

                    if point_id is None or vector is None:
                        logger.error("Invalid point format", point_type=type(point), point_attrs=dir(point) if hasattr(point, '__dict__') else 'no attrs')
                        continue

                    point_dict = {
                        "id": str(point_id),
                        "vector": vector,
                        "payload": payload
                    }
                    points_data.append(point_dict)

            if not points_data:
                logger.error("No valid points to upsert")
                return False

            request_data = {"points": points_data}
            logger.info("Upsert request data", points_data_sample=points_data[0] if points_data else None, payload_sample=points_data[0].get('payload') if points_data else None)

            headers = {"Content-Type": "application/json"}
            if self.api_key:
                headers["api-key"] = self.api_key

            response = await asyncio.to_thread(
                self.session.put,
                f"{self.base_url}/collections/{COLLECTION_NAME}/points",
                json=request_data,
                headers=headers,
                timeout=10.0
            )

            if response.status_code in [200, 201]:
                return True
            else:
                logger.error("Failed to upsert points", status=response.status_code, response=response.text[:500])
                raise Exception(f"Upsert failed: {response.status_code} - {response.text[:500]}")

        except Exception as e:
            logger.error("Error upserting points", error=str(e), count=len(points))
            raise

    async def search(
        self,
        query_vector: List[float],
        limit: int = 10,
        score_threshold: Optional[float] = None,
    ) -> List[dict]:
        """
        Search for similar vectors.

        Args:
            query_vector: Query embedding vector
            limit: Maximum number of results
            score_threshold: Optional minimum similarity score

        Returns:
            List of search results with id and score
        """
        try:
            # Ensure collection exists
            await self.ensure_collection()

            search_data = {
                "vector": query_vector,
                "limit": limit,
                "with_payload": True
            }
            if score_threshold is not None:
                search_data["score_threshold"] = score_threshold

            headers = {"Content-Type": "application/json"}
            if self.api_key:
                headers["api-key"] = self.api_key

            response = await asyncio.to_thread(
                self.session.post,
                f"{self.base_url}/collections/{COLLECTION_NAME}/points/search",
                json=search_data,
                headers=headers
            )

            if response.status_code == 200:
                response_data = response.json()
                results = [
                    {
                        "id": hit["id"],
                        "score": hit["score"],
                        "payload": hit.get("payload", {}),
                    }
                    for hit in response_data.get("result", [])
                ]

                return results
            else:
                logger.error("Search failed", status=response.status_code, response=response.text)
                return []

        except Exception as e:
            logger.error("Error searching Qdrant", error=str(e), query_vector_dim=len(query_vector), limit=limit, score_threshold=score_threshold)
            return []

    async def delete_points(self, point_ids: List[str]) -> bool:
        """
        Delete points from collection.

        Args:
            point_ids: List of point IDs to delete

        Returns:
            True if successful, False otherwise
        """
        try:
            await self.client.delete(
                collection_name=COLLECTION_NAME,
                points_selector=point_ids,
            )
            logger.debug("Points deleted", count=len(point_ids), collection=COLLECTION_NAME)
            return True
        except Exception as e:
            logger.error("Error deleting points", error=str(e), count=len(point_ids))
            return False


# Global client instances
_async_qdrant_client: Optional[AsyncQdrantClientWrapper] = None


def get_async_qdrant_client() -> AsyncQdrantClientWrapper:
    """
    Get global async Qdrant client instance.

    Returns:
        AsyncQdrantClientWrapper instance
    """
    global _async_qdrant_client
    if _async_qdrant_client is None:
        _async_qdrant_client = AsyncQdrantClientWrapper()
    return _async_qdrant_client

