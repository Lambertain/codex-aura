"""Prometheus metrics for codex-aura.

Metrics are disabled by default. Set ENABLE_METRICS=1 to enable.
"""

import os
import time
from typing import Optional, TYPE_CHECKING

# Check if metrics are enabled
_metrics_enabled = os.getenv("ENABLE_METRICS", "").lower() in ("1", "true", "yes")

# Lazy imports to avoid hanging on Windows
if TYPE_CHECKING:
    from prometheus_client import Counter, Histogram, Gauge
    from fastapi.responses import Response

# Placeholder metrics (no-op when disabled)
_metrics_initialized = False
_counter_class = None
_histogram_class = None
_gauge_class = None

REQUESTS_TOTAL = None
REQUEST_DURATION = None
GRAPH_SIZE = None
GRAPHS_TOTAL = None
ANALYSIS_DURATION = None
ANALYSIS_FILES = None
CONTEXT_REQUESTS_TOTAL = None
CONTEXT_NODES_RETURNED = None
STORAGE_OPERATIONS_TOTAL = None
HEALTH_CHECKS_TOTAL = None


class NoOpMetric:
    """No-op metric that does nothing when called."""

    def __init__(self, *args, **kwargs):
        pass

    def labels(self, **kwargs):
        return self

    def inc(self, amount=1):
        pass

    def dec(self, amount=1):
        pass

    def set(self, value):
        pass

    def observe(self, amount):
        pass


def _initialize_metrics():
    """Initialize Prometheus metrics if enabled."""
    global _metrics_initialized, _counter_class, _histogram_class, _gauge_class
    global REQUESTS_TOTAL, REQUEST_DURATION, GRAPH_SIZE, GRAPHS_TOTAL
    global ANALYSIS_DURATION, ANALYSIS_FILES, CONTEXT_REQUESTS_TOTAL
    global CONTEXT_NODES_RETURNED, STORAGE_OPERATIONS_TOTAL, HEALTH_CHECKS_TOTAL

    if _metrics_initialized:
        return

    _metrics_initialized = True

    if not _metrics_enabled:
        # Use no-op metrics
        REQUESTS_TOTAL = NoOpMetric()
        REQUEST_DURATION = NoOpMetric()
        GRAPH_SIZE = NoOpMetric()
        GRAPHS_TOTAL = NoOpMetric()
        ANALYSIS_DURATION = NoOpMetric()
        ANALYSIS_FILES = NoOpMetric()
        CONTEXT_REQUESTS_TOTAL = NoOpMetric()
        CONTEXT_NODES_RETURNED = NoOpMetric()
        STORAGE_OPERATIONS_TOTAL = NoOpMetric()
        HEALTH_CHECKS_TOTAL = NoOpMetric()
        return

    try:
        from prometheus_client import Counter, Histogram, Gauge
        _counter_class = Counter
        _histogram_class = Histogram
        _gauge_class = Gauge

        # Request metrics
        REQUESTS_TOTAL = Counter(
            "codex_aura_requests_total",
            "Total requests",
            ["endpoint", "method", "status"]
        )

        REQUEST_DURATION = Histogram(
            "codex_aura_request_duration_seconds",
            "Request duration in seconds",
            ["endpoint", "method"]
        )

        # Graph metrics
        GRAPH_SIZE = Gauge(
            "codex_aura_graph_nodes_total",
            "Number of nodes in graph",
            ["graph_id"]
        )

        GRAPHS_TOTAL = Counter(
            "codex_aura_graphs_created_total",
            "Total graphs created"
        )

        # Analysis metrics
        ANALYSIS_DURATION = Histogram(
            "codex_aura_analysis_duration_seconds",
            "Analysis duration in seconds",
            ["repo_name"]
        )

        ANALYSIS_FILES = Counter(
            "codex_aura_analysis_files_total",
            "Total files analyzed",
            ["repo_name"]
        )

        # Context retrieval metrics
        CONTEXT_REQUESTS_TOTAL = Counter(
            "codex_aura_context_requests_total",
            "Total context requests"
        )

        CONTEXT_NODES_RETURNED = Histogram(
            "codex_aura_context_nodes_returned",
            "Number of context nodes returned",
            ["truncated"]
        )

        # Storage metrics
        STORAGE_OPERATIONS_TOTAL = Counter(
            "codex_aura_storage_operations_total",
            "Total storage operations",
            ["operation", "status"]
        )

        # Health check metrics
        HEALTH_CHECKS_TOTAL = Counter(
            "codex_aura_health_checks_total",
            "Total health checks",
            ["endpoint", "status"]
        )

    except ImportError:
        # prometheus_client not installed, use no-op
        REQUESTS_TOTAL = NoOpMetric()
        REQUEST_DURATION = NoOpMetric()
        GRAPH_SIZE = NoOpMetric()
        GRAPHS_TOTAL = NoOpMetric()
        ANALYSIS_DURATION = NoOpMetric()
        ANALYSIS_FILES = NoOpMetric()
        CONTEXT_REQUESTS_TOTAL = NoOpMetric()
        CONTEXT_NODES_RETURNED = NoOpMetric()
        STORAGE_OPERATIONS_TOTAL = NoOpMetric()
        HEALTH_CHECKS_TOTAL = NoOpMetric()


# Initialize on first import
_initialize_metrics()


def get_metrics_response():
    """Get Prometheus metrics response."""
    from fastapi.responses import Response

    if not _metrics_enabled:
        return Response(
            content="# Metrics disabled. Set ENABLE_METRICS=1 to enable.\n",
            media_type="text/plain"
        )

    try:
        from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
        return Response(
            generate_latest(),
            media_type=CONTENT_TYPE_LATEST
        )
    except ImportError:
        return Response(
            content="# prometheus_client not installed\n",
            media_type="text/plain"
        )


class MetricsMiddleware:
    """Middleware to collect request metrics."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        start_time = time.time()

        # Get request info
        path = scope["path"]
        method = scope["method"]

        # Create a wrapper for send to capture response status
        status_code = [200]  # Default

        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                status_code[0] = message["status"]
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)

            # Record metrics (no-op if disabled)
            duration = time.time() - start_time
            if REQUESTS_TOTAL is not None:
                REQUESTS_TOTAL.labels(
                    endpoint=path,
                    method=method,
                    status=status_code[0]
                ).inc()

            if REQUEST_DURATION is not None:
                REQUEST_DURATION.labels(
                    endpoint=path,
                    method=method
                ).observe(duration)

        except Exception as e:
            # Record failed request
            duration = time.time() - start_time
            if REQUESTS_TOTAL is not None:
                REQUESTS_TOTAL.labels(
                    endpoint=path,
                    method=method,
                    status=500
                ).inc()

            if REQUEST_DURATION is not None:
                REQUEST_DURATION.labels(
                    endpoint=path,
                    method=method
                ).observe(duration)

            raise
