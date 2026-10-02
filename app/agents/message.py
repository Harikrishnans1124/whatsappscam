"""Message Scorer (Stub for Phase 2, implemented in Phase 3c)."""

from __future__ import annotations

from typing import Any

from app.extraction import CheckContext


async def message_scorer(context: CheckContext) -> dict[str, Any]:
    """Stub scorer for message text and scam pattern analysis."""
    if not context.message_text or not context.message_text.strip():
        return {
            "status": "not_applicable",
            "risk": None,
            "reasons": [],
            "flags": [],
            "evidence": {"stub": True, "details": "No message text provided."},
        }

    return {
        "status": "not_applicable",
        "risk": None,
        "reasons": [],
        "flags": [],
        "evidence": {
            "stub": True,
            "details": "Message scorer stub (will be fully implemented in Phase 3c).",
        },
    }
