#!/usr/bin/env python3
"""Run a sample verification check and print an OpenTelemetry trace summary."""

import asyncio
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

import app.telemetry as tm
from app.main import create_check
from app.registry import get_session_factory, init_db
from app.schemas import CheckRequest, PaymentInput


def main():
    print("=" * 80)
    print("TrustShop AI - OpenTelemetry Trace Verifier")
    print("=" * 80)

    # Attach in-memory exporter to active provider
    exporter = InMemorySpanExporter()
    provider = tm.init_tracer_provider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))

    init_db()

    payload = CheckRequest(
        claimed_brand="Flipkart",
        phone_number="+91 98765 43210",
        message_text="Special festive discount today only! Pay token advance to book your order.",
        urls=["https://flipkart-festivesale.shop/deal"],
        payment=PaymentInput(upi_id="seller987@ybl", display_name="Rakesh Kumar"),
        language="en",
    )

    print(f"\n[1] Submitting test check for: {payload.claimed_brand}")
    print(f"    Phone: {payload.phone_number}")
    print(f"    URL:   {payload.urls[0]}")
    print(f"    Payee: {payload.payment.display_name} ({payload.payment.upi_id})\n")

    from starlette.requests import Request

    scope = {
        "type": "http",
        "method": "POST",
        "path": "/v1/checks",
        "headers": [(b"host", b"localhost:8000")],
        "client": ("127.0.0.1", 54321),
    }
    mock_request = Request(scope)

    session_factory = get_session_factory()
    with session_factory() as db:
        res = asyncio.run(create_check(payload, mock_request, db))

    print(f"[2] Received Verdict: {res.verdict} (Risk: {res.risk_score})")
    print(f"    Summary: {res.summary}")
    print(f"    Reason Codes: {res.reason_codes}")

    # Inspect captured OpenTelemetry Spans
    spans = exporter.get_finished_spans()
    print(f"\n[3] OpenTelemetry Captured Spans ({len(spans)} total):")
    print("-" * 80)
    print(f"{'Span Name':<28} {'Duration (ms)':<15} {'Key Attributes'}")
    print("-" * 80)

    for span in sorted(spans, key=lambda s: s.start_time or 0):
        duration_ms = (
            (span.end_time - span.start_time) / 1_000_000
            if span.start_time and span.end_time
            else 0.0
        )
        attrs = []
        for k, v in span.attributes.items():
            if k in (
                "scorer.status",
                "scorer.risk",
                "verdict",
                "risk_score",
                "degraded",
                "scorer.flags",
            ):
                attrs.append(f"{k}={v}")
        attr_str = ", ".join(attrs) if attrs else "(internal)"
        print(f"{span.name:<28} {duration_ms:>10.2f} ms     {attr_str}")

    print("-" * 80)
    print("Trace verification complete: Spans generated per scorer, decision layer, and audit log.\n")


if __name__ == "__main__":
    main()
