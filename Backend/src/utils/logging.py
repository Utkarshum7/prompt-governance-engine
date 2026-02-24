"""Structured logging utilities with request IDs and correlation IDs."""

import contextvars
import uuid
from typing import Any, Dict, Optional

import structlog

# Context variables for request tracking
request_id_var: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar("request_id", default=None)
correlation_id_var: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar("correlation_id", default=None)


def get_request_id() -> Optional[str]:
    """Get current request ID."""
    return request_id_var.get()


def set_request_id(request_id: Optional[str] = None) -> str:
    """
    Set request ID in context.

    Args:
        request_id: Optional request ID. If None, generates a new UUID.

    Returns:
        Request ID string
    """
    if request_id is None:
        request_id = str(uuid.uuid4())
    request_id_var.set(request_id)
    return request_id


def get_correlation_id() -> Optional[str]:
    """Get current correlation ID."""
    return correlation_id_var.get()


def set_correlation_id(correlation_id: Optional[str] = None) -> str:
    """
    Set correlation ID in context.

    Args:
        correlation_id: Optional correlation ID. If None, generates a new UUID.

    Returns:
        Correlation ID string
    """
    if correlation_id is None:
        correlation_id = str(uuid.uuid4())
    correlation_id_var.set(correlation_id)
    return correlation_id


def redact_sensitive_data(data: Any) -> Any:
    """
    Redact sensitive data from log entries.

    Args:
        data: Data to redact

    Returns:
        Data with sensitive fields redacted
    """
    if not isinstance(data, dict):
        return data

    sensitive_keys = {
        "password",
        "api_key",
        "apiKey",
        "secret",
        "token",
        "authorization",
        "auth",
        "credential",
        "private_key",
        "access_key",
    }

    redacted = {}
    for key, value in data.items():
        key_lower = key.lower()
        if any(sensitive in key_lower for sensitive in sensitive_keys):
            redacted[key] = "***REDACTED***"
        elif isinstance(value, dict):
            redacted[key] = redact_sensitive_data(value)
        elif isinstance(value, list):
            redacted[key] = [
                redact_sensitive_data(item) if isinstance(item, dict) else item
                for item in value
            ]
        else:
            redacted[key] = value

    return redacted


def get_logger(name: Optional[str] = None) -> structlog.BoundLogger:
    """
    Get structured logger with context.

    Args:
        name: Optional logger name

    Returns:
        Bound logger with request/correlation IDs
    """
    logger = structlog.get_logger(name)

    # Add context variables to logger
    request_id = get_request_id()
    correlation_id = get_correlation_id()

    if request_id or correlation_id:
        context: Dict[str, Any] = {}
        if request_id:
            context["request_id"] = request_id
        if correlation_id:
            context["correlation_id"] = correlation_id
        logger = logger.bind(**context)

    return logger


def configure_logging(log_level: str = "INFO"):
    """
    Configure structured logging.

    Args:
        log_level: Log level (DEBUG, INFO, WARNING, ERROR)
    """
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
            # Add context processors
            structlog.processors.add_log_level,
            # Redact sensitive data
            lambda logger, method_name, event_dict: redact_sensitive_data(event_dict),
            structlog.processors.JSONRenderer(),
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

