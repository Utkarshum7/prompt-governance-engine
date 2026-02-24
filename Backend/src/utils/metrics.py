"""Prometheus metrics for monitoring."""

import time
from typing import Optional

from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST
from starlette.requests import Request
from starlette.responses import Response

# Request metrics
http_requests_total = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "endpoint", "status_code"],
)

http_request_duration_seconds = Histogram(
    "http_request_duration_seconds",
    "HTTP request duration in seconds",
    ["method", "endpoint"],
    buckets=[0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0],
)

# Business metrics
prompts_processed_total = Counter(
    "prompts_processed_total",
    "Total prompts processed",
    ["status"],
)

prompts_rejected_total = Counter(
    "prompts_rejected_total",
    "Total prompts rejected",
    ["reason"],
)

clusters_created_total = Counter(
    "clusters_created_total",
    "Total clusters created",
)

templates_extracted_total = Counter(
    "templates_extracted_total",
    "Total templates extracted",
    ["model"],
)

# Token usage metrics
tokens_used_total = Counter(
    "tokens_used_total",
    "Total tokens used",
    ["model", "operation"],
)

# System metrics
active_clusters = Gauge(
    "active_clusters",
    "Number of active clusters",
)

active_templates = Gauge(
    "active_templates",
    "Number of active templates",
)

cache_hits_total = Counter(
    "cache_hits_total",
    "Total cache hits",
    ["cache_type"],
)

cache_misses_total = Counter(
    "cache_misses_total",
    "Total cache misses",
    ["cache_type"],
)


class MetricsMiddleware:
    """Middleware for collecting Prometheus metrics."""

    async def __call__(self, request: Request, call_next):
        """
        Collect metrics for request.

        Args:
            request: HTTP request
            call_next: Next middleware/handler

        Returns:
            HTTP response
        """
        # Skip metrics endpoint
        if request.url.path == "/metrics":
            return await call_next(request)

        start_time = time.time()
        method = request.method
        endpoint = request.url.path

        try:
            response = await call_next(request)
            status_code = response.status_code

            # Record metrics
            duration = time.time() - start_time
            http_requests_total.labels(method=method, endpoint=endpoint, status_code=status_code).inc()
            http_request_duration_seconds.labels(method=method, endpoint=endpoint).observe(duration)

            return response

        except Exception as e:
            # Record error
            http_requests_total.labels(method=method, endpoint=endpoint, status_code=500).inc()
            raise


async def metrics_endpoint(request: Request) -> Response:
    """
    Prometheus metrics endpoint.

    Args:
        request: HTTP request

    Returns:
        Metrics response
    """
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


def record_prompt_processed(status: str):
    """
    Record prompt processed metric.

    Args:
        status: Processing status (accepted, rejected, error)
    """
    prompts_processed_total.labels(status=status).inc()


def record_prompt_rejected(reason: str):
    """
    Record prompt rejected metric.

    Args:
        reason: Rejection reason
    """
    prompts_rejected_total.labels(reason=reason).inc()


def record_cluster_created():
    """Record cluster created metric."""
    clusters_created_total.inc()


def record_template_extracted(model: str):
    """
    Record template extracted metric.

    Args:
        model: Model used for extraction
    """
    templates_extracted_total.labels(model=model).inc()


def record_tokens_used(model: str, operation: str, tokens: int):
    """
    Record token usage metric.

    Args:
        model: Model name
        operation: Operation type (embedding, completion, etc.)
        tokens: Number of tokens used
    """
    tokens_used_total.labels(model=model, operation=operation).inc(tokens)


def record_cache_hit(cache_type: str):
    """
    Record cache hit metric.

    Args:
        cache_type: Type of cache (embedding, similarity, etc.)
    """
    cache_hits_total.labels(cache_type=cache_type).inc()


def record_cache_miss(cache_type: str):
    """
    Record cache miss metric.

    Args:
        cache_type: Type of cache (embedding, similarity, etc.)
    """
    cache_misses_total.labels(cache_type=cache_type).inc()


def update_active_clusters(count: int):
    """
    Update active clusters gauge.

    Args:
        count: Number of active clusters
    """
    active_clusters.set(count)


def update_active_templates(count: int):
    """
    Update active templates gauge.

    Args:
        count: Number of active templates
    """
    active_templates.set(count)

