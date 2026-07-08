"""Model routing logic for selecting appropriate models using AI Decision Engine."""

from typing import Any, Dict, Literal, Optional
from structlog import get_logger

from src.config.settings import get_settings
from src.services.decision_engine import DecisionOutput, get_decision_engine

logger = get_logger(__name__)


class ModelRouter:
    """Router that consumes Decision Engine output to generate Portkey configurations."""

    def __init__(self):
        """Initialize model router."""
        settings = get_settings()
        self.gpt4o_model = settings.models.canonicalization.primary
        self.claude_model = settings.models.canonicalization.alternative
        self.decision_engine = get_decision_engine()

        logger.info(
            "Model router initialized",
            gpt4o_model=self.gpt4o_model,
            claude_model=self.claude_model,
        )

    def route_for_decision(
        self,
        decision: DecisionOutput,
        confidence_score: Optional[float] = None,
        confidence_threshold: float = 0.85,
    ) -> Dict[str, Any]:
        """
        Select models and generate Portkey routing config based on Decision Engine output.

        Args:
            decision: DecisionOutput from the AIDecisionEngine
            confidence_score: Optional previous confidence score
            confidence_threshold: Threshold below which we upgrade to reasoning models

        Returns:
            Portkey gateway routing config dict
        """
        settings = get_settings()

        # Default options from settings
        primary_model = self.gpt4o_model
        alternative_model = self.claude_model
        reasoning_model = settings.models.reasoning.model

        # 1. Evaluate routing targets
        if confidence_score is not None and confidence_score < confidence_threshold:
            logger.info(
                "Router: Confidence below threshold, upgrading to reasoning model",
                confidence_score=confidence_score,
                threshold=confidence_threshold,
                model=reasoning_model,
            )
            first_target = reasoning_model
            second_target = primary_model
        else:
            # Route based on complexity and code detection from Decision Engine
            if decision.is_code or decision.task_type == "coding":
                logger.info("Router: Routing to Claude for complex code workload", model=alternative_model)
                first_target = alternative_model
                second_target = primary_model
            elif decision.complexity == "high":
                logger.info("Router: Routing to GPT-4o for high complexity prompt", model=primary_model)
                first_target = primary_model
                second_target = alternative_model
            else:
                logger.info("Router: Routing to GPT-4o-mini/standard for low/medium complexity prompt", model=primary_model)
                # In production, we can route simple prompts to a cheaper model (e.g. gpt-4o-mini)
                # But to maintain exact consistency, we use primary_model and alternative_model
                first_target = primary_model
                second_target = alternative_model

        # Helper to parse Portkey format e.g. "@openai/gpt-4o-2024-08-06" to provider and model
        def parse_target(target_str: str) -> Dict[str, Any]:
            if target_str.startswith("@"):
                parts = target_str[1:].split("/", 1)
                if len(parts) == 2:
                    return {"provider": parts[0], "model": parts[1]}
            return {"provider": "openai", "model": target_str}

        t1 = parse_target(first_target)
        t2 = parse_target(second_target)

        # Portkey dynamic routing config
        return {
            "strategy": {
                "mode": "fallback"
            },
            "targets": [
                {
                    "provider": t1["provider"],
                    "model": t1["model"],
                    "override_params": {
                        "temperature": settings.models.canonicalization.temperature,
                        "max_tokens": settings.models.canonicalization.max_tokens
                    }
                },
                {
                    "provider": t2["provider"],
                    "model": t2["model"],
                    "override_params": {
                        "temperature": settings.models.canonicalization.temperature,
                        "max_tokens": settings.models.canonicalization.max_tokens
                    }
                }
            ]
        }

    def route_canonicalization(
        self, prompt: str, force_model: Optional[Literal["gpt4o", "claude"]] = None
    ) -> str:
        """
        Route to appropriate canonicalization model (Backward compatible).

        Args:
            prompt: Prompt text to analyze
            force_model: Optional model override ("gpt4o" or "claude")

        Returns:
            Model identifier to use
        """
        if force_model:
            if force_model == "claude":
                return self.claude_model
            else:
                return self.gpt4o_model

        # Call Decision Engine locally for analysis
        # Run it synchronously since it is high performance
        import asyncio
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # Run in a background thread or using a separate helper
            is_code = self.decision_engine._detect_code(prompt)
        else:
            is_code = asyncio.run(self.decision_engine.analyze_prompt(prompt)).is_code

        if is_code:
            return self.claude_model
        return self.gpt4o_model

    def route_embedding(self, prompt: str) -> str:
        """
        Route to appropriate embedding model (Backward compatible).

        Args:
            prompt: Prompt text to analyze

        Returns:
            Model identifier to use
        """
        settings = get_settings()
        primary_model = settings.models.embedding.primary
        fallback_model = settings.models.embedding.fallback

        # Estimate tokens (1 token ≈ 4 characters)
        estimated_tokens = len(prompt) // 4

        if estimated_tokens > 8000:
            return fallback_model

        return primary_model

    def get_portkey_config(
        self,
        prompt: str,
        confidence_score: Optional[float] = None,
        confidence_threshold: float = 0.85
    ) -> Dict[str, Any]:
        """
        Get Portkey config by running Decision Engine (Backward compatible).

        Args:
            prompt: Prompt content
            confidence_score: Optional confidence score
            confidence_threshold: Optional threshold

        Returns:
            Portkey config dictionary
        """
        import asyncio
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # If loop is already running, run the analysis synchronously
                # (Heuristics in DecisionEngine are non-blocking, so we can mock the async call)
                token_count = len(prompt) // 4
                is_code = self.decision_engine._detect_code(prompt)
                task_type = self.decision_engine._classify_task(prompt)
                decision = DecisionOutput(
                    prompt=prompt,
                    token_count=token_count,
                    is_code=is_code,
                    complexity="high" if is_code or token_count > 4000 else "low",
                    task_type=task_type,
                    latency_preference="low",
                    cost_preference="low",
                    confidence_estimate=0.9,
                )
            else:
                decision = asyncio.run(self.decision_engine.analyze_prompt(prompt))
        except Exception:
            # Fallback in case of runtime issues
            token_count = len(prompt) // 4
            is_code = self.decision_engine._detect_code(prompt)
            decision = DecisionOutput(
                prompt=prompt,
                token_count=token_count,
                is_code=is_code,
                complexity="high" if is_code or token_count > 4000 else "low",
                task_type="coding" if is_code else "general",
                latency_preference="low",
                cost_preference="low",
                confidence_estimate=0.9,
            )

        return self.route_for_decision(
            decision=decision,
            confidence_score=confidence_score,
            confidence_threshold=confidence_threshold,
        )


# Global model router instance
_model_router: Optional[ModelRouter] = None


def get_model_router() -> ModelRouter:
    """Get global ModelRouter instance."""
    global _model_router
    if _model_router is None:
        _model_router = ModelRouter()
    return _model_router
