"""Tests for OpenTelemetry tracing instrumentation and scorer span generation."""

import pytest
from fastapi.testclient import TestClient
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from app.main import app
from app.telemetry import init_tracer_provider, traced_scorer


@pytest.fixture
def memory_exporter():
    exporter = InMemorySpanExporter()
    provider = init_tracer_provider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    yield exporter
    exporter.clear()


@pytest.fixture
def client():
    return TestClient(app)


def test_traced_scorer_records_attributes():
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    test_tracer = provider.get_tracer("test-tracer")

    import app.telemetry as tm
    orig_tracer = tm.tracer
    tm.tracer = test_tracer

    try:
        import asyncio

        async def dummy_scorer():
            return {
                "status": "ok",
                "risk": 0.85,
                "flags": ["OTP_REQUEST"],
                "reasons": ["OTP_REQUEST"],
            }

        res = asyncio.run(traced_scorer("message", dummy_scorer()))
        assert res["risk"] == 0.85

        spans = exporter.get_finished_spans()
        assert len(spans) == 1
        span = spans[0]
        assert span.name == "scorer.message"
        assert span.attributes["scorer.name"] == "message"
        assert span.attributes["scorer.status"] == "ok"
        assert span.attributes["scorer.risk"] == 0.85
        assert span.attributes["scorer.flags"] == "OTP_REQUEST"
    finally:
        tm.tracer = orig_tracer


def test_api_check_generates_spans(client: TestClient, memory_exporter: InMemorySpanExporter):
    resp = client.post(
        "/v1/checks",
        json={
            "claimed_brand": "Flipkart",
            "phone_number": "+91 1800 202 9898",
        },
    )
    assert resp.status_code == 200

    spans = memory_exporter.get_finished_spans()
    span_names = [s.name for s in spans]

    # Verify scorer child spans are recorded
    assert any("scorer.brand_identity" in name for name in span_names)
    assert any("decision_layer" in name for name in span_names)
    assert any("audit_log" in name for name in span_names)

    # Privacy check: Ensure raw chat or raw phone numbers are NOT placed into span attributes
    for s in spans:
        for attr_key, attr_val in s.attributes.items():
            assert "raw_chat" not in attr_key.lower()
            if isinstance(attr_val, str):
                assert "+91 1800 202 9898" not in attr_val
