"""Health check endpoints."""

from datetime import datetime
from typing import Dict

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from structlog import get_logger

from src.api.dependencies import get_db
from src.config.settings import get_settings

logger = get_logger(__name__)

router = APIRouter(prefix="/health", tags=["health"])


@router.get("")
async def health_check() -> Dict[str, str]:
    """
    Basic health check endpoint.

    Returns:
        Health status
    """
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "service": "portkey-prompt-parser",
    }


@router.get("/ready")
async def readiness_check(db: AsyncSession = Depends(get_db)) -> Dict[str, str]:
    """
    Readiness check endpoint - verifies database connectivity.

    Args:
        db: Database session

    Returns:
        Readiness status

    Raises:
        HTTPException: If database is not ready
    """
    try:
        # Test database connection
        result = await db.execute(text("SELECT 1"))
        result.scalar()

        settings = get_settings()
        return {
            "status": "ready",
            "timestamp": datetime.utcnow().isoformat(),
            "service": "portkey-prompt-parser",
            "database": "connected",
            "environment": settings.app.environment,
        }
    except Exception as e:
        logger.error("Readiness check failed", error=str(e))
        raise HTTPException(
            status_code=503,
            detail={
                "status": "not_ready",
                "timestamp": datetime.utcnow().isoformat(),
                "service": "portkey-prompt-parser",
                "database": "disconnected",
                "error": str(e),
            },
        )

