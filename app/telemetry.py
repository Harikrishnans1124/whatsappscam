"""OpenTelemetry tracing setup and helpers for TrustShop AI."""

from __future__ import annotations

import logging
import os
from typing import Any

from fastapi import FastAPI
from opentelemetry import trace
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import (
    BatchSpanProcessor,
    ConsoleSpanExporter,
    SimpleSpanProcessor,
)

logger = logging.getLogger(__name__)

_PROVIDER_INITIALIZED = False


def init_tracer_provider() -> TracerProvider:
    """Initialize OpenTelemetry tracer provider with OTLP or fallback processor."""
    global _PROVIDER_INITIALIZED
    if _PROVIDER_INITIALIZED:
        provider = trace.get_tracer_provider()
        if isinstance(provider, TracerProvider):
            return provider

    service_name = os.getenv("OTEL_SERVICE_NAME", "trustshop-api")
    resource = Resource.create({"service.name": service_name})
    provider = TracerProvider(resource=resource)

    otlp_endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
    if otlp_endpoint:
        try:
            from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
                OTLPSpanExporter,
            )

            exporter = OTLPSpanExporter(endpoint=otlp_endpoint, insecure=True)
            provider.add_span_processor(BatchSpanProcessor(exporter))
            logger.info("OpenTelemetry OTLP gRPC exporter configured for %s", otlp_endpoint)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Could not initialize OTLP exporter (%s), falling back to noop", exc)
    else:
        # Development / test mode fallback
        if os.getenv("OTEL_DEBUG_CONSOLE"):
            provider.add_span_processor(SimpleSpanProcessor(ConsoleSpanExporter()))

    trace.set_tracer_provider(provider)
    _PROVIDER_INITIALIZED = True
    return provider


def setup_telemetry(app: FastAPI) -> None:
    """Instrument the FastAPI application with OpenTelemetry."""
    try:
        init_tracer_provider()
        FastAPIInstrumentor.instrument_app(
            app,
            tracer_provider=trace.get_tracer_provider(),
            excluded_urls="healthz,readyz,static",
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to instrument FastAPI with OpenTelemetry: %s", exc)


def get_tracer(name: str = "trustshop-api"):
    """Get or create a named OpenTelemetry tracer."""
    init_tracer_provider()
    return trace.get_tracer(name)


tracer = get_tracer("trustshop-api")


async def traced_scorer(scorer_name: str, coro: Any) -> dict[str, Any]:
    """Execute a guarded scorer coroutine within an OpenTelemetry span."""
    with tracer.start_as_current_span(f"scorer.{scorer_name}") as span:
        span.set_attribute("scorer.name", scorer_name)
        res = await coro
        span.set_attribute("scorer.status", res.get("status", "unknown"))
        if res.get("risk") is not None:
            span.set_attribute("scorer.risk", float(res["risk"]))
        if res.get("flags"):
            span.set_attribute("scorer.flags", ",".join(res["flags"]))
        return res
