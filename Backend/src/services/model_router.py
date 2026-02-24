"""Model routing logic for selecting appropriate models."""

import re
from typing import Literal, Optional

from structlog import get_logger

from src.config.settings import get_settings

logger = get_logger(__name__)

# Code detection patterns
CODE_PATTERNS = [
    r"```[\s\S]*?```",  # Code blocks
    r"`[^`]+`",  # Inline code
    r"\b(def|class|function|import|from|const|let|var|return|if|else|for|while)\b",  # Code keywords
    r"\{[^}]*\}",  # Code-like structures
    r"\([^)]*\)\s*=>",  # Arrow functions
    r"#include|#define|#ifdef",  # C/C++ preprocessor
    r"SELECT|FROM|WHERE|INSERT|UPDATE|DELETE",  # SQL keywords
]


class ModelRouter:
    """Router to select appropriate model based on prompt characteristics."""

    def __init__(self):
        """Initialize model router."""
        settings = get_settings()
        self.gpt4o_model = settings.models.canonicalization.primary
        self.claude_model = settings.models.canonicalization.alternative

        logger.info(
            "Model router initialized",
            gpt4o_model=self.gpt4o_model,
            claude_model=self.claude_model,
        )

    def _detect_code(self, text: str) -> bool:
        """
        Detect if text contains code.

        Args:
            text: Text to analyze

        Returns:
            True if code is detected, False otherwise
        """
        text_lower = text.lower()

        # Check for code patterns
        for pattern in CODE_PATTERNS:
            if re.search(pattern, text, re.IGNORECASE):
                logger.debug("Code detected", pattern=pattern)
                return True

        # Check for high code keyword density
        code_keywords = [
            "def ",
            "class ",
            "function",
            "import ",
            "const ",
            "let ",
            "var ",
            "return ",
            "if ",
            "else ",
            "for ",
            "while ",
            "SELECT ",
            "FROM ",
            "WHERE ",
        ]

        keyword_count = sum(1 for keyword in code_keywords if keyword in text_lower)
        keyword_density = keyword_count / max(len(text.split()), 1)

        # If keyword density > 0.05 (5%), likely code-heavy
        if keyword_density > 0.05:
            logger.debug("High code keyword density detected", density=keyword_density)
            return True

        return False

    def route_canonicalization(
        self, prompt: str, force_model: Optional[Literal["gpt4o", "claude"]] = None
    ) -> str:
        """
        Route to appropriate canonicalization model.

        Args:
            prompt: Prompt text to analyze
            force_model: Optional model override ("gpt4o" or "claude")

        Returns:
            Model identifier to use
        """
        if force_model:
            if force_model == "claude":
                logger.debug("Using Claude model (forced)", model=self.claude_model)
                return self.claude_model
            else:
                logger.debug("Using GPT-4o model (forced)", model=self.gpt4o_model)
                return self.gpt4o_model

        # Detect code-heavy prompts
        if self._detect_code(prompt):
            logger.debug("Routing to Claude for code-heavy prompt", model=self.claude_model)
            return self.claude_model

        # Default to GPT-4o
        logger.debug("Routing to GPT-4o for regular prompt", model=self.gpt4o_model)
        return self.gpt4o_model

    def route_embedding(self, prompt: str) -> str:
        """
        Route to appropriate embedding model.

        Args:
            prompt: Prompt text to analyze

        Returns:
            Model identifier to use
        """
        settings = get_settings()
        primary_model = settings.models.embedding.primary
        fallback_model = settings.models.embedding.fallback

        # Estimate tokens (rough: 1 token ≈ 4 characters)
        estimated_tokens = len(prompt) // 4

        if estimated_tokens > 8000:
            logger.debug(
                "Routing to fallback embedding model for long prompt",
                estimated_tokens=estimated_tokens,
                model=fallback_model,
            )
            return fallback_model

        logger.debug("Routing to primary embedding model", model=primary_model)
        return primary_model


# Global model router instance
_model_router: Optional[ModelRouter] = None


def get_model_router() -> ModelRouter:
    """
    Get global model router instance.

    Returns:
        ModelRouter instance
    """
    global _model_router
    if _model_router is None:
        _model_router = ModelRouter()
    return _model_router

