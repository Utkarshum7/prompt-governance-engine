"""AI Decision Engine for estimating prompt complexity and task classification."""

import re
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field
from structlog import get_logger

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


class DecisionOutput(BaseModel):
    """Output metadata from the AI Decision Engine."""

    prompt: str = Field(..., description="The raw prompt analyzed")
    token_count: int = Field(..., description="Estimated token count")
    is_code: bool = Field(..., description="True if code syntax is detected")
    complexity: str = Field(..., description="Estimated complexity: low, medium, high")
    task_type: str = Field(..., description="Classified task type: classification, canonicalization, reasoning, moderation, coding, general")
    latency_preference: str = Field(..., description="Preference: low, normal")
    cost_preference: str = Field(..., description="Preference: low, normal")
    confidence_estimate: float = Field(..., description="Initial confidence estimate (0.0 to 1.0)")


class AIDecisionEngine:
    """Decision Engine that analyzes prompts to optimize routing and model execution."""

    def __init__(self):
        """Initialize AI Decision Engine."""
        logger.info("AI Decision Engine initialized")

    def _detect_code(self, text: str) -> bool:
        """Detect if text contains code snippets or coding keywords."""
        text_lower = text.lower()

        # Check for regex patterns
        for pattern in CODE_PATTERNS:
            if re.search(pattern, text, re.IGNORECASE):
                return True

        # Check for keyword density
        code_keywords = [
            "def ", "class ", "function", "import ", "const ", "let ",
            "var ", "return ", "if ", "else ", "for ", "while ",
            "select ", "from ", "where "
        ]
        keyword_count = sum(1 for keyword in code_keywords if keyword in text_lower)
        words = text.split()
        keyword_density = keyword_count / max(len(words), 1)

        if keyword_density > 0.05:
            return True

        return False

    def _classify_task(self, text: str, context: Optional[str] = None) -> str:
        """Classify task type based on content keywords and context."""
        if context:
            return context

        text_lower = text.lower()
        if self._detect_code(text):
            return "coding"
        if any(kw in text_lower for kw in ["translate", "language", "english", "spanish", "french"]):
            return "translation"
        if any(kw in text_lower for kw in ["summarize", "summary", "tldr", "shorten"]):
            return "summarization"
        if any(kw in text_lower for kw in ["moderate", "censor", "flag", "safety", "harmful"]):
            return "moderation"
        if any(kw in text_lower for kw in ["cluster", "group", "semantic", "similarity"]):
            return "canonicalization"
        if any(kw in text_lower for kw in ["reason", "prove", "solve", "logic", "explain"]):
            return "reasoning"

        return "general"

    async def analyze_prompt(self, prompt: str, task_context: Optional[str] = None) -> DecisionOutput:
        """
        Analyze a prompt to extract complexity, estimated tokens, and task classification.

        Args:
            prompt: Raw prompt text
            task_context: Optional context hint

        Returns:
            DecisionOutput object
        """
        # 1. Estimate tokens (1 token ≈ 4 characters)
        estimated_tokens = max(len(prompt) // 4, 1)

        # 2. Detect code
        is_code = self._detect_code(prompt)

        # 3. Classify task type
        task_type = self._classify_task(prompt, task_context)

        # 4. Estimate complexity
        if is_code or estimated_tokens > 4000 or task_type == "reasoning":
            complexity = "high"
            latency_preference = "normal"
            cost_preference = "normal"
            confidence_estimate = 0.85
        elif estimated_tokens > 1000 or task_type in ["translation", "summarization"]:
            complexity = "medium"
            latency_preference = "low"
            cost_preference = "low"
            confidence_estimate = 0.90
        else:
            complexity = "low"
            latency_preference = "low"
            cost_preference = "low"
            confidence_estimate = 0.95

        output = DecisionOutput(
            prompt=prompt,
            token_count=estimated_tokens,
            is_code=is_code,
            complexity=complexity,
            task_type=task_type,
            latency_preference=latency_preference,
            cost_preference=cost_preference,
            confidence_estimate=confidence_estimate,
        )

        logger.info(
            "Prompt analyzed by Decision Engine",
            token_count=output.token_count,
            is_code=output.is_code,
            complexity=output.complexity,
            task_type=output.task_type,
        )

        return output


# Global instance of AIDecisionEngine
_decision_engine: Optional[AIDecisionEngine] = None


def get_decision_engine() -> AIDecisionEngine:
    """Get global AIDecisionEngine instance."""
    global _decision_engine
    if _decision_engine is None:
        _decision_engine = AIDecisionEngine()
    return _decision_engine
