"""FastAPI application entry point."""

import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from src.api.middleware.logging import RequestLoggingMiddleware
from src.api.middleware.rate_limit import RateLimitMiddleware
from src.api.v1 import clusters, evolution, health, prompts, templates
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

# Include web routers (frontend pages)
app.include_router(index.router)
app.include_router(web_prompts.router)
app.include_router(dataset.router)
app.include_router(web_clusters.router)
app.include_router(web_templates.router)
app.include_router(web_evolution.router)


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
    
    # Note: Qdrant collection creation is now done lazily when first needed
    logger.info("Application startup complete - Qdrant collection will be created on first use")


@app.on_event("shutdown")
async def shutdown_event():
    """Application shutdown event."""
    logger.info("Application shutting down")


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

