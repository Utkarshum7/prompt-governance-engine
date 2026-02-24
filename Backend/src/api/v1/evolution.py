"""Evolution tracking API endpoints."""

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from structlog import get_logger

from src.api.dependencies import get_db
from src.models.database import EvolutionEvent, PromptFamily
from src.models.schemas import (
    DriftDetectionResponse,
    ErrorResponse,
    EvolutionEventListResponse,
    EvolutionEventResponse,
    PromptFamilyListResponse,
    PromptFamilyResponse,
)
from src.services.drift_detection import get_drift_detection_service
from src.services.evolution import get_evolution_tracking_service

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1/evolution", tags=["evolution"])


@router.get(
    "/events",
    response_model=EvolutionEventListResponse,
    responses={500: {"model": ErrorResponse}},
)
async def list_evolution_events(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    event_type: Optional[str] = Query(None, description="Filter by event type"),
    template_id: Optional[UUID] = Query(None, description="Filter by template ID"),
    db: AsyncSession = Depends(get_db),
) -> EvolutionEventListResponse:
    """
    List evolution events with filtering and pagination.

    Args:
        page: Page number (1-indexed)
        page_size: Number of items per page
        event_type: Optional event type filter
        template_id: Optional template ID filter
        db: Database session

    Returns:
        List of evolution events with pagination info
    """
    try:
        # Calculate offset
        offset = (page - 1) * page_size

        # Build query
        stmt = select(EvolutionEvent)
        count_stmt = select(func.count(EvolutionEvent.id))

        if event_type:
            stmt = stmt.where(EvolutionEvent.event_type == event_type)
            count_stmt = count_stmt.where(EvolutionEvent.event_type == event_type)

        if template_id:
            stmt = stmt.where(EvolutionEvent.template_id == template_id)
            count_stmt = count_stmt.where(EvolutionEvent.template_id == template_id)

        # Get total count
        total_result = await db.execute(count_stmt)
        total = total_result.scalar() or 0

        # Get events with pagination
        stmt = stmt.order_by(EvolutionEvent.created_at.desc()).offset(offset).limit(page_size)
        result = await db.execute(stmt)
        events = result.scalars().all()

        event_responses = [EvolutionEventResponse.model_validate(e) for e in events]

        logger.debug(
            "Listed evolution events",
            page=page,
            page_size=page_size,
            total=total,
            event_type=event_type,
            template_id=template_id,
        )

        return EvolutionEventListResponse(
            events=event_responses,
            total=total,
            page=page,
            page_size=page_size,
        )

    except Exception as e:
        logger.error("Error listing evolution events", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "Failed to list evolution events", "detail": str(e)},
        )


@router.get(
    "/families",
    response_model=PromptFamilyListResponse,
    responses={500: {"model": ErrorResponse}},
)
async def list_prompt_families(
    db: AsyncSession = Depends(get_db),
) -> PromptFamilyListResponse:
    """
    List all prompt families.

    Args:
        db: Database session

    Returns:
        List of prompt families
    """
    try:
        stmt = select(PromptFamily).order_by(PromptFamily.created_at.desc())
        result = await db.execute(stmt)
        families = result.scalars().all()

        # Get cluster counts for each family
        from src.models.database import FamilyClusterMapping

        family_responses = []
        for family in families:
            count_stmt = select(func.count(FamilyClusterMapping.id)).where(
                FamilyClusterMapping.family_id == family.id
            )
            count_result = await db.execute(count_stmt)
            cluster_count = count_result.scalar() or 0

            family_dict = PromptFamilyResponse.model_validate(family).model_dump()
            family_dict["cluster_count"] = cluster_count
            family_responses.append(PromptFamilyResponse(**family_dict))

        logger.debug("Listed prompt families", count=len(families))

        return PromptFamilyListResponse(families=family_responses, total=len(families))

    except Exception as e:
        logger.error("Error listing prompt families", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "Failed to list prompt families", "detail": str(e)},
        )


@router.get(
    "/drift",
    response_model=DriftDetectionResponse,
    responses={404: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
)
async def detect_drift(
    cluster_id: UUID = Query(..., description="Cluster ID to analyze"),
    template_id: Optional[UUID] = Query(None, description="Optional template ID"),
    recent_prompts_count: int = Query(20, ge=5, le=100, description="Number of recent prompts to analyze"),
    db: AsyncSession = Depends(get_db),
) -> DriftDetectionResponse:
    """
    Detect semantic drift in a cluster.

    Args:
        cluster_id: Cluster ID to analyze
        template_id: Optional template ID
        recent_prompts_count: Number of recent prompts to analyze
        db: Database session

    Returns:
        Drift detection result

    Raises:
        HTTPException: If cluster not found or detection fails
    """
    try:
        # Verify cluster exists
        from src.models.database import Cluster

        cluster = await db.get(Cluster, cluster_id)
        if not cluster:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": "Cluster not found", "cluster_id": str(cluster_id)},
            )

        # Run drift detection
        drift_service = get_drift_detection_service(db)
        drift_result = await drift_service.detect_drift(
            cluster_id=cluster_id,
            template_id=template_id,
            recent_prompts_count=recent_prompts_count,
        )

        logger.info(
            "Drift detection completed",
            cluster_id=cluster_id,
            has_drift=drift_result.get("has_drift"),
            drift_score=drift_result.get("drift_score"),
        )

        return DriftDetectionResponse(
            cluster_id=cluster_id,
            template_id=template_id,
            has_drift=drift_result.get("has_drift", False),
            drift_score=drift_result.get("drift_score", 0.0),
            reasoning=drift_result.get("reasoning", ""),
            detected_changes=drift_result.get("detected_changes", []),
            recommendation=drift_result.get("recommendation", "none"),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error detecting drift", cluster_id=cluster_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "Failed to detect drift", "detail": str(e)},
        )

