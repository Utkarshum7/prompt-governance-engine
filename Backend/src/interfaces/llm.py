from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

class LLMClientError(Exception):
    """Base exception class for all LLM client providers."""
    pass


class ILLMProvider(ABC):
    """ILLMProvider defines the interface for LLM operations (Portkey, OpenAI, Anthropic, etc.)."""

    @abstractmethod
    def with_options(self, trace_id: Optional[str] = None, metadata: Optional[Dict[str, Any]] = None) -> Any:
        """Apply request-level options (trace ID, metadata)."""
        pass

    @abstractmethod
    async def chat_completions_create(self, *args, **kwargs) -> Any:
        """Call LLM chat completions endpoint."""
        pass

    @abstractmethod
    async def embeddings_create(self, *args, **kwargs) -> Any:
        """Call LLM embeddings endpoint."""
        pass

    @abstractmethod
    async def moderations_create(self, *args, **kwargs) -> Any:
        """Call LLM content moderations endpoint."""
        pass
