"""Payment Scorer (Stub for Phase 2, implemented in Phase 3a)."""

from __future__ import annotations

from typing import Any

from app.extraction import CheckContext


async def payment_scorer(context: CheckContext) -> dict[str, Any]:
    """Stub scorer for payment payee and VPA checks."""
    if not context.payment or not context.payment.get("upi_id"):
        return {
            "status": "not_applicable",
            "risk": None,
            "reasons": [],
            "flags": [],
            "evidence": {"stub": True, "details": "No payment details provided."},
        }

    # Phase 2 stub: returns not_applicable until Phase 3a
    return {
        "status": "not_applicable",
        "risk": None,
        "reasons": [],
        "flags": [],
        "evidence": {
            "stub": True,
            "upi_id": context.payment.get("upi_id"),
            "display_name": context.payment.get("display_name"),
            "details": "Payment scorer stub (will be fully implemented in Phase 3a).",
        },
    }
