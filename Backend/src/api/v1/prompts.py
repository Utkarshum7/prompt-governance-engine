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
        logger.info("Processing prompt ingestion", content_length=len(request.content), trace_id=trace_id)

        # Step 1: Moderation check
        moderation_service = get_moderation_service()
        moderation_result = await moderation_service.moderate(request.content, trace_id=trace_id)

        if moderation_result["flagged"]:
            logger.warning("Prompt rejected by moderation", trace_id=trace_id)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": "Prompt rejected by content moderation",
                    "reason": "Content flagged as inappropriate",
                    "categories": moderation_result.get("categories", {}),
                },
            )

        # Step 2: Generate embedding
        embedding_service = get_embedding_service()
        embedding, embedding_metadata = await embedding_service.generate_embedding(
            request.content, trace_id=trace_id
        )

        # Step 3: Store prompt in database
        from src.models.database import Prompt

        prompt_id = uuid.uuid4()
        prompt = Prompt(
            id=prompt_id,
            content=request.content,
            moderation_status=moderation_result["status"],
        )

        db.add(prompt)
        await db.flush()

        # Step 4: Cluster assignment
        clustering_service = get_clustering_service(db)
        assignment_result = await clustering_service.assign_to_cluster(
            prompt_id=prompt_id,
            embedding=embedding,
            prompt_content=request.content,
        )

        await db.commit()

        logger.info(
            "Prompt ingested successfully",
            prompt_id=prompt_id,
            cluster_id=assignment_result.get("cluster_id"),
            trace_id=trace_id,
        )

        return PromptIngestionResponse(
            prompt_id=assignment_result["prompt_id"] if isinstance(assignment_result["prompt_id"], uuid.UUID) else uuid.UUID(assignment_result["prompt_id"]),
            cluster_id=assignment_result["cluster_id"] if isinstance(assignment_result.get("cluster_id"), uuid.UUID) else uuid.UUID(assignment_result["cluster_id"]) if assignment_result.get("cluster_id") else None,
            similarity_score=assignment_result.get("similarity_score"),
            confidence_score=assignment_result.get("confidence_score"),
            reasoning=assignment_result.get("reasoning"),
            status="accepted",
            is_new_cluster=assignment_result.get("is_new_cluster", False),
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

