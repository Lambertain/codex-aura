"""Prometheus metrics for codex-aura."""

from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST
from fastapi.responses import Response
import time
from typing import Optional

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


def get_metrics_response() -> Response:
    """Get Prometheus metrics response."""
    return Response(
        generate_latest(),
        media_type=CONTENT_TYPE_LATEST
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

            # Record metrics
            duration = time.time() - start_time
            REQUESTS_TOTAL.labels(
                endpoint=path,
                method=method,
                status=status_code[0]
            ).inc()

            REQUEST_DURATION.labels(
                endpoint=path,
                method=method
            ).observe(duration)

        except Exception as e:
            # Record failed request
            duration = time.time() - start_time
            REQUESTS_TOTAL.labels(
                endpoint=path,
                method=method,
                status=500
            ).inc()

            REQUEST_DURATION.labels(
                endpoint=path,
                method=method
            ).observe(duration)

            raise