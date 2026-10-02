"""Domain Scorer (Stub for Phase 2, implemented in Phase 3b)."""

from __future__ import annotations

from typing import Any

from app.extraction import CheckContext


async def domain_scorer(context: CheckContext) -> dict[str, Any]:
    """Stub scorer for domain RDAP age and lookalike detection."""
    if not context.urls:
        return {
            "status": "not_applicable",
            "risk": None,
            "reasons": [],
            "flags": [],
            "evidence": {"stub": True, "details": "No URLs provided."},
        }

    return {
        "status": "not_applicable",
        "risk": None,
        "reasons": [],
        "flags": [],
        "evidence": {
            "stub": True,
            "domains": [u.get("registrable_domain") for u in context.urls],
            "details": "Domain scorer stub (will be fully implemented in Phase 3b).",
        },
    }
