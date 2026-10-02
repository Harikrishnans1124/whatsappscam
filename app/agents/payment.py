"""Payment Scorer for TrustShop AI.

Evaluates payment details (UPI ID and payee display name) against:
- Brand's verified legal names and aliases using rapidfuzz token_set_ratio.
- Company vs personal payee classification.
- Phone-number style UPI handle detection.
"""

from __future__ import annotations

import re
from typing import Any

from rapidfuzz import fuzz

from app.extraction import CheckContext

# Common tokens indicating a business, firm, or corporate entity
COMPANY_INDICATOR_TOKENS = {
    "pvt",
    "private",
    "ltd",
    "limited",
    "llp",
    "corp",
    "corporation",
    "inc",
    "incorporated",
    "co",
    "company",
    "enterprises",
    "enterprise",
    "solutions",
    "services",
    "technologies",
    "tech",
    "retail",
    "stores",
    "store",
    "industries",
    "holdings",
    "payments",
    "merchant",
    "trading",
    "agency",
    "associates",
    "ventures",
}

# Regex for phone-number based UPI usernames (e.g. 9876543210@upi, 919876543210@paytm)
PHONE_UPI_REGEX = re.compile(r"^(\+?91)?[6-9]\d{9}$")


def normalize_entity_name(name: str) -> str:
    """Normalize company and entity names for fuzzy comparison.
    Expands common abbreviations (pvt -> private, ltd -> limited) and strips punctuation.
    """
    if not name:
        return ""
    text = name.lower()
    # Normalize punctuation to spaces
    text = re.sub(r"[^\w\s]", " ", text)
    # Standardize common corporate abbreviations
    replacements = {
        r"\bpvt\b": "private",
        r"\bltd\b": "limited",
        r"\bcorp\b": "corporation",
        r"\binc\b": "incorporated",
        r"\bco\b": "company",
        r"\bintl\b": "international",
    }
    for pattern, repl in replacements.items():
        text = re.sub(pattern, repl, text)
    # Collapse multiple whitespaces
    return re.sub(r"\s+", " ", text).strip()


def is_personal_name(display_name: str) -> bool:
    """Determine if a display name resembles an individual's personal name rather than a company."""
    if not display_name or not display_name.strip():
        return False
    words = re.findall(r"\b\w+\b", display_name.lower())
    if not words:
        return False
    # If any token is a known company indicator, it is not considered a personal name
    for w in words:
        if w in COMPANY_INDICATOR_TOKENS:
            return False
    return True


def is_phone_number_upi(upi_id: str) -> bool:
    """Check if the VPA username consists of a 10-digit Indian mobile number."""
    if not upi_id or "@" not in upi_id:
        return False
    username = upi_id.split("@")[0].strip()
    return bool(PHONE_UPI_REGEX.match(username))


async def payment_scorer(context: CheckContext) -> dict[str, Any]:
    """Score payment details against brand records and scam risk patterns."""
    payment_info = context.payment or {}
    display_name = payment_info.get("display_name")
    upi_id = payment_info.get("upi_id")

    # If no explicit UPI, check extracted UPIs from message
    if not upi_id and context.upi_ids:
        upi_id = context.upi_ids[0]

    # If neither display name nor UPI ID provided, scorer is not applicable
    if not display_name and not upi_id:
        return {
            "status": "not_applicable",
            "risk": None,
            "reasons": [],
            "flags": [],
            "evidence": {"details": "No payment details (UPI ID or payee name) provided."},
        }

    reasons: list[str] = []
    flags: list[str] = []
    evidence: dict[str, Any] = {
        "upi_id": upi_id,
        "display_name": display_name,
    }

    # 1. Analyze UPI handle structure
    phone_upi = is_phone_number_upi(upi_id) if upi_id else False
    evidence["is_phone_upi"] = phone_upi
    if phone_upi:
        reasons.append("PHONE_STYLE_UPI")

    # 2. Check brand context
    brand_info = context.brand
    has_registry_brand = bool(brand_info and brand_info.get("in_registry") and brand_info.get("brand_data"))
    brand_data = brand_info.get("brand_data") if has_registry_brand else None

    # Base risk calculation
    risk = 0.15

    # Case A: Brand is in registry
    if has_registry_brand and brand_data:
        brand_name = brand_data.get("name", "")
        legal_names = brand_data.get("legal_names", [])
        aliases = brand_data.get("aliases", [])
        candidate_official_names = [brand_name, *legal_names, *aliases]

        if display_name:
            norm_payee = normalize_entity_name(display_name)
            evidence["normalized_payee"] = norm_payee

            best_score = 0.0
            best_match_name = ""
            for official_name in candidate_official_names:
                norm_official = normalize_entity_name(official_name)
                # Rapidfuzz token_set_ratio handles reordered tokens and subset matches
                score = fuzz.token_set_ratio(norm_payee, norm_official)
                if score > best_score:
                    best_score = score
                    best_match_name = official_name

            evidence["best_fuzzy_score"] = round(best_score, 1)
            evidence["best_match_name"] = best_match_name

            # Fuzzy score >= 80 counts as match
            if best_score >= 80:
                reasons.append("PAYEE_NAME_MATCH")
                risk = 0.05
            else:
                reasons.append("PAYEE_NAME_MISMATCH")
                payee_is_personal = is_personal_name(display_name)
                evidence["is_personal_payee"] = payee_is_personal

                if payee_is_personal:
                    # Known brand + non-matching personal-looking name raises PERSONAL_PAYEE flag
                    flags.append("PERSONAL_PAYEE")
                    reasons.append("PERSONAL_PAYEE")
                    risk = 0.75
                else:
                    # Non-matching corporate or unknown entity
                    risk = 0.60
        else:
            # No display name provided for a registry brand, but UPI is given
            if phone_upi:
                # Registered major brands never ask for payments to personal mobile UPI handles
                risk = 0.45
            else:
                risk = 0.20

    # Case B: Brand is NOT in registry or NO brand claim
    else:
        if display_name:
            payee_is_personal = is_personal_name(display_name)
            evidence["is_personal_payee"] = payee_is_personal
            if phone_upi and payee_is_personal:
                risk = 0.30
            elif phone_upi:
                risk = 0.25
            else:
                risk = 0.15
        else:
            if phone_upi:
                risk = 0.25
            else:
                risk = 0.15

    return {
        "status": "ok",
        "risk": round(risk, 2),
        "reasons": reasons,
        "flags": flags,
        "evidence": evidence,
    }
