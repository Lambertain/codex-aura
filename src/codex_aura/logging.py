"""Structured logging configuration for codex-aura."""

import os
import uuid
import structlog
from typing import Any, Dict


def configure_logging(log_level: str = "INFO") -> None:
    """Configure structured logging with JSON output and request ID tracking.

    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    """
    # Set log level
    import logging
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)
    logging.basicConfig(level=numeric_level)

    # Configure structlog
    structlog.configure(
        processors=[
            # Add request_id if available in context
            _add_request_id,
            # Add timestamp
            structlog.processors.TimeStamper(fmt="iso"),
            # Add log level
            structlog.processors.add_log_level,
            # JSON renderer
            structlog.processors.JSONRenderer()
        ],
        # Context variables that should be added to all logs
        context_class=dict,
        logger_factory=structlog.WriteLoggerFactory(),
        wrapper_class=structlog.make_filtering_bound_logger(numeric_level),
        cache_logger_on_first_use=True,
    )


def _add_request_id(logger: Any, method_name: str, event_dict: Dict[str, Any]) -> Dict[str, Any]:
    """Add request_id to log event if available in context."""
    from structlog.contextvars import get_contextvars

    context = get_contextvars()
    if "request_id" in context:
        event_dict["request_id"] = context["request_id"]

    return event_dict


def get_logger(name: str) -> Any:
    """Get a structured logger instance.

    Args:
        name: Logger name (usually __name__)

    Returns:
        Configured logger instance
    """
    return structlog.get_logger(name)


def generate_request_id() -> str:
    """Generate a unique request ID.

    Returns:
        UUID-based request ID string
    """
    return str(uuid.uuid4())


# Context manager for request ID
class RequestContext:
    """Context manager for setting request ID in logging context."""

    def __init__(self, request_id: str | None = None):
        self.request_id = request_id or generate_request_id()
        self.token = None

    def __enter__(self):
        from structlog.contextvars import bind_contextvars
        self.token = bind_contextvars(request_id=self.request_id)
        return self.request_id

    def __exit__(self, exc_type, exc_val, exc_tb):
        from structlog.contextvars import unbind_contextvars
        if self.token:
            unbind_contextvars(self.token)