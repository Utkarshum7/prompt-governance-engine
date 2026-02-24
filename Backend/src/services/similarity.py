"""Vector similarity search service using Qdrant."""

from typing import List, Optional

from structlog import get_logger

from src.clients.qdrant import AsyncQdrantClientWrapper, get_async_qdrant_client
from src.config.settings import get_settings

logger = get_logger(__name__)


class SimilarityService:
    """Service for finding similar prompts using vector search."""

    def __init__(self, qdrant_client: Optional[AsyncQdrantClientWrapper] = None):
        """
        Initialize similarity service.

        Args:
            qdrant_client: Optional AsyncQdrantClientWrapper instance
        """
        self.qdrant_client = qdrant_client or get_async_qdrant_client()
        settings = get_settings()
        self.similarity_threshold = settings.app.clustering.similarity_threshold

        logger.info(
            "Similarity service initialized",
            similarity_threshold=self.similarity_threshold,
        )

    async def find_similar(
        self,
        embedding: List[float],
        limit: int = 10,
        similarity_threshold: Optional[float] = None,
    ) -> List[dict]:
        """
        Find similar prompts using approximate nearest neighbor search.

        Args:
            embedding: Query embedding vector
            limit: Maximum number of results
            similarity_threshold: Optional minimum similarity score override

        Returns:
            List of similar prompts with id, score, and payload
        """
        try:
            # Ensure collection exists before searching
            await self.qdrant_client.ensure_collection()
            
            threshold = similarity_threshold or self.similarity_threshold

            logger.debug(
                "Searching for similar prompts",
                embedding_dim=len(embedding),
                limit=limit,
                threshold=threshold,
            )

            results = await self.qdrant_client.search(
                query_vector=embedding,
                limit=limit,
                score_threshold=threshold,
            )

            logger.debug(
                "Similarity search completed",
                results_count=len(results),
                threshold=threshold,
            )

            return results

        except Exception as e:
            logger.error("Error in similarity search", error=str(e), embedding_dim=len(embedding), limit=limit, threshold=threshold)
            return []

    async def find_top_k_similar(
        self,
        embedding: List[float],
        k: int = 5,
        similarity_threshold: Optional[float] = None,
    ) -> List[dict]:
        """
        Find top-k most similar prompts.

        Args:
            embedding: Query embedding vector
            k: Number of top results
            similarity_threshold: Optional minimum similarity score override

        Returns:
            List of top-k similar prompts sorted by score (descending)
        """
        results = await self.find_similar(embedding, limit=k, similarity_threshold=similarity_threshold)

        # Sort by score descending (Qdrant already returns sorted, but ensure)
        results.sort(key=lambda x: x["score"], reverse=True)

        return results[:k]

    async def find_best_match(
        self,
        embedding: List[float],
        similarity_threshold: Optional[float] = None,
    ) -> Optional[dict]:
        """
        Find the best matching prompt.

        Args:
            embedding: Query embedding vector
            similarity_threshold: Optional minimum similarity score override

        Returns:
            Best match dictionary or None if no match above threshold
        """
        results = await self.find_top_k_similar(embedding, k=1, similarity_threshold=similarity_threshold)

        if results:
            return results[0]

        return None

    async def find_cluster_candidates(
        self,
        embedding: List[float],
        similarity_threshold: Optional[float] = None,
    ) -> List[dict]:
        """
        Find cluster candidates for a prompt.

        Args:
            embedding: Query embedding vector
            similarity_threshold: Optional minimum similarity score override

        Returns:
            List of cluster candidates with scores
        """
        # Search for similar prompts
        similar_prompts = await self.find_similar(
            embedding, limit=20, similarity_threshold=similarity_threshold
        )

        # Group by cluster_id if available in payload
        cluster_scores = {}
        for result in similar_prompts:
            payload = result.get("payload", {})
            cluster_id = payload.get("cluster_id")

            if cluster_id:
                if cluster_id not in cluster_scores:
                    cluster_scores[cluster_id] = {
                        "cluster_id": cluster_id,
                        "max_score": result["score"],
                        "prompt_count": 0,
                        "prompt_ids": [],
                    }

                cluster_scores[cluster_id]["max_score"] = max(
                    cluster_scores[cluster_id]["max_score"], result["score"]
                )
                cluster_scores[cluster_id]["prompt_count"] += 1
                cluster_scores[cluster_id]["prompt_ids"].append(result["id"])

        # Convert to list and sort by max_score
        candidates = list(cluster_scores.values())
        candidates.sort(key=lambda x: x["max_score"], reverse=True)

        logger.debug(
            "Found cluster candidates",
            candidates_count=len(candidates),
            threshold=similarity_threshold or self.similarity_threshold,
        )

        return candidates


# Global similarity service instance
_similarity_service: Optional[SimilarityService] = None


def get_similarity_service() -> SimilarityService:
    """
    Get global similarity service instance.

    Returns:
        SimilarityService instance
    """
    global _similarity_service
    if _similarity_service is None:
        _similarity_service = SimilarityService()
    return _similarity_service

