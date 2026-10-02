"""Brand Identity Scorer.

Verifies whether the submitted contact channels (phone number, domain URLs)
match the brand's verified official registry records.
"""

from __future__ import annotations

import datetime as dt
from typing import Any

from app.extraction import CheckContext


def evaluate_brand_identity(
    context: CheckContext,
    stale_after_days: int = 90,
    reference_date: dt.date | None = None,
) -> dict[str, Any]:
    """Evaluate brand identity for a given CheckContext.
    Returns standard scorer dictionary:
    {
        "status": "ok" | "not_applicable" | "failed",
        "risk": float | None,
        "reasons": list[str],
        "flags": list[str],
        "evidence": dict
    }
    """
    brand_info = context.brand

    # 1. No brand claim or detection
    if not brand_info or not brand_info.get("claimed"):
        return {
            "status": "not_applicable",
            "risk": None,
            "reasons": [],
            "flags": [],
            "evidence": {
                "outcome": "NO_BRAND_CLAIM",
                "details": "No brand claim was provided or detected.",
            },
        }

    # 2. Claimed brand is not in registry
    if not brand_info.get("in_registry") or not brand_info.get("brand_data"):
        claimed_name = brand_info.get("claimed") or "Unknown"
        return {
            "status": "ok",
            "risk": 0.20,  # Neutral unverified risk
            "reasons": ["BRAND_NOT_IN_REGISTRY"],
            "flags": [],
            "evidence": {
                "outcome": "UNKNOWN_BRAND",
                "claimed_brand": claimed_name,
                "details": f"Brand '{claimed_name}' is not in the official registry. Cannot verify against official channels.",
            },
        }

    brand_data = brand_info["brand_data"]
    official_domains = [d.lower() for d in brand_data.get("official_domains", [])]
    official_phones = [p.strip() for p in brand_data.get("official_phones", [])]
    brand_name = brand_data.get("name", brand_info.get("claimed"))
    brand_slug = brand_data.get("slug")

    # Check for stale registry entry
    ref = reference_date or dt.datetime.now(dt.timezone.utc).date()
    latest_verified_date: dt.date | None = None
    for src in brand_data.get("sources", []):
        try:
            v_date = dt.date.fromisoformat(src.get("verified_on", ""))
            if latest_verified_date is None or v_date > latest_verified_date:
                latest_verified_date = v_date
        except (ValueError, TypeError):
            continue

    is_stale = False
    if latest_verified_date:
        age_days = (ref - latest_verified_date).days
        if age_days > stale_after_days:
            is_stale = True
    else:
        is_stale = True

    # 3. Check submitted channels against official brand channels
    phone_checked = False
    phone_matched = False
    mismatched_phones: list[str] = []
    matched_phones: list[str] = []

    # Check primary phone if valid
    phones_to_check = []
    if context.phone.get("valid") and context.phone.get("e164"):
        phones_to_check.append(context.phone["e164"])

    # Check any extracted phones from text
    for ep in context.extracted_phones:
        if ep.get("valid") and ep.get("e164") and ep["e164"] not in phones_to_check:
            phones_to_check.append(ep["e164"])

    if phones_to_check:
        phone_checked = True
        for ph in phones_to_check:
            if ph in official_phones:
                matched_phones.append(ph)
            else:
                mismatched_phones.append(ph)
        phone_matched = len(matched_phones) > 0 and len(mismatched_phones) == 0

    # Check URLs / domains
    domain_checked = False
    domain_matched = False
    matched_domains: list[str] = []
    mismatched_domains: list[str] = []

    if context.urls:
        domain_checked = True
        for u in context.urls:
            reg = u.get("registrable_domain", "").lower()
            if reg in official_domains:
                matched_domains.append(reg)
            else:
                mismatched_domains.append(reg)
        domain_matched = len(matched_domains) > 0 and len(mismatched_domains) == 0

    evidence: dict[str, Any] = {
        "brand": brand_name,
        "slug": brand_slug,
        "official_domains": official_domains,
        "official_phones": official_phones,
        "payment_policy": brand_data.get("payment_policy", ""),
        "latest_verified_on": latest_verified_date.isoformat() if latest_verified_date else None,
        "is_stale": is_stale,
        "phone_checked": phone_checked,
        "phone_matched": phone_matched,
        "matched_phones": matched_phones,
        "mismatched_phones": mismatched_phones,
        "domain_checked": domain_checked,
        "domain_matched": domain_matched,
        "matched_domains": matched_domains,
        "mismatched_domains": mismatched_domains,
    }

    reasons: list[str] = []
    flags: list[str] = []

    # Mismatch condition: any submitted channel did not match official records
    has_mismatch = (phone_checked and len(mismatched_phones) > 0) or (domain_checked and len(mismatched_domains) > 0)

    # Match condition: at least one channel checked, matched, and NO channel mismatched
    has_match = (phone_checked or domain_checked) and not has_mismatch and (len(matched_phones) > 0 or len(matched_domains) > 0)

    if has_mismatch:
        outcome = "MISMATCH"
        risk = 0.85
        flags.append("BRAND_CHANNEL_MISMATCH")
        reasons.append("BRAND_CHANNEL_MISMATCH")
        evidence["outcome"] = outcome
        evidence["details"] = (
            f"The contact channel does not match {brand_name}'s official published channels. "
            f"Official domains: {', '.join(official_domains) or 'None'}. "
            f"Official phones: {', '.join(official_phones) or 'None (brand does not sell via phone numbers)'}."
        )
    elif has_match:
        outcome = "MATCH"
        risk = 0.0
        reasons.append("BRAND_CHANNEL_MATCH")
        evidence["outcome"] = outcome
        evidence["details"] = f"Submitted contact channel matches {brand_name}'s verified official registry records."
    else:
        # Brand in registry, but no phone or URL was provided to verify
        outcome = "NO_CHANNELS_TO_VERIFY"
        risk = 0.10
        evidence["outcome"] = outcome
        evidence["details"] = f"Brand is known ({brand_name}), but no phone number or link was provided to check."

    if is_stale:
        reasons.append("REGISTRY_STALE")

    return {
        "status": "ok",
        "risk": risk,
        "reasons": reasons,
        "flags": flags,
        "evidence": evidence,
    }


async def brand_identity_scorer(context: CheckContext) -> dict[str, Any]:
    """Async wrapper for the brand identity scorer."""
    return evaluate_brand_identity(context)
