"""Abstract interface for embedding generation providers."""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Tuple


class IEmbeddingProvider(ABC):
    """IEmbeddingProvider defines the interface for generating prompt embeddings."""

    @abstractmethod
    async def generate_embedding(
        self,
        text: str,
        model: Optional[str] = None,
        encoding_format: str = "float",
        trace_id: Optional[str] = None,
        use_cache: bool = True,
    ) -> Tuple[List[float], Dict[str, Any]]:
        """Generate embedding vector for a single text."""
        pass

    @abstractmethod
    async def generate_embeddings_batch(
        self,
        texts: List[str],
        model: Optional[str] = None,
        encoding_format: str = "float",
        trace_id: Optional[str] = None,
    ) -> List[Tuple[List[float], Dict[str, Any]]]:
        """Generate embedding vectors for a batch of texts."""
        pass
