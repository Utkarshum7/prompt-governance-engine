"""Portkey AI client wrapper with retry logic and error handling."""

import os
from typing import Any, Dict, Optional

import httpx
from portkey_ai import AsyncPortkey, Portkey
from structlog import get_logger
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from src.config.settings import get_settings

logger = get_logger(__name__)


class PortkeyClientError(Exception):
    """Base exception for Portkey client errors."""

    pass


class PortkeyClient:
    """Portkey AI client wrapper with retry logic and error handling."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        provider: Optional[str] = None,
        config: Optional[str] = None,
        virtual_key: Optional[str] = None,
        timeout: Optional[int] = None,
        retry_attempts: Optional[int] = None,
        http_client: Optional[httpx.Client] = None,
    ):
        """
        Initialize Portkey client.

        Args:
            api_key: Portkey API key. If None, loads from config or PORTKEY_API_KEY env var.
            provider: Provider/model identifier (e.g., "@openai/gpt-4o")
            config: Config ID (e.g., "cf-***")
            virtual_key: Virtual key for provider selection
            timeout: Request timeout in seconds. If None, uses config default.
            retry_attempts: Number of retry attempts. If None, uses config default.
            http_client: Custom httpx.Client for requests
        """
        settings = get_settings()

        # Get API key from parameter, config, or environment
        self.api_key = api_key or settings.portkey.api_key or os.getenv("PORTKEY_API_KEY")
        if not self.api_key:
            raise ValueError("Portkey API key is required")

        # Get timeout and retry settings
        self.timeout = timeout or settings.portkey.timeout
        self.retry_attempts = retry_attempts or settings.portkey.retry_attempts

        # Initialize Portkey client
        client_kwargs: Dict[str, Any] = {
            "api_key": self.api_key,
            "timeout": self.timeout,
        }

        if provider:
            client_kwargs["provider"] = provider
        elif config:
            client_kwargs["config"] = config
        elif virtual_key:
            client_kwargs["virtual_key"] = virtual_key

        if http_client:
            client_kwargs["http_client"] = http_client

        self.client = Portkey(**client_kwargs)

        logger.info(
            "Portkey client initialized",
            provider=provider,
            config=config,
            virtual_key=virtual_key,
            timeout=self.timeout,
        )

    def with_options(self, trace_id: Optional[str] = None, metadata: Optional[Dict[str, Any]] = None):
        """
        Create a client instance with request-level overrides.

        Args:
            trace_id: Trace ID for request tracking
            metadata: Additional metadata for the request

        Returns:
            Portkey client with options applied
        """
        return self.client.with_options(trace_id=trace_id, metadata=metadata or {})

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((httpx.HTTPError, httpx.TimeoutException)),
        reraise=True,
    )
    def _execute_with_retry(self, func, *args, **kwargs):
        """
        Execute function with retry logic.

        Args:
            func: Function to execute
            *args: Positional arguments
            **kwargs: Keyword arguments

        Returns:
            Function result

        Raises:
            PortkeyClientError: If execution fails after retries
        """
        try:
            logger.debug("Executing Portkey API call", function=func.__name__)
            result = func(*args, **kwargs)
            logger.debug("Portkey API call successful", function=func.__name__)
            return result
        except httpx.HTTPError as e:
            logger.error(
                "Portkey API HTTP error",
                error=str(e),
                function=func.__name__,
                attempt=self.retry_attempts,
            )
            raise PortkeyClientError(f"Portkey API HTTP error: {e}") from e
        except httpx.TimeoutException as e:
            logger.error(
                "Portkey API timeout",
                error=str(e),
                function=func.__name__,
                timeout=self.timeout,
            )
            raise PortkeyClientError(f"Portkey API timeout after {self.timeout}s") from e
        except Exception as e:
            logger.error("Portkey API error", error=str(e), function=func.__name__)
            raise PortkeyClientError(f"Portkey API error: {e}") from e

    def chat_completions_create(self, *args, **kwargs):
        """Create chat completion with retry logic."""
        return self._execute_with_retry(self.client.chat.completions.create, *args, **kwargs)

    def embeddings_create(self, *args, **kwargs):
        """Create embeddings with retry logic."""
        return self._execute_with_retry(self.client.embeddings.create, *args, **kwargs)

    def moderations_create(self, *args, **kwargs):
        """Create moderation check with retry logic."""
        return self._execute_with_retry(self.client.moderations.create, *args, **kwargs)


class AsyncPortkeyClient:
    """Async Portkey AI client wrapper with retry logic and error handling."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        provider: Optional[str] = None,
        config: Optional[str] = None,
        virtual_key: Optional[str] = None,
        timeout: Optional[int] = None,
        retry_attempts: Optional[int] = None,
        http_client: Optional[httpx.AsyncClient] = None,
    ):
        """
        Initialize Async Portkey client.

        Args:
            api_key: Portkey API key. If None, loads from config or PORTKEY_API_KEY env var.
            provider: Provider/model identifier (e.g., "@openai/gpt-4o")
            config: Config ID (e.g., "cf-***")
            virtual_key: Virtual key for provider selection
            timeout: Request timeout in seconds. If None, uses config default.
            retry_attempts: Number of retry attempts. If None, uses config default.
            http_client: Custom httpx.AsyncClient for requests
        """
        settings = get_settings()

        # Get API key from parameter, config, or environment
        self.api_key = api_key or settings.portkey.api_key or os.getenv("PORTKEY_API_KEY")
        if not self.api_key:
            raise ValueError("Portkey API key is required")

        # Get timeout and retry settings
        self.timeout = timeout or settings.portkey.timeout
        self.retry_attempts = retry_attempts or settings.portkey.retry_attempts

        # Initialize AsyncPortkey client
        client_kwargs: Dict[str, Any] = {
            "api_key": self.api_key,
            "timeout": self.timeout,
        }

        if provider:
            client_kwargs["provider"] = provider
        elif config:
            client_kwargs["config"] = config
        elif virtual_key:
            client_kwargs["virtual_key"] = virtual_key

        if http_client:
            client_kwargs["http_client"] = http_client

        self.client = AsyncPortkey(**client_kwargs)

        logger.info(
            "Async Portkey client initialized",
            provider=provider,
            config=config,
            virtual_key=virtual_key,
            timeout=self.timeout,
        )

    def with_options(self, trace_id: Optional[str] = None, metadata: Optional[Dict[str, Any]] = None):
        """
        Create a client instance with request-level overrides.

        Args:
            trace_id: Trace ID for request tracking
            metadata: Additional metadata for the request

        Returns:
            AsyncPortkey client with options applied
        """
        return self.client.with_options(trace_id=trace_id, metadata=metadata or {})

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((httpx.HTTPError, httpx.TimeoutException)),
        reraise=True,
    )
    async def _execute_with_retry(self, func, *args, **kwargs):
        """
        Execute async function with retry logic.

        Args:
            func: Async function to execute
            *args: Positional arguments
            **kwargs: Keyword arguments

        Returns:
            Function result

        Raises:
            PortkeyClientError: If execution fails after retries
        """
        try:
            logger.debug("Executing async Portkey API call", function=func.__name__)
            result = await func(*args, **kwargs)
            logger.debug("Async Portkey API call successful", function=func.__name__)
            return result
        except httpx.HTTPError as e:
            logger.error(
                "Portkey API HTTP error",
                error=str(e),
                function=func.__name__,
                attempt=self.retry_attempts,
            )
            raise PortkeyClientError(f"Portkey API HTTP error: {e}") from e
        except httpx.TimeoutException as e:
            logger.error(
                "Portkey API timeout",
                error=str(e),
                function=func.__name__,
                timeout=self.timeout,
            )
            raise PortkeyClientError(f"Portkey API timeout after {self.timeout}s") from e
        except Exception as e:
            logger.error("Portkey API error", error=str(e), function=func.__name__)
            raise PortkeyClientError(f"Portkey API error: {e}") from e

    async def chat_completions_create(self, *args, **kwargs):
        """Create chat completion with retry logic."""
        return await self._execute_with_retry(self.client.chat.completions.create, *args, **kwargs)

    async def embeddings_create(self, *args, **kwargs):
        """Create embeddings with retry logic."""
        return await self._execute_with_retry(self.client.embeddings.create, *args, **kwargs)

    async def moderations_create(self, *args, **kwargs):
        """Create moderation check with retry logic."""
        return await self._execute_with_retry(self.client.moderations.create, *args, **kwargs)


def get_portkey_client(
    provider: Optional[str] = None,
    config: Optional[str] = None,
    virtual_key: Optional[str] = None,
) -> PortkeyClient:
    """
    Get a Portkey client instance.

    Args:
        provider: Provider/model identifier (e.g., "@openai/gpt-4o")
        config: Config ID (e.g., "cf-***")
        virtual_key: Virtual key for provider selection

    Returns:
        PortkeyClient instance
    """
    return PortkeyClient(provider=provider, config=config, virtual_key=virtual_key)


def get_async_portkey_client(
    provider: Optional[str] = None,
    config: Optional[str] = None,
    virtual_key: Optional[str] = None,
) -> AsyncPortkeyClient:
    """
    Get an async Portkey client instance.

    Args:
        provider: Provider/model identifier (e.g., "@openai/gpt-4o")
        config: Config ID (e.g., "cf-***")
        virtual_key: Virtual key for provider selection

    Returns:
        AsyncPortkeyClient instance
    """
    return AsyncPortkeyClient(provider=provider, config=config, virtual_key=virtual_key)

