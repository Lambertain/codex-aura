"""OpenTelemetry tracing configuration for codex-aura."""

import os
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider

# Check if tracing is enabled
_tracing_enabled = os.getenv("ENABLE_TRACING", "").lower() in ("1", "true", "yes")

try:
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
except ImportError:
    FastAPIInstrumentor = None


def configure_tracing(service_name: str = "codex-aura", jaeger_host: str = "localhost", jaeger_port: int = 14268):
    """Configure OpenTelemetry tracing with Jaeger exporter.

    Tracing is disabled by default. Set ENABLE_TRACING=1 to enable.

    Args:
        service_name: Name of the service for tracing
        jaeger_host: Jaeger collector host
        jaeger_port: Jaeger collector port
    """
    # Set up tracer provider (always needed for get_tracer to work)
    trace.set_tracer_provider(TracerProvider())

    # Skip Jaeger unless explicitly enabled
    if not _tracing_enabled:
        return

    try:
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
        from opentelemetry.exporter.jaeger.thrift import JaegerExporter

        # Configure Jaeger exporter
        jaeger_exporter = JaegerExporter(
            agent_host_name=jaeger_host,
            agent_port=jaeger_port,
        )

        # Add span processor
        span_processor = BatchSpanProcessor(jaeger_exporter)
        trace.get_tracer_provider().add_span_processor(span_processor)
    except ImportError:
        # Jaeger exporter not installed
        pass
    except Exception:
        # If Jaeger is not available, just continue without tracing
        pass

    # Instrument FastAPI (will be called after app creation)
    # FastAPIInstrumentor.instrument_app(app) - called in server.py


def get_tracer(name: str) -> trace.Tracer:
    """Get a tracer instance.

    Args:
        name: Tracer name (usually __name__)

    Returns:
        Configured tracer instance
    """
    return trace.get_tracer(name)


def instrument_app(app):
    """Instrument FastAPI app with OpenTelemetry.

    Args:
        app: FastAPI application instance
    """
    if FastAPIInstrumentor is not None and _tracing_enabled:
        try:
            FastAPIInstrumentor.instrument_app(app)
        except Exception:
            pass  # Ignore instrumentation errors