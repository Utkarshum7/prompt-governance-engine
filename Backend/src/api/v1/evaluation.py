"""Evaluation API endpoints for AI prompt governance telemetry."""

from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from structlog import get_logger

from src.api.dependencies import get_db
from src.models.schemas import ErrorResponse
from src.services.evaluation import EvaluationEngine

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1/evaluation", tags=["evaluation"])


@router.get(
    "/system",
    responses={500: {"model": ErrorResponse}},
)
async def get_system_metrics(
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Get aggregated system-wide performance and accuracy metrics.
    """
    try:
        eval_engine = EvaluationEngine(db)
        metrics = await eval_engine.get_system_wide_metrics()
        return metrics
    except Exception as e:
        logger.error("Error retrieving system metrics", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "Failed to get system evaluation metrics", "detail": str(e)},
        )


@router.get(
    "/cluster/{cluster_id}",
    responses={404: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
)
async def get_cluster_metrics(
    cluster_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Get evaluation metrics for a single cluster.
    """
    try:
        from src.models.database import Cluster
        cluster = await db.get(Cluster, cluster_id)
        if not cluster:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": "Cluster not found", "cluster_id": str(cluster_id)},
            )

        eval_engine = EvaluationEngine(db)
        metrics = await eval_engine.evaluate_cluster(cluster_id)
        return metrics
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error retrieving cluster metrics", cluster_id=cluster_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "Failed to get cluster evaluation metrics", "detail": str(e)},
        )
