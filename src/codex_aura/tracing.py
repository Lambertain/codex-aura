"""OpenTelemetry tracing configuration for codex-aura."""

import os
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.jaeger.thrift import JaegerExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor


def configure_tracing(service_name: str = "codex-aura", jaeger_host: str = "localhost", jaeger_port: int = 14268):
    """Configure OpenTelemetry tracing with Jaeger exporter.

    Args:
        service_name: Name of the service for tracing
        jaeger_host: Jaeger collector host
        jaeger_port: Jaeger collector port
    """
    # Set up tracer provider
    trace.set_tracer_provider(TracerProvider())

    # Configure Jaeger exporter
    jaeger_exporter = JaegerExporter(
        agent_host_name=jaeger_host,
        agent_port=jaeger_port,
    )

    # Add span processor
    span_processor = BatchSpanProcessor(jaeger_exporter)
    trace.get_tracer_provider().add_span_processor(span_processor)

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
    FastAPIInstrumentor.instrument_app(app)