"""Prompt ingestion API endpoints."""

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from structlog import get_logger

from src.api.dependencies import get_db
from src.models.schemas import ErrorResponse, PromptCreateRequest, PromptIngestionResponse
from src.services.clustering import get_clustering_service
from src.services.embedding import get_embedding_service
from src.services.moderation import get_moderation_service

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1/prompts", tags=["prompts"])


@router.post(
    "",
    response_model=PromptIngestionResponse,
    status_code=status.HTTP_201_CREATED,
    responses={400: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
)
async def ingest_prompt(
    request: PromptCreateRequest,
    db: AsyncSession = Depends(get_db),
    trace_id: Optional[str] = None,
) -> PromptIngestionResponse:
    """
    Ingest a single prompt through the full pipeline.

    Pipeline:
    1. Moderation check
    2. Embedding generation
    3. Clustering assignment
    4. Template extraction (if new cluster or on demand)

    Args:
        request: Prompt creation request
        db: Database session
        trace_id: Optional trace ID for request tracking

    Returns:
        Prompt ingestion response with cluster assignment

    Raises:
        HTTPException: If prompt is rejected or processing fails
    """
    try:
        logger.info("Processing prompt ingestion via AIOrchestrator", content_length=len(request.content), trace_id=trace_id)

        from src.services.orchestrator import AIOrchestrator
        orchestrator = AIOrchestrator(db)
        
        result = await orchestrator.ingest_prompt(request.content, trace_id=trace_id)

        if result["status"] == "rejected":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": "Prompt rejected by content moderation",
                    "reason": "Content flagged as inappropriate",
                    "categories": result.get("moderation_result", {}).get("categories", {}),
                },
            )

        # Commit transaction
        await db.commit()

        return PromptIngestionResponse(
            prompt_id=result["prompt_id"],
            cluster_id=result["cluster_id"],
            similarity_score=result["similarity_score"],
            confidence_score=result["confidence_score"],
            reasoning=result["reasoning"],
            status="accepted",
            is_new_cluster=result["is_new_cluster"],
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error ingesting prompt", error=str(e), trace_id=trace_id)
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "Failed to ingest prompt", "detail": str(e)},
        )

