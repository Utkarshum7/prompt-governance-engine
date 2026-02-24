"""Template API endpoints."""

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from structlog import get_logger

from src.api.dependencies import get_db
from src.models.database import CanonicalTemplate, TemplateSlot
from src.models.schemas import (
    ErrorResponse,
    TemplateDetailResponse,
    TemplateListResponse,
    TemplateResponse,
    TemplateSlotResponse,
)
from src.services.template_versioning import get_template_versioning_service

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1/templates", tags=["templates"])


@router.get(
    "",
    response_model=TemplateListResponse,
    responses={500: {"model": ErrorResponse}},
)
async def list_templates(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    cluster_id: Optional[UUID] = Query(None, description="Filter by cluster ID"),
    db: AsyncSession = Depends(get_db),
) -> TemplateListResponse:
    """
    List all templates with pagination.

    Args:
        page: Page number (1-indexed)
        page_size: Number of items per page
        cluster_id: Optional cluster ID filter
        db: Database session

    Returns:
        List of templates with pagination info
    """
    try:
        # Calculate offset
        offset = (page - 1) * page_size

        # Build query
        stmt = select(CanonicalTemplate)
        count_stmt = select(func.count(CanonicalTemplate.id))

        if cluster_id:
            stmt = stmt.where(CanonicalTemplate.cluster_id == cluster_id)
            count_stmt = count_stmt.where(CanonicalTemplate.cluster_id == cluster_id)

        # Get total count
        total_result = await db.execute(count_stmt)
        total = total_result.scalar() or 0

        # Get templates with pagination
        stmt = stmt.order_by(CanonicalTemplate.created_at.desc()).offset(offset).limit(page_size)
        result = await db.execute(stmt)
        templates = result.scalars().all()

        template_responses = [TemplateResponse.model_validate(t) for t in templates]

        logger.debug("Listed templates", page=page, page_size=page_size, total=total, cluster_id=cluster_id)

        return TemplateListResponse(
            templates=template_responses,
            total=total,
            page=page,
            page_size=page_size,
        )

    except Exception as e:
        logger.error("Error listing templates", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "Failed to list templates", "detail": str(e)},
        )


@router.get(
    "/{template_id}",
    response_model=TemplateDetailResponse,
    responses={404: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
)
async def get_template(
    template_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> TemplateDetailResponse:
    """
    Get template details by ID.

    Args:
        template_id: Template ID
        db: Database session

    Returns:
        Template details with slots

    Raises:
        HTTPException: If template not found
    """
    try:
        template = await db.get(CanonicalTemplate, template_id)
        if not template:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": "Template not found", "template_id": str(template_id)},
            )

        # Get template slots
        stmt = select(TemplateSlot).where(TemplateSlot.template_id == template_id)
        result = await db.execute(stmt)
        slots = result.scalars().all()

        slot_responses = [TemplateSlotResponse.model_validate(s) for s in slots]

        template_dict = TemplateResponse.model_validate(template).model_dump()

        logger.debug("Retrieved template", template_id=template_id, slots_count=len(slots))

        return TemplateDetailResponse(
            **template_dict,
            template_slots=slot_responses,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error getting template", template_id=template_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "Failed to get template", "detail": str(e)},
        )


@router.get(
    "/{template_id}/versions",
    response_model=list[TemplateResponse],
    responses={404: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
)
async def get_template_versions(
    template_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> list[TemplateResponse]:
    """
    Get all versions of a template.

    Args:
        template_id: Template ID (any version)
        db: Database session

    Returns:
        List of template versions

    Raises:
        HTTPException: If template not found
    """
    try:
        # Get template to find cluster_id
        template = await db.get(CanonicalTemplate, template_id)
        if not template:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": "Template not found", "template_id": str(template_id)},
            )

        # Get all versions for this cluster
        versioning_service = get_template_versioning_service(db)
        versions = await versioning_service.get_template_versions(template.cluster_id)

        logger.debug("Retrieved template versions", template_id=template_id, versions_count=len(versions))

        return [TemplateResponse.model_validate(v) for v in versions]

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error getting template versions", template_id=template_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "Failed to get template versions", "detail": str(e)},
        )


@router.get(
    "/{template_id}/evolution",
    response_model=list[dict],
    responses={404: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
)
async def get_template_evolution(
    template_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    """
    Get evolution history for a template.

    Args:
        template_id: Template ID
        db: Database session

    Returns:
        List of evolution events

    Raises:
        HTTPException: If template not found
    """
    try:
        # Verify template exists
        template = await db.get(CanonicalTemplate, template_id)
        if not template:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": "Template not found", "template_id": str(template_id)},
            )

        # Get evolution history
        from src.services.evolution import get_evolution_tracking_service

        evolution_service = get_evolution_tracking_service(db)
        events = await evolution_service.get_template_evolution(template_id)

        logger.debug("Retrieved template evolution", template_id=template_id, events_count=len(events))

        return [
            {
                "id": str(e.id),
                "event_type": e.event_type,
                "previous_version": e.previous_version,
                "new_version": e.new_version,
                "change_reason": e.change_reason,
                "detected_by": e.detected_by,
                "created_at": e.created_at.isoformat(),
            }
            for e in events
        ]

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error getting template evolution", template_id=template_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "Failed to get template evolution", "detail": str(e)},
        )

