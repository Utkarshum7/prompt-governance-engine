"""Content moderation service using Portkey AI."""

from typing import Any, Dict, Optional

from structlog import get_logger

from src.clients.portkey import AsyncPortkeyClient, PortkeyClientError, get_async_portkey_client
from src.config.settings import get_settings

logger = get_logger(__name__)


class ModerationService:
    """Service for content moderation using text-moderation-latest."""

    def __init__(self, client: Optional[AsyncPortkeyClient] = None):
        """
        Initialize moderation service.

        Args:
            client: Optional AsyncPortkeyClient instance. If None, creates a new one.
        """
        settings = get_settings()
        self.model = settings.models.moderation.model
        self.client = client or get_async_portkey_client(provider=self.model)

        logger.info("Moderation service initialized", model=self.model)

    async def moderate(self, content: str, trace_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Moderate content using text-moderation-latest.

        Args:
            content: Content to moderate
            trace_id: Optional trace ID for request tracking

        Returns:
            Moderation result with status and flags

        Raises:
            PortkeyClientError: If moderation API call fails
        """
        try:
            logger.debug("Moderating content", content_length=len(content), trace_id=trace_id)

            # Use with_options for request-level overrides
            client_with_options = self.client.with_options(trace_id=trace_id) if trace_id else self.client

            response = await client_with_options.moderations_create(
                input=content,
                model=self.model,
            )

            # Extract moderation results
            result = response.results[0] if response.results else None

            if not result:
                logger.warning("No moderation results returned", trace_id=trace_id)
                return {
                    "flagged": False,
                    "status": "safe",
                    "categories": {},
                    "category_scores": {},
                }

            # Determine if content is flagged
            flagged = result.flagged if hasattr(result, "flagged") else False

            # Extract categories and scores
            categories = {}
            category_scores = {}

            if hasattr(result, "categories"):
                categories = {
                    key: getattr(result.categories, key, False)
                    for key in [
                        "hate",
                        "hate/threatening",
                        "harassment",
                        "harassment/threatening",
                        "self-harm",
                        "self-harm/intent",
                        "self-harm/instructions",
                        "sexual",
                        "sexual/minors",
                        "violence",
                        "violence/graphic",
                    ]
                }

            if hasattr(result, "category_scores"):
                category_scores = {
                    key: getattr(result.category_scores, key, 0.0)
                    for key in [
                        "hate",
                        "hate/threatening",
                        "harassment",
                        "harassment/threatening",
                        "self-harm",
                        "self-harm/intent",
                        "self-harm/instructions",
                        "sexual",
                        "sexual/minors",
                        "violence",
                        "violence/graphic",
                    ]
                }

            status = "rejected" if flagged else "safe"

            if flagged:
                logger.warning(
                    "Content rejected by moderation",
                    status=status,
                    categories=categories,
                    trace_id=trace_id,
                )
            else:
                logger.debug("Content passed moderation", status=status, trace_id=trace_id)

            return {
                "flagged": flagged,
                "status": status,
                "categories": categories,
                "category_scores": category_scores,
            }

        except PortkeyClientError as e:
            logger.error("Moderation API error", error=str(e), trace_id=trace_id)
            raise
        except Exception as e:
            logger.error("Unexpected moderation error", error=str(e), trace_id=trace_id)
            raise PortkeyClientError(f"Moderation failed: {e}") from e

    async def is_safe(self, content: str, trace_id: Optional[str] = None) -> bool:
        """
        Check if content is safe (not flagged).

        Args:
            content: Content to check
            trace_id: Optional trace ID for request tracking

        Returns:
            True if content is safe, False if flagged
        """
        result = await self.moderate(content, trace_id=trace_id)
        return not result["flagged"]


# Global moderation service instance
_moderation_service: Optional[ModerationService] = None


def get_moderation_service() -> ModerationService:
    """
    Get global moderation service instance.

    Returns:
        ModerationService instance
    """
    global _moderation_service
    if _moderation_service is None:
        _moderation_service = ModerationService()
    return _moderation_service

