"""Embedding generation service using Portkey AI."""

import base64
import hashlib
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from structlog import get_logger

from src.clients.portkey import AsyncPortkeyClient, PortkeyClientError, get_async_portkey_client
from src.clients.redis import RedisClient, get_redis_client
from src.config.settings import get_settings

logger = get_logger(__name__)

# Cache TTL: 7 days in seconds
EMBEDDING_CACHE_TTL = 7 * 24 * 60 * 60


class EmbeddingService:
    """Service for generating embeddings using text-embedding-3-small."""

    def __init__(
        self,
        client: Optional[AsyncPortkeyClient] = None,
        redis_client: Optional[RedisClient] = None,
    ):
        """
        Initialize embedding service.

        Args:
            client: Optional AsyncPortkeyClient instance. If None, creates a new one.
            redis_client: Optional RedisClient instance. If None, creates a new one.
        """
        settings = get_settings()
        self.primary_model = settings.models.embedding.primary
        self.fallback_model = settings.models.embedding.fallback
        self.batch_size = settings.models.embedding.batch_size
        self.client = client or get_async_portkey_client(provider=self.primary_model)
        self.redis_client = redis_client or get_redis_client()

        logger.info(
            "Embedding service initialized",
            primary_model=self.primary_model,
            fallback_model=self.fallback_model,
            batch_size=self.batch_size,
        )

    def _estimate_tokens(self, text: str) -> int:
        """
        Estimate token count (rough approximation: 1 token ≈ 4 characters).

        Args:
            text: Text to estimate tokens for

        Returns:
            Estimated token count
        """
        return len(text) // 4

    def _get_model_for_text(self, text: str) -> str:
        """
        Select appropriate model based on text length.

        Args:
            text: Text to embed

        Returns:
            Model identifier to use
        """
        estimated_tokens = self._estimate_tokens(text)
        if estimated_tokens > 8000:
            logger.debug(
                "Using fallback model for long text",
                estimated_tokens=estimated_tokens,
                model=self.fallback_model,
            )
            return self.fallback_model
        return self.primary_model

    def _generate_prompt_hash(self, content: str) -> str:
        """
        Generate hash for prompt content (for caching).

        Args:
            content: Prompt content

        Returns:
            SHA256 hash of content
        """
        return hashlib.sha256(content.encode("utf-8")).hexdigest()

    def _get_cache_key(self, content: str, model: str) -> str:
        """
        Generate cache key for embedding.

        Args:
            content: Text content
            model: Model identifier

        Returns:
            Cache key
        """
        prompt_hash = self._generate_prompt_hash(content)
        return f"embedding:{model}:{prompt_hash}"

    async def generate_embedding(
        self,
        text: str,
        model: Optional[str] = None,
        encoding_format: str = "float",
        trace_id: Optional[str] = None,
        use_cache: bool = True,
    ) -> Tuple[List[float], Dict[str, Any]]:
        """
        Generate embedding for a single text.

        Args:
            text: Text to embed
            model: Optional model override. If None, selects based on text length.
            encoding_format: Encoding format ("float" or "base64")
            trace_id: Optional trace ID for request tracking
            use_cache: Whether to use Redis cache

        Returns:
            Tuple of (embedding vector, metadata)

        Raises:
            PortkeyClientError: If embedding API call fails
        """
        # Select model
        selected_model = model or self._get_model_for_text(text)

        # Check cache first
        if use_cache:
            cache_key = self._get_cache_key(text, selected_model)
            cached_result = await self.redis_client.get(cache_key)
            if cached_result:
                logger.debug("Embedding cache hit", cache_key=cache_key, trace_id=trace_id)
                # Return cached embedding and metadata
                embedding = cached_result.get("embedding", [])
                metadata = cached_result.get("metadata", {})
                return embedding, metadata

            logger.debug("Embedding cache miss", cache_key=cache_key, trace_id=trace_id)

        try:
            logger.debug("Generating embedding", text_length=len(text), trace_id=trace_id)

            # Select model
            selected_model = model or self._get_model_for_text(text)

            # Use with_options for request-level overrides
            client_with_options = (
                self.client.with_options(trace_id=trace_id) if trace_id else self.client
            )

            # Create client with selected model if different from default
            if selected_model != self.primary_model:
                client_with_options = get_async_portkey_client(provider=selected_model)

            response = await client_with_options.embeddings_create(
                input=text,
                model=selected_model,
                encoding_format=encoding_format,
            )

            # Extract embedding
            embedding_data = response.data[0] if response.data else None

            if not embedding_data:
                raise PortkeyClientError("No embedding data returned")

            raw_embedding = embedding_data.embedding if hasattr(embedding_data, "embedding") else ""

            # Decode base64 string to float array
            if isinstance(raw_embedding, str):
                # Base64 encoded embedding
                try:
                    decoded_bytes = base64.b64decode(raw_embedding)
                    embedding = np.frombuffer(decoded_bytes, dtype=np.float32).tolist()
                except Exception as e:
                    logger.error("Failed to decode base64 embedding", error=str(e))
                    raise PortkeyClientError(f"Failed to decode embedding: {e}")
            elif isinstance(raw_embedding, list):
                # Already a list of floats
                embedding = raw_embedding
            else:
                raise PortkeyClientError("Unexpected embedding format")

            metadata = {
                "model": selected_model,
                "dimensions": len(embedding),
                "encoding_format": encoding_format,
                "prompt_hash": self._generate_prompt_hash(text),
            }

            logger.debug(
                "Embedding generated successfully",
                model=selected_model,
                dimensions=len(embedding),
                trace_id=trace_id,
            )

            # Cache the result
            if use_cache:
                cache_key = self._get_cache_key(text, selected_model)
                cache_value = {
                    "embedding": embedding,
                    "metadata": metadata,
                }
                await self.redis_client.set(cache_key, cache_value, ttl=EMBEDDING_CACHE_TTL)
                logger.debug("Embedding cached", cache_key=cache_key, trace_id=trace_id)

            return embedding, metadata

        except PortkeyClientError as e:
            logger.error("Embedding API error", error=str(e), trace_id=trace_id)
            raise
        except Exception as e:
            logger.error("Unexpected embedding error", error=str(e), trace_id=trace_id)
            raise PortkeyClientError(f"Embedding generation failed: {e}") from e

    async def generate_embeddings_batch(
        self,
        texts: List[str],
        model: Optional[str] = None,
        encoding_format: str = "float",
        trace_id: Optional[str] = None,
    ) -> List[Tuple[List[float], Dict[str, Any]]]:
        """
        Generate embeddings for multiple texts in batch.

        Args:
            texts: List of texts to embed
            model: Optional model override
            encoding_format: Encoding format ("float" or "base64")
            trace_id: Optional trace ID for request tracking

        Returns:
            List of tuples (embedding vector, metadata) for each text

        Raises:
            PortkeyClientError: If embedding API call fails
        """
        try:
            logger.debug(
                "Generating embeddings batch",
                batch_size=len(texts),
                trace_id=trace_id,
            )

            # Select model (use primary for batch, or check if any text is long)
            selected_model = model or self.primary_model
            if not model:
                # Check if any text requires fallback model
                for text in texts:
                    if self._estimate_tokens(text) > 8000:
                        selected_model = self.fallback_model
                        break

            # Use with_options for request-level overrides
            client_with_options = (
                self.client.with_options(trace_id=trace_id) if trace_id else self.client
            )

            # Create client with selected model if different from default
            if selected_model != self.primary_model:
                client_with_options = get_async_portkey_client(provider=selected_model)

            response = await client_with_options.embeddings_create(
                input=texts,
                model=selected_model,
                encoding_format=encoding_format,
            )

            # Extract embeddings
            results = []
            for i, embedding_data in enumerate(response.data):
                embedding = embedding_data.embedding if hasattr(embedding_data, "embedding") else []

                metadata = {
                    "model": selected_model,
                    "dimensions": len(embedding),
                    "encoding_format": encoding_format,
                    "prompt_hash": self._generate_prompt_hash(texts[i]),
                    "index": i,
                }

                results.append((embedding, metadata))

            logger.debug(
                "Batch embeddings generated successfully",
                batch_size=len(results),
                model=selected_model,
                trace_id=trace_id,
            )

            return results

        except PortkeyClientError as e:
            logger.error("Batch embedding API error", error=str(e), trace_id=trace_id)
            raise
        except Exception as e:
            logger.error("Unexpected batch embedding error", error=str(e), trace_id=trace_id)
            raise PortkeyClientError(f"Batch embedding generation failed: {e}") from e


# Global embedding service instance
_embedding_service: Optional[EmbeddingService] = None


def get_embedding_service() -> EmbeddingService:
    """
    Get global embedding service instance.

    Returns:
        EmbeddingService instance
    """
    global _embedding_service
    if _embedding_service is None:
        _embedding_service = EmbeddingService()
    return _embedding_service

