"""Explanation and advice generator for TrustShop AI."""

from __future__ import annotations

from typing import Any

from app.extraction import CheckContext
from app.schemas import ReasonItem

REASON_TEMPLATES = {
    "BRAND_CHANNEL_MATCH": "This contact channel matches the brand's verified official registry records.",
    "BRAND_CHANNEL_MISMATCH": "This contact number or website is not on the brand's official published list.",
    "BRAND_NOT_IN_REGISTRY": "This brand is not covered in our official registry. Cannot verify against official channels.",
    "REGISTRY_STALE": "The registry information for this brand is older than 90 days and pending re-verification.",
    "PERSONAL_PAYEE": "The payment payee appears to be an individual's personal account rather than the official company.",
    "PAYEE_NAME_MISMATCH": "The payee name does not match the company's registered legal entity.",
    "PAYEE_NAME_MATCH": "The payment payee matches the brand's verified legal company name.",
    "PHONE_STYLE_UPI": "The UPI ID uses a personal mobile number format rather than an official merchant ID.",
    "OFFICIAL_DOMAIN_MATCH": "The website domain matches the brand's official verified domain.",
    "LOOKALIKE_DOMAIN": "The website name closely imitates an official brand domain but is registered under an unauthorized name.",
    "NEW_DOMAIN": "The website domain was registered very recently.",
    "URL_SHORTENER": "A URL shortener was used to conceal the final destination link.",
    "OTP_REQUEST": "The message requests a one-time password (OTP). Legitimate brands will never ask for your OTP.",
    "REMOTE_ACCESS_REQUEST": "The message asks you to install remote-access software (e.g. AnyDesk, TeamViewer).",
    "URGENCY_PRESSURE": "The seller uses high-pressure urgency tactics ('today only', 'last items').",
    "ADVANCE_PAYMENT_REQUEST": "The seller demands advance payment outside official checkout channels.",
    "SUSPICIOUS_OFFER": "The message advertises unrealistic discounts or unverified lottery/prize claims.",
    "OFF_PLATFORM_MOVE": "The seller requests moving conversation to personal numbers or unmonitored channels.",
    "INVALID_PHONE_NUMBER": "The phone number format is invalid according to international numbering standards.",
    "REPORTED_BY_USERS": "This contact has been reported by multiple independent users as suspicious.",
    "RDAP_LOOKUP_FAILED": "Domain registration records could not be retrieved from RDAP servers.",
    "SCORER_UNAVAILABLE": "A verification service is temporarily unavailable due to upstream issues.",
    "SCORER_TIMEOUT": "A verification service timed out before completing.",
    "SCORER_FAILED": "An unexpected error occurred during verification.",
    "DEGRADED_MODE": "One or more external verification checks were unavailable. Proceed with caution.",
}


def get_reason_explanation(code: str) -> str:
    return REASON_TEMPLATES.get(code, f"Check triggered code {code}.")


def generate_explanation(
    context: CheckContext,
    verdict: str,
    reason_codes: list[str],
) -> dict[str, Any]:
    brand_name = "the claimed brand"
    if context.brand and context.brand.get("name"):
        brand_name = context.brand["name"]

    # Build reasons list
    reasons_list: list[ReasonItem] = []
    for code in reason_codes:
        reasons_list.append(ReasonItem(code=code, text=get_reason_explanation(code)))

    # Summary
    if verdict == "MATCHES_OFFICIAL":
        summary = f"This contact matches the official published channels for {brand_name}."
    elif verdict == "LIKELY_SCAM":
        summary = f"Warning: Strong indicators of impersonation. This does not look like {brand_name}."
    elif verdict == "SUSPICIOUS":
        summary = f"Caution: Red flags detected. This contact does not match {brand_name}'s official records."
    else:  # UNVERIFIED
        summary = "Cannot verify this seller against official brand channels."

    # Advice
    advice: list[str] = []
    if verdict == "LIKELY_SCAM":
        advice.append("Do not send any money, scan QR codes, or share card/UPI details.")
        advice.append(f"Open {brand_name}'s official website or app yourself and order there.")
        advice.append(
            "If you have already sent money, immediately call 1930 (national cybercrime helpline) and report at https://cybercrime.gov.in."
        )
    elif verdict == "SUSPICIOUS":
        advice.append("Do not make advance payments on this number, link, or payment ID.")
        advice.append(f"Contact {brand_name} directly through their official app or website to confirm.")
    elif verdict == "MATCHES_OFFICIAL":
        advice.append("The contact channel matches verified official records.")
        advice.append(
            f"Still confirm your cart and checkout directly inside {brand_name}'s official app before completing payment."
        )
    else:  # UNVERIFIED
        advice.append("Do not treat this seller as verified or safe.")
        advice.append(
            "Always purchase through the brand's official store, verified website, or approved app."
        )

    return {
        "summary": summary,
        "reasons": reasons_list,
        "advice": advice,
    }
