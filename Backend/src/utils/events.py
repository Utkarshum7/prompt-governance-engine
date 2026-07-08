"""Structured event logging for AI decisions and performance tracing."""

import uuid
from typing import Any, Dict, Optional
from structlog import get_logger

logger = get_logger("ai.governance.telemetry")


def log_ai_decision(
    request_id: Optional[str] = None,
    selected_model: Optional[str] = None,
    routing_reason: Optional[str] = None,
    confidence_score: Optional[float] = None,
    similarity_score: Optional[float] = None,
    cluster_id: Optional[str] = None,
    latency: Optional[float] = None,
    estimated_token_usage: Optional[int] = None,
    extra_metadata: Optional[Dict[str, Any]] = None,
):
    """
    Log a structured AI decision event to the telemetry logger.

    Args:
        request_id: Unique request trace ID
        selected_model: Model string chosen for execution
        routing_reason: Explanation of routing path (e.g. 'is_code', 'complexity')
        confidence_score: Confidence estimate of the operation
        similarity_score: Similarity score for clustering mappings
        cluster_id: Target cluster uuid string
        latency: Execution time in seconds
        estimated_token_usage: Estimated prompt + response token count
        extra_metadata: Any additional payload fields
    """
    req_id = request_id or str(uuid.uuid4())
    payload = {
        "event_type": "ai_decision_trace",
        "request_id": req_id,
        "selected_model": selected_model or "unknown",
        "routing_reason": routing_reason or "default",
        "confidence_score": confidence_score if confidence_score is not None else 0.0,
        "similarity_score": similarity_score if similarity_score is not None else 0.0,
        "cluster_id": cluster_id or "none",
        "latency_seconds": latency if latency is not None else 0.0,
        "estimated_token_usage": estimated_token_usage if estimated_token_usage is not None else 0,
    }

    if extra_metadata:
        payload.update(extra_metadata)

    logger.info("AI Decision Processed", **payload)
