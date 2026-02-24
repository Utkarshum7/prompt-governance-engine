"""Clustering service for semantic similarity-based grouping."""

import uuid
from typing import Any, Dict, List, Optional, Tuple

from qdrant_client.models import PointStruct
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from structlog import get_logger

from src.clients.qdrant import AsyncQdrantClientWrapper, get_async_qdrant_client
from src.clients.redis import RedisClient, get_redis_client
from src.config.settings import get_settings
from src.models.database import Cluster, ClusterAssignment, Prompt
from src.services.similarity import SimilarityService, get_similarity_service

logger = get_logger(__name__)

# Cache TTL: 1 day in seconds
SIMILARITY_CACHE_TTL = 24 * 60 * 60


class ClusteringService:
    """Service for semantic similarity-based clustering."""

    def __init__(
        self,
        db: AsyncSession,
        similarity_service: Optional[SimilarityService] = None,
        qdrant_client: Optional[AsyncQdrantClientWrapper] = None,
        redis_client: Optional[RedisClient] = None,
    ):
        """
        Initialize clustering service.

        Args:
            db: Database session
            similarity_service: Optional SimilarityService instance
            qdrant_client: Optional AsyncQdrantClientWrapper instance
            redis_client: Optional RedisClient instance
        """
        self.db = db
        self.similarity_service = similarity_service or get_similarity_service()
        self.qdrant_client = qdrant_client or get_async_qdrant_client()
        self.redis_client = redis_client or get_redis_client()

        settings = get_settings()
        self.similarity_threshold = settings.app.clustering.similarity_threshold
        self.confidence_threshold = settings.app.clustering.confidence_threshold

        logger.info(
            "Clustering service initialized",
            similarity_threshold=self.similarity_threshold,
            confidence_threshold=self.confidence_threshold,
        )

    def _get_cache_key(self, prompt_id: str, cluster_id: str) -> str:
        """
        Generate cache key for similarity score.

        Args:
            prompt_id: Prompt ID
            cluster_id: Cluster ID

        Returns:
            Cache key
        """
        return f"similarity:{prompt_id}:{cluster_id}"

    async def _get_cached_similarity(
        self, prompt_id: str, cluster_id: str
    ) -> Optional[float]:
        """
        Get cached similarity score.

        Args:
            prompt_id: Prompt ID
            cluster_id: Cluster ID

        Returns:
            Cached similarity score or None
        """
        cache_key = self._get_cache_key(prompt_id, cluster_id)
        cached = await self.redis_client.get(cache_key)
        if cached:
            logger.debug("Similarity cache hit", prompt_id=prompt_id, cluster_id=cluster_id)
            return cached.get("score")
        return None

    async def _cache_similarity(
        self, prompt_id: str, cluster_id: str, score: float
    ) -> None:
        """
        Cache similarity score.

        Args:
            prompt_id: Prompt ID
            cluster_id: Cluster ID
            score: Similarity score
        """
        cache_key = self._get_cache_key(prompt_id, cluster_id)
        cache_value = {"score": score, "prompt_id": prompt_id, "cluster_id": cluster_id}
        await self.redis_client.set(cache_key, cache_value, ttl=SIMILARITY_CACHE_TTL)
        logger.debug("Similarity cached", prompt_id=prompt_id, cluster_id=cluster_id, score=score)

    async def _calculate_similarity_to_cluster(
        self, embedding: List[float], cluster_id: uuid.UUID
    ) -> Optional[float]:
        """
        Calculate similarity between embedding and cluster centroid.

        Args:
            embedding: Prompt embedding vector
            cluster_id: Cluster ID

        Returns:
            Similarity score or None
        """
        # Get cluster from database
        cluster = await self.db.get(Cluster, cluster_id)
        if not cluster or not cluster.centroid_embedding_id:
            return None

        # Search for similar prompts in this cluster
        # Use Qdrant payload filter to search within cluster
        results = await self.qdrant_client.search(
            query_vector=embedding,
            limit=1,
            score_threshold=self.similarity_threshold,
        )

        # Filter results by cluster_id in payload
        for result in results:
            payload = result.get("payload", {})
            if payload.get("cluster_id") == str(cluster_id):
                return result["score"]

        return None

    async def _find_best_cluster(
        self, embedding: List[float], prompt_id: uuid.UUID
    ) -> Optional[Tuple[uuid.UUID, float]]:
        """
        Find the best matching cluster for an embedding.

        Args:
            embedding: Prompt embedding vector
            prompt_id: Prompt ID

        Returns:
            Tuple of (cluster_id, similarity_score) or None if no match
        """
        # Ensure Qdrant collection exists before searching
        await self.qdrant_client.ensure_collection()

        # Find similar prompts - use lower threshold for search, then filter
        # This ensures we find all potential matches even if slightly below threshold
        # For identical prompts, similarity should be ~1.0, so we use a very low threshold
        # to catch all potential matches
        similar_prompts = await self.similarity_service.find_similar(
            embedding, limit=50, similarity_threshold=0.5  # Very low threshold to find all candidates
        )

        if not similar_prompts:
            logger.debug("No similar prompts found in Qdrant", prompt_id=str(prompt_id))
            return None

        # Group by cluster_id and find best match
        cluster_scores = {}
        for result in similar_prompts:
            payload = result.get("payload", {})
            cluster_id_str = payload.get("cluster_id")

            if cluster_id_str:
                try:
                    cluster_id = uuid.UUID(cluster_id_str)
                    if cluster_id not in cluster_scores:
                        cluster_scores[cluster_id] = []

                    cluster_scores[cluster_id].append(result["score"])
                except ValueError:
                    continue

        if not cluster_scores:
            return None

        # Find cluster with highest average similarity
        best_cluster_id = None
        best_score = 0.0

        for cluster_id, scores in cluster_scores.items():
            # Use MAX score instead of average - this ensures identical prompts match
            # even if there are other prompts in the cluster with lower similarity
            max_score = max(scores)

            # Check cache first
            cached_score = await self._get_cached_similarity(str(prompt_id), str(cluster_id))
            if cached_score:
                final_score = cached_score
            else:
                final_score = max_score
                # Cache the result
                await self._cache_similarity(str(prompt_id), str(cluster_id), final_score)

            if final_score > best_score:
                best_score = final_score
                best_cluster_id = cluster_id

        # Only return if above threshold
        if best_cluster_id and best_score >= self.similarity_threshold:
            logger.info(
                "Found matching cluster",
                prompt_id=str(prompt_id),
                cluster_id=str(best_cluster_id),
                similarity_score=best_score,
                threshold=self.similarity_threshold,
            )
            return (best_cluster_id, best_score)

        logger.debug(
            "No cluster above threshold",
            prompt_id=str(prompt_id),
            best_score=best_score if best_cluster_id else 0.0,
            threshold=self.similarity_threshold,
            clusters_found=len(cluster_scores),
        )
        return None

    async def _create_new_cluster(
        self, prompt_id: uuid.UUID, embedding: List[float]
    ) -> Cluster:
        """
        Create a new cluster for a prompt.

        Args:
            prompt_id: Prompt ID
            embedding: Prompt embedding vector

        Returns:
            Created Cluster object
        """
        cluster_id = uuid.uuid4()

        cluster = Cluster(
            id=cluster_id,
            name=f"Cluster-{cluster_id.hex[:8]}",
            centroid_embedding_id=prompt_id,
            similarity_threshold=self.similarity_threshold,
            confidence_score=1.0,  # New cluster has high confidence
        )

        self.db.add(cluster)
        await self.db.flush()

        logger.info("Created new cluster", cluster_id=cluster_id, prompt_id=prompt_id)

        return cluster

    async def _find_exact_content_match(
        self, prompt_content: str, current_prompt_id: uuid.UUID
    ) -> Optional[Tuple[uuid.UUID, float]]:
        """
        Find existing prompt with exact same content.

        Args:
            prompt_content: The prompt content to match
            current_prompt_id: Current prompt ID (to exclude self-match)

        Returns:
            Tuple of (cluster_id, similarity_score) or None if no exact match
        """
        # Query database for prompts with exact content match
        stmt = select(Prompt, ClusterAssignment.cluster_id).join(
            ClusterAssignment, Prompt.id == ClusterAssignment.prompt_id
        ).where(
            and_(
                Prompt.content == prompt_content,
                Prompt.id != current_prompt_id  # Exclude current prompt
            )
        ).limit(1)

        result = await self.db.execute(stmt)
        row = result.first()

        if row:
            prompt, cluster_id = row
            return (cluster_id, 1.0)  # Perfect similarity score for exact match

        return None

    def _generate_reasoning(
        self, similarity_score: float, cluster_id: uuid.UUID, is_new: bool = False
    ) -> str:
        """
        Generate reasoning for cluster assignment.

        Args:
            similarity_score: Similarity score
            cluster_id: Cluster ID
            is_new: Whether this is a new cluster

        Returns:
            Reasoning string
        """
        if is_new:
            return (
                f"Created new cluster {cluster_id} because no existing cluster "
                f"matched similarity threshold ({self.similarity_threshold})"
            )

        return (
            f"Assigned to cluster {cluster_id} with similarity score {similarity_score:.3f} "
            f"(threshold: {self.similarity_threshold})"
        )

    async def assign_to_cluster(
        self,
        prompt_id: uuid.UUID,
        embedding: List[float],
        prompt_content: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Assign a prompt to a cluster (existing or new).

        Args:
            prompt_id: Prompt ID
            embedding: Prompt embedding vector
            prompt_content: Optional prompt content for logging

        Returns:
            Assignment result dictionary
        """
        try:
            logger.debug("Assigning prompt to cluster", prompt_id=prompt_id)

            # First, check for exact string match with existing prompts
            if prompt_content:
                exact_match = await self._find_exact_content_match(prompt_content, prompt_id)
                if exact_match:
                    cluster_id, similarity_score = exact_match
                    cluster = await self.db.get(Cluster, cluster_id)
                    is_new_cluster = False


                    # Calculate confidence score
                    confidence_score = 1.0  # Perfect match for exact content

                    # Generate reasoning
                    reasoning = "Assigned to existing cluster due to exact prompt content match"

                    # Create cluster assignment
                    assignment = ClusterAssignment(
                        prompt_id=prompt_id,
                        cluster_id=cluster_id,
                        similarity_score=similarity_score,
                        confidence_score=confidence_score,
                        reasoning=reasoning,
                    )

                    self.db.add(assignment)
                    await self.db.flush()

                    # Store embedding in Qdrant with cluster_id in payload
                    point_data = {
                        "id": str(prompt_id),
                        "vector": embedding,
                        "payload": {
                            "prompt_id": str(prompt_id),
                            "cluster_id": str(cluster_id),
                            "content": prompt_content or "",
                        },
                    }

                    await self.qdrant_client.upsert_points([point_data])

                    await self.db.commit()

                    return {
                        "prompt_id": prompt_id,
                        "cluster_id": cluster_id,
                        "similarity_score": similarity_score,
                        "confidence_score": confidence_score,
                        "reasoning": reasoning,
                        "status": "accepted",
                        "is_new_cluster": is_new_cluster,
                    }

            # Find best matching cluster using vector similarity
            best_match = await self._find_best_cluster(embedding, prompt_id)

            if best_match:
                cluster_id, similarity_score = best_match
                cluster = await self.db.get(Cluster, cluster_id)
                is_new_cluster = False

                logger.debug(
                    "Found matching cluster",
                    prompt_id=prompt_id,
                    cluster_id=cluster_id,
                    similarity_score=similarity_score,
                )
            else:
                # Create new cluster
                cluster = await self._create_new_cluster(prompt_id, embedding)
                cluster_id = cluster.id
                similarity_score = 1.0  # Perfect match for new cluster
                is_new_cluster = True

                logger.debug(
                    "Created new cluster",
                    prompt_id=prompt_id,
                    cluster_id=cluster_id,
                )

            # Calculate confidence score
            confidence_score = min(similarity_score / self.similarity_threshold, 1.0)

            # Generate reasoning
            reasoning = self._generate_reasoning(similarity_score, cluster_id, is_new_cluster)

            # Create cluster assignment
            assignment = ClusterAssignment(
                prompt_id=prompt_id,
                cluster_id=cluster_id,
                similarity_score=similarity_score,
                confidence_score=confidence_score,
                reasoning=reasoning,
            )

            self.db.add(assignment)
            await self.db.flush()

            # Ensure collection exists before storing
            await self.qdrant_client.ensure_collection()

            # Store embedding in Qdrant with cluster_id in payload
            point_data = {
                "id": str(prompt_id),
                "vector": embedding,
                "payload": {
                    "prompt_id": str(prompt_id),
                    "cluster_id": str(cluster_id),
                    "content": prompt_content or "",
                },
            }

            await self.qdrant_client.upsert_points([point_data])

            logger.info(
                "Prompt assigned to cluster",
                prompt_id=prompt_id,
                cluster_id=cluster_id,
                similarity_score=similarity_score,
                confidence_score=confidence_score,
                is_new=is_new_cluster,
            )

            return {
                "prompt_id": str(prompt_id),
                "cluster_id": str(cluster_id),
                "similarity_score": similarity_score,
                "confidence_score": confidence_score,
                "reasoning": reasoning,
                "is_new_cluster": is_new_cluster,
            }

        except Exception as e:
            logger.error("Error assigning prompt to cluster", prompt_id=prompt_id, error=str(e))
            raise

    async def get_cluster_prompts(self, cluster_id: uuid.UUID) -> List[Prompt]:
        """
        Get all prompts in a cluster.

        Args:
            cluster_id: Cluster ID

        Returns:
            List of Prompt objects
        """
        # Query cluster assignments
        stmt = select(ClusterAssignment).where(ClusterAssignment.cluster_id == cluster_id)
        result = await self.db.execute(stmt)
        assignments = result.scalars().all()

        # Get prompt IDs
        prompt_ids = [assignment.prompt_id for assignment in assignments]

        # Fetch prompts
        prompts = []
        for prompt_id in prompt_ids:
            prompt = await self.db.get(Prompt, prompt_id)
            if prompt:
                prompts.append(prompt)

        return prompts


def get_clustering_service(
    db: AsyncSession,
    similarity_service: Optional[SimilarityService] = None,
    qdrant_client: Optional[AsyncQdrantClientWrapper] = None,
    redis_client: Optional[RedisClient] = None,
) -> ClusteringService:
    """
    Get clustering service instance.

    Args:
        db: Database session
        similarity_service: Optional SimilarityService instance
        qdrant_client: Optional AsyncQdrantClientWrapper instance
        redis_client: Optional RedisClient instance

    Returns:
        ClusteringService instance
    """
    return ClusteringService(
        db=db,
        similarity_service=similarity_service,
        qdrant_client=qdrant_client,
        redis_client=redis_client,
    )

