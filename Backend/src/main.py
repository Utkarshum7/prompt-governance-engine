"""FastAPI application entry point."""

import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from src.api.middleware.logging import RequestLoggingMiddleware
from src.api.middleware.rate_limit import RateLimitMiddleware
from src.api.v1 import clusters, evolution, health, prompts, templates, evaluation
from src.api.v1.web import clusters as web_clusters, dataset, evolution as web_evolution, index, prompts as web_prompts, templates as web_templates
from src.config.settings import get_settings
from src.utils.metrics import metrics_endpoint

# Configure structured logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer(),
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger(__name__)

# Load settings
settings = get_settings()

# Create FastAPI app
app = FastAPI(
    title="Smart Prompt Parser & Canonicalisation Engine",
    description="Production-grade AI system for clustering semantically equivalent prompts",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add request logging middleware (first, to capture all requests)
app.add_middleware(RequestLoggingMiddleware)

# Add rate limiting middleware (after CORS)
app.add_middleware(RateLimitMiddleware)

# Include API routers
app.include_router(health.router)
app.include_router(prompts.router)
app.include_router(clusters.router)
app.include_router(templates.router)
app.include_router(evolution.router)
app.include_router(evaluation.router)

# Include web routers (frontend pages)
app.include_router(index.router)
app.include_router(web_prompts.router)
app.include_router(dataset.router)
app.include_router(web_clusters.router)
app.include_router(web_templates.router)
app.include_router(web_evolution.router)


import asyncio
from sqlalchemy import text
from src.services.scheduler import run_periodic_drift_detection

async def validate_dependencies():
    """Validate all external service connections on startup."""
    logger.info("Validating external service dependencies...")
    
    # 1. Validate PostgreSQL
    try:
        from src.api.dependencies import get_session_factory
        session_factory = get_session_factory()
        async with session_factory() as session:
            await session.execute(text("SELECT 1"))
        logger.info("✓ PostgreSQL connection validated successfully (Neon)")
    except Exception as e:
        logger.error("✗ PostgreSQL connection validation failed", error=str(e))
        raise RuntimeError(f"Database connection failed: {e}") from e
        
    # 2. Validate Redis
    try:
        from src.clients.redis import get_redis_client
        redis_client = get_redis_client()
        pong = await redis_client.ping()
        if pong:
            logger.info("✓ Redis connection validated successfully (Upstash)")
        else:
            raise ValueError("Redis ping returned False")
    except Exception as e:
        logger.error("✗ Redis connection validation failed", error=str(e))
        raise RuntimeError(f"Redis connection failed: {e}") from e
        
    # 3. Validate Qdrant
    try:
        from src.clients.qdrant import get_async_qdrant_client
        qdrant_client = get_async_qdrant_client()
        await qdrant_client.ensure_collection()
        logger.info("✓ Qdrant connection validated successfully (Qdrant Cloud)")
    except Exception as e:
        logger.error("✗ Qdrant connection validation failed", error=str(e))
        raise RuntimeError(f"Qdrant connection failed: {e}") from e

    logger.info("✓ All startup dependencies validated successfully")


@app.on_event("startup")
async def startup_event():
    """Application startup event."""
    logger.info(
        "Application starting",
        environment=settings.app.environment,
        log_level=settings.app.log_level,
        api_host=settings.app.api.host,
        api_port=settings.app.api.port,
    )
    
    # Validate dependencies (fail fast in production)
    try:
        await validate_dependencies()
    except Exception as e:
        logger.critical("Dependency validation failed. Shutting down application.", error=str(e))
        raise e
    
    # Note: Qdrant collection creation is now done lazily when first needed
    logger.info("Application startup complete - Qdrant collection will be created on first use")

    # Start the async generic Job Scheduler
    from src.services.scheduler import (
        get_job_scheduler,
        run_periodic_drift_detection,
        run_periodic_evaluation_metrics,
        run_periodic_cache_cleanup,
        run_periodic_dataset_refresh,
    )
    
    scheduler = get_job_scheduler()
    scheduler.register("drift_detection", run_periodic_drift_detection, 21600)  # every 6 hours
    scheduler.register("evaluation_metrics", run_periodic_evaluation_metrics, 43200)  # every 12 hours
    scheduler.register("cache_cleanup", run_periodic_cache_cleanup, 86400)  # every 24 hours
    scheduler.register("dataset_refresh", run_periodic_dataset_refresh, 3600)  # every 1 hour
    
    scheduler.start()
    app.state.scheduler = scheduler
    logger.info("Generic Job Scheduler started with registered background tasks")


@app.on_event("shutdown")
async def shutdown_event():
    """Application shutdown event."""
    logger.info("Application shutting down")
    
    # Stop periodic background scheduled jobs
    if hasattr(app.state, "scheduler"):
        await app.state.scheduler.stop()
        logger.info("Scheduler background tasks stopped successfully")


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "service": "Smart Prompt Parser & Canonicalisation Engine",
        "version": "0.1.0",
        "status": "running",
        "docs": "/docs",
    }


@app.get("/metrics")
async def metrics(request: Request):
    """Prometheus metrics endpoint."""
    return await metrics_endpoint(request)

