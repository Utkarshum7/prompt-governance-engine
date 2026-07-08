"""Health check endpoints."""

from datetime import datetime
from typing import Any, Dict

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
async def readiness_check(db: AsyncSession = Depends(get_db)) -> Dict[str, Any]:
    """
    Readiness check endpoint - verifies database, redis, and qdrant connectivity.

    Args:
        db: Database session

    Returns:
        Readiness status details

    Raises:
        HTTPException: If any service is not ready
    """
    status_details = {
        "status": "ready",
        "timestamp": datetime.utcnow().isoformat(),
        "service": "portkey-prompt-parser",
        "database": "disconnected",
        "redis": "disconnected",
        "qdrant": "disconnected",
    }
    
    # 1. Test database connection (Neon)
    try:
        result = await db.execute(text("SELECT 1"))
        result.scalar()
        status_details["database"] = "connected"
    except Exception as e:
        logger.error("Database readiness check failed", error=str(e))
        status_details["status"] = "not_ready"
        status_details["database"] = f"error: {str(e)}"

    # 2. Test Redis connection (Upstash)
    try:
        from src.clients.redis import get_redis_client
        redis_client = get_redis_client()
        if await redis_client.ping():
            status_details["redis"] = "connected"
        else:
            status_details["status"] = "not_ready"
            status_details["redis"] = "ping failed"
    except Exception as e:
        logger.error("Redis readiness check failed", error=str(e))
        status_details["status"] = "not_ready"
        status_details["redis"] = f"error: {str(e)}"

    # 3. Test Qdrant connection (Qdrant Cloud)
    try:
        from src.clients.qdrant import get_async_qdrant_client
        qdrant_client = get_async_qdrant_client()
        if await qdrant_client.ensure_collection():
            status_details["qdrant"] = "connected"
        else:
            status_details["status"] = "not_ready"
            status_details["qdrant"] = "collection not ready"
    except Exception as e:
        logger.error("Qdrant readiness check failed", error=str(e))
        status_details["status"] = "not_ready"
        status_details["qdrant"] = f"error: {str(e)}"

    if status_details["status"] != "ready":
        raise HTTPException(
            status_code=503,
            detail=status_details,
        )

    return status_details

