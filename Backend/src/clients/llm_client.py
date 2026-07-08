"""Factory module for LLM client providers."""

from typing import Any, Dict, Optional
from src.interfaces.llm import ILLMProvider, LLMClientError
from src.clients.gemini import get_async_gemini_client

# Re-export base exception for client errors
LLMClientError = LLMClientError


def get_async_llm_client(
    provider: Optional[str] = None,
    config: Optional[Dict[str, Any]] = None,
) -> ILLMProvider:
    """
    Get the configured async LLM client provider (currently Google Gemini).

    Args:
        provider: Optional provider name
        config: Optional routing config

    Returns:
        Instance of ILLMProvider
    """
    # Current active provider is Google Gemini
    return get_async_gemini_client(config=config)
