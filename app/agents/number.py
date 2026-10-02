"""Number Scorer (Stub for Phase 2, implemented in Phase 3d)."""

from __future__ import annotations

from typing import Any

from app.extraction import CheckContext


async def number_scorer(context: CheckContext) -> dict[str, Any]:
    """Stub scorer for number validity and community reports."""
    if not context.phone or not context.phone.get("valid"):
        return {
            "status": "not_applicable",
            "risk": None,
            "reasons": [],
            "flags": [],
            "evidence": {"stub": True, "details": "No valid phone number provided."},
        }

    return {
        "status": "not_applicable",
        "risk": None,
        "reasons": [],
        "flags": [],
        "evidence": {
            "stub": True,
            "e164": context.phone.get("e164"),
            "details": "Number scorer stub (will be fully implemented in Phase 3d).",
        },
    }
