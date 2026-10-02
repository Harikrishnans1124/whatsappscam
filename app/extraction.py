"""Extraction and normalization module for TrustShop AI.

Handles:
- Phone number normalization to E.164 and type classification via phonenumbers (Google libphonenumber)
- URL and registrable domain extraction via tldextract
- UPI ID extraction while safely distinguishing UPI handles from email addresses
- Claimed brand detection from user input, aliases, message content, and domain tokens
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

import phonenumbers
import tldextract
from phonenumbers import PhoneNumberType

# Number type mapping from phonenumbers enum
PHONE_TYPE_MAP = {
    PhoneNumberType.FIXED_LINE: "FIXED_LINE",
    PhoneNumberType.MOBILE: "MOBILE",
    PhoneNumberType.FIXED_LINE_OR_MOBILE: "FIXED_LINE_OR_MOBILE",
    PhoneNumberType.TOLL_FREE: "TOLL_FREE",
    PhoneNumberType.PREMIUM_RATE: "PREMIUM_RATE",
    PhoneNumberType.SHARED_COST: "SHARED_COST",
    PhoneNumberType.VOIP: "VOIP",
    PhoneNumberType.PERSONAL_NUMBER: "PERSONAL_NUMBER",
    PhoneNumberType.PAGER: "PAGER",
    PhoneNumberType.UAN: "UAN",
    PhoneNumberType.VOICEMAIL: "VOICEMAIL",
    PhoneNumberType.UNKNOWN: "UNKNOWN",
}

# Common email domains to explicitly reject as UPI handles
COMMON_EMAIL_DOMAINS = {
    "gmail.com",
    "yahoo.com",
    "yahoo.co.in",
    "hotmail.com",
    "outlook.com",
    "icloud.com",
    "rediffmail.com",
    "live.com",
    "mail.com",
    "zoho.com",
    "protonmail.com",
    "yandex.com",
    "aol.com",
}

# Standard TLDs that indicate an email domain rather than a UPI handle
STANDARD_TLD_SUFFIXES = (
    ".com", ".org", ".net", ".edu", ".gov", ".mil", ".io",
    ".co.in", ".co.uk", ".org.in", ".net.in", ".info", ".biz", ".me"
)

# Known popular Indian UPI PSP handles (NPCI ecosystem)
KNOWN_UPI_HANDLES = {
    "okhdfcbank", "oksbi", "okicici", "okaxis", "ybl", "ibl", "axl",
    "paytm", "apl", "upi", "fbl", "barodampay", "federal", "rbl",
    "idfcbank", "aubank", "indus", "kotak", "kmbl", "postbank",
    "equitas", "yesbank", "icici", "sbi", "hdfcbank", "pnb", "cnrb",
    "unionbank", "uco", "boi", "syndicate", "airtel", "amazonpay",
    "jupiteraxis", "sliceaxis", "naviaxis", "superyes", "freecharge"
}

# URL regex for text extraction
URL_REGEX = re.compile(
    r"(?i)\b((?:https?://|www\d{0,3}[.]|[a-z0-9.\-]+[.][a-z]{2,4}/)(?:[^\s()<>]+|\(([^\s()<>]+|(\([^\s()<>]+\)))\))+(?:\(([^\s()<>]+|(\([^\s()<>]+\)))\)|[^\s`!()\[\]{};:'\".,<>?«»“”‘’]))"
)

# Potential UPI / email pattern
VPA_REGEX = re.compile(r"\b([a-zA-Z0-9.\-_]{2,64})@([a-zA-Z0-9.\-_]{2,64})\b")


def normalize_phone(raw: str | None, default_region: str = "IN") -> dict[str, Any]:
    """Normalize a phone number string to E.164, validating and determining number type."""
    if not raw or not isinstance(raw, str) or not raw.strip():
        return {
            "valid": False,
            "e164": None,
            "type": None,
            "raw": raw or "",
        }

    cleaned = raw.strip()
    
    # Handle double zero international prefix e.g. 0091... -> +91...
    if cleaned.startswith("00") and len(cleaned) > 4:
        cleaned = "+" + cleaned[2:]

    try:
        parsed = phonenumbers.parse(cleaned, default_region)
    except phonenumbers.NumberParseException:
        return {
            "valid": False,
            "e164": None,
            "type": None,
            "raw": raw,
        }

    is_valid = phonenumbers.is_valid_number(parsed)
    if not is_valid:
        return {
            "valid": False,
            "e164": None,
            "type": None,
            "raw": raw,
        }

    e164 = phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
    raw_type = phonenumbers.number_type(parsed)
    type_name = PHONE_TYPE_MAP.get(raw_type, "UNKNOWN")

    return {
        "valid": True,
        "e164": e164,
        "type": type_name,
        "raw": raw,
    }


def extract_phones_from_text(text: str | None, default_region: str = "IN") -> list[dict[str, Any]]:
    """Extract valid phone numbers embedded in message text."""
    if not text:
        return []
    
    results = []
    seen_e164 = set()
    for match in phonenumbers.PhoneNumberMatcher(text, default_region):
        num = match.number
        if phonenumbers.is_valid_number(num):
            e164 = phonenumbers.format_number(num, phonenumbers.PhoneNumberFormat.E164)
            if e164 not in seen_e164:
                seen_e164.add(e164)
                raw_type = phonenumbers.number_type(num)
                results.append({
                    "valid": True,
                    "e164": e164,
                    "type": PHONE_TYPE_MAP.get(raw_type, "UNKNOWN"),
                    "raw": match.raw_string,
                })
    return results


def extract_urls(text: str | None, explicit_urls: list[str] | None = None) -> list[dict[str, Any]]:
    """Extract and parse URLs from text and explicit inputs using tldextract."""
    candidates: list[str] = []
    if explicit_urls:
        candidates.extend(explicit_urls)

    if text:
        matches = URL_REGEX.findall(text)
        for m in matches:
            url_str = m[0] if isinstance(m, tuple) else m
            if url_str:
                candidates.append(url_str)

    results = []
    seen_registrable = set()

    for item in candidates:
        if not item or not isinstance(item, str):
            continue
        cleaned = item.strip().rstrip(".,;:!?)")
        if not cleaned:
            continue

        normalized_url = cleaned if cleaned.startswith(("http://", "https://")) else f"https://{cleaned}"
        ext = tldextract.extract(normalized_url)

        if not ext.domain or not ext.suffix:
            continue

        registrable = f"{ext.domain}.{ext.suffix}".lower()
        if registrable not in seen_registrable:
            seen_registrable.add(registrable)
            results.append({
                "original": item,
                "url": normalized_url,
                "registrable_domain": registrable,
                "domain_label": ext.domain.lower(),
                "subdomain": ext.subdomain.lower() if ext.subdomain else "",
                "suffix": ext.suffix.lower(),
            })

    return results


def is_valid_upi_id(candidate: str) -> bool:
    """Determine whether a string is a valid UPI VPA and NOT an email address."""
    if not candidate or "@" not in candidate:
        return False
    parts = candidate.strip().split("@")
    if len(parts) != 2:
        return False

    username, handle = parts[0].lower(), parts[1].lower()
    if not username or not handle:
        return False

    # 1. Reject known email domains
    if handle in COMMON_EMAIL_DOMAINS:
        return False

    # 2. Reject handles ending with email/web domain suffixes (e.g. .com, .org, .co.in)
    # Standard UPI handles in India do not have domain suffixes (e.g. @okhdfcbank, @ybl, @paytm)
    for suffix in STANDARD_TLD_SUFFIXES:
        if handle.endswith(suffix):
            return False

    # 3. Reject if handle contains a dot (most emails have dots; UPI handles typically do not)
    if "." in handle:
        return False

    # 4. Handle should match standard UPI handle pattern
    return bool(re.match(r"^[a-zA-Z0-9_\-]+$", handle))


def extract_upi_ids(text: str | None, explicit_upi: str | None = None) -> list[str]:
    """Extract UPI IDs from text and explicit inputs, filtering out email addresses."""
    found: list[str] = []
    seen = set()

    if explicit_upi and is_valid_upi_id(explicit_upi):
        norm = explicit_upi.strip().lower()
        found.append(norm)
        seen.add(norm)

    if text:
        matches = VPA_REGEX.findall(text)
        for username, handle in matches:
            vpa = f"{username}@{handle}".strip().lower()
            if is_valid_upi_id(vpa) and vpa not in seen:
                found.append(vpa)
                seen.add(vpa)

    return found


def detect_claimed_brand(
    claimed_brand: str | None,
    message_text: str | None,
    extracted_urls: list[dict[str, Any]],
    registry_brands: list[dict[str, Any]],
) -> dict[str, Any] | None:
    """Detect brand identity either from user input or by searching message text and domain tokens."""
    # 1. User explicitly provided claimed_brand
    if claimed_brand and claimed_brand.strip():
        q = claimed_brand.strip().lower()
        for b in registry_brands:
            b_slug = b["slug"].lower()
            b_name = b["name"].lower()
            b_aliases = [a.lower() for a in b.get("aliases", [])]

            if q == b_slug or q == b_name or q in b_aliases:
                return {
                    "claimed": claimed_brand.strip(),
                    "slug": b["slug"],
                    "name": b["name"],
                    "in_registry": True,
                    "brand_data": b,
                    "detection_method": "user_input_exact",
                }

        # Substring / partial match on user input
        for b in registry_brands:
            b_name = b["name"].lower()
            if q in b_name or b_name in q:
                return {
                    "claimed": claimed_brand.strip(),
                    "slug": b["slug"],
                    "name": b["name"],
                    "in_registry": True,
                    "brand_data": b,
                    "detection_method": "user_input_partial",
                }

        # Brand claimed by user but not in registry
        return {
            "claimed": claimed_brand.strip(),
            "slug": None,
            "name": claimed_brand.strip(),
            "in_registry": False,
            "brand_data": None,
            "detection_method": "user_input_unregistered",
        }

    # 2. No user input: scan message text for brand names or aliases
    if message_text:
        text_lower = message_text.lower()
        for b in registry_brands:
            # Check brand name
            pattern_name = r"\b" + re.escape(b["name"].lower()) + r"\b"
            if re.search(pattern_name, text_lower):
                return {
                    "claimed": b["name"],
                    "slug": b["slug"],
                    "name": b["name"],
                    "in_registry": True,
                    "brand_data": b,
                    "detection_method": "message_text_name",
                }
            # Check aliases
            for alias in b.get("aliases", []):
                pattern_alias = r"\b" + re.escape(alias.lower()) + r"\b"
                if re.search(pattern_alias, text_lower):
                    return {
                        "claimed": b["name"],
                        "slug": b["slug"],
                        "name": b["name"],
                        "in_registry": True,
                        "brand_data": b,
                        "detection_method": "message_text_alias",
                    }

    # 3. Check extracted domain labels for brand name tokens
    for u in extracted_urls:
        label = u.get("domain_label", "").lower()
        for b in registry_brands:
            b_slug = b["slug"].lower()
            # If domain contains slug without dashes e.g. acmefootwear in acmefootwear-outlet
            clean_slug = b_slug.replace("-", "")
            if clean_slug in label.replace("-", ""):
                return {
                    "claimed": b["name"],
                    "slug": b["slug"],
                    "name": b["name"],
                    "in_registry": True,
                    "brand_data": b,
                    "detection_method": "domain_token_match",
                }

    return None


@dataclass
class CheckContext:
    """Normalized context passed to all verification scorers."""

    phone: dict[str, Any]
    extracted_phones: list[dict[str, Any]]
    urls: list[dict[str, Any]]
    upi_ids: list[str]
    payment: dict[str, Any]
    brand: dict[str, Any] | None
    message_text: str | None = None
    language: str = "en"


def extract_check_context(
    phone_number: str | None = None,
    message_text: str | None = None,
    urls: list[str] | None = None,
    claimed_brand: str | None = None,
    payment: dict[str, Any] | None = None,
    language: str = "en",
    registry_brands: list[dict[str, Any]] | None = None,
) -> CheckContext:
    """Build a unified CheckContext from user inputs."""
    # Normalize primary phone
    norm_phone = normalize_phone(phone_number)

    # Extract any secondary phone numbers in message text
    extracted_phones = extract_phones_from_text(message_text)

    # Extract and parse URLs
    parsed_urls = extract_urls(message_text, urls or [])

    # Extract UPI IDs
    payment_dict = payment or {}
    explicit_upi = payment_dict.get("upi_id")
    upi_ids = extract_upi_ids(message_text, explicit_upi)

    # Detect claimed brand
    detected_brand = detect_claimed_brand(
        claimed_brand=claimed_brand,
        message_text=message_text,
        extracted_urls=parsed_urls,
        registry_brands=registry_brands or [],
    )

    return CheckContext(
        phone=norm_phone,
        extracted_phones=extracted_phones,
        urls=parsed_urls,
        upi_ids=upi_ids,
        payment=payment_dict,
        brand=detected_brand,
        message_text=message_text,
        language=language,
    )
