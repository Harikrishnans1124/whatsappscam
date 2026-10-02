"""Number Scorer for TrustShop AI.

Analyzes phone numbers using:
1. Phone validity and type classification via phonenumbers.
2. Community crowd-sourced reports using privacy-preserving HMAC identifier hashes.
3. Brand channel consistency (personal mobile vs enterprise official line).
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.config import settings
from app.extraction import CheckContext
from app.registry import count_distinct_reporters, get_session_factory


async def number_scorer(
    context: CheckContext,
    db_session: Session | None = None,
) -> dict[str, Any]:
    """Score phone number for validity, reputation, and report count."""
    phone = context.phone
    if not phone or not phone.get("raw"):
        return {
            "status": "not_applicable",
            "risk": None,
            "reasons": [],
            "flags": [],
            "evidence": {"details": "No phone number provided."},
        }

    # 1. Check validity
    if not phone.get("valid"):
        return {
            "status": "ok",
            "risk": 0.85,
            "reasons": ["INVALID_PHONE_NUMBER"],
            "flags": [],
            "evidence": {
                "valid": False,
                "raw": phone.get("raw"),
                "details": "Phone number is not valid according to international numbering plans.",
            },
        }

    e164 = phone.get("e164") or ""
    phone_type = phone.get("type", "UNKNOWN")
    reasons: list[str] = []
    flags: list[str] = []
    evidence: dict[str, Any] = {
        "valid": True,
        "e164": e164,
        "type": phone_type,
    }

    # 2. Check community reports count
    reporter_count = 0
    if e164:
        if db_session is not None:
            reporter_count = count_distinct_reporters(db_session, e164)
        else:
            try:
                session_factory = get_session_factory()
                with session_factory() as session:
                    reporter_count = count_distinct_reporters(session, e164)
            except (SQLAlchemyError, OSError, ValueError):
                reporter_count = 0

    evidence["distinct_reporters"] = reporter_count
    reports_cfg = settings.get("reports", {})
    min_distinct = reports_cfg.get("min_distinct_reporters", 3)

    if reporter_count >= min_distinct:
        reasons.append("REPORTED_BY_USERS")
        # Scaled risk based on report volume: min 0.50, max 0.85
        risk = min(0.85, 0.40 + 0.10 * (reporter_count - min_distinct + 1))
    else:
        # 3. Brand consistency check
        brand_info = context.brand
        if brand_info and brand_info.get("in_registry") and brand_info.get("brand_data"):
            official_phones = brand_info["brand_data"].get("official_phones", [])
            if e164 in official_phones:
                risk = 0.0
                evidence["is_official_phone"] = True
            else:
                evidence["is_official_phone"] = False
                # Personal mobile claiming to represent a brand
                if phone_type in ("MOBILE", "FIXED_LINE_OR_MOBILE"):
                    risk = 0.30
                else:
                    risk = 0.20
        else:
            risk = 0.10

    return {
        "status": "ok",
        "risk": round(risk, 2),
        "reasons": reasons,
        "flags": flags,
        "evidence": evidence,
    }
