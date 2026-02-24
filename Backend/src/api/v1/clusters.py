"""Cluster query API endpoints."""

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from structlog import get_logger

from src.api.dependencies import get_db
from src.models.database import Cluster, ClusterAssignment, Prompt
from src.models.schemas import (
    ClusterDetailResponse,
    ClusterListResponse,
    ClusterResponse,
    ErrorResponse,
    PromptResponse,
)

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1/clusters", tags=["clusters"])


@router.get(
    "",
    response_model=ClusterListResponse,
    responses={500: {"model": ErrorResponse}},
)
async def list_clusters(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    db: AsyncSession = Depends(get_db),
) -> ClusterListResponse:
    """
    List all clusters with pagination.

    Args:
        page: Page number (1-indexed)
        page_size: Number of items per page
        db: Database session

    Returns:
        List of clusters with pagination info
    """
    try:
        # Calculate offset
        offset = (page - 1) * page_size

        # Get total count
        count_stmt = select(func.count(Cluster.id))
        total_result = await db.execute(count_stmt)
        total = total_result.scalar() or 0

        # Get clusters with pagination
        stmt = select(Cluster).order_by(Cluster.created_at.desc()).offset(offset).limit(page_size)
        result = await db.execute(stmt)
        clusters = result.scalars().all()

        # Get prompt counts for each cluster
        cluster_responses = []
        for cluster in clusters:
            # Count prompts in cluster
            count_stmt = select(func.count(ClusterAssignment.id)).where(
                ClusterAssignment.cluster_id == cluster.id
            )
            count_result = await db.execute(count_stmt)
            prompt_count = count_result.scalar() or 0

            cluster_dict = ClusterResponse.model_validate(cluster).model_dump()
            cluster_dict["prompt_count"] = prompt_count
            cluster_responses.append(ClusterResponse(**cluster_dict))

        logger.debug("Listed clusters", page=page, page_size=page_size, total=total)

        return ClusterListResponse(
            clusters=cluster_responses,
            total=total,
            page=page,
            page_size=page_size,
        )

    except Exception as e:
        logger.error("Error listing clusters", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "Failed to list clusters", "detail": str(e)},
        )


@router.get(
    "/{cluster_id}",
    response_model=ClusterDetailResponse,
    responses={404: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
)
async def get_cluster(
    cluster_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> ClusterDetailResponse:
    """
    Get cluster details by ID.

    Args:
        cluster_id: Cluster ID
        db: Database session

    Returns:
        Cluster details with prompts

    Raises:
        HTTPException: If cluster not found
    """
    try:
        cluster = await db.get(Cluster, cluster_id)
        if not cluster:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": "Cluster not found", "cluster_id": str(cluster_id)},
            )

        # Get prompts in cluster
        from src.services.clustering import get_clustering_service

        clustering_service = get_clustering_service(db)
        prompts = await clustering_service.get_cluster_prompts(cluster_id)

        prompt_responses = [PromptResponse.model_validate(p) for p in prompts]

        cluster_dict = ClusterResponse.model_validate(cluster).model_dump()
        cluster_dict["prompt_count"] = len(prompts)

        logger.debug("Retrieved cluster", cluster_id=cluster_id, prompts_count=len(prompts))

        return ClusterDetailResponse(
            **cluster_dict,
            prompts=prompt_responses,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error getting cluster", cluster_id=cluster_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "Failed to get cluster", "detail": str(e)},
        )


@router.get(
    "/{cluster_id}/prompts",
    response_model=list[PromptResponse],
    responses={404: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
)
async def get_cluster_prompts(
    cluster_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> list[PromptResponse]:
    """
    Get all prompts in a cluster.

    Args:
        cluster_id: Cluster ID
        db: Database session

    Returns:
        List of prompts in the cluster

    Raises:
        HTTPException: If cluster not found
    """
    try:
        # Verify cluster exists
        cluster = await db.get(Cluster, cluster_id)
        if not cluster:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": "Cluster not found", "cluster_id": str(cluster_id)},
            )

        # Get prompts
        from src.services.clustering import get_clustering_service

        clustering_service = get_clustering_service(db)
        prompts = await clustering_service.get_cluster_prompts(cluster_id)

        logger.debug("Retrieved cluster prompts", cluster_id=cluster_id, count=len(prompts))

        return [PromptResponse.model_validate(p) for p in prompts]

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error getting cluster prompts", cluster_id=cluster_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "Failed to get cluster prompts", "detail": str(e)},
        )

