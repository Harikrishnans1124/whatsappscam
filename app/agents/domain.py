"""Domain Scorer for TrustShop AI.

Evaluates domain names and URLs extracted from user messages and inputs against:
- Official registry brand domains (exact match).
- Lookalike / typosquatting detection:
  - Levenshtein / Damerau typo distance
  - Brand-stuffing with e-commerce keywords (e.g. nike-outlet, flipkart-offers)
  - Hyphen and digit substitution tricks (amaz0n, flip-kart)
  - Punycode (IDN) and mixed-script homoglyphs
- Known URL shortener detection (e.g. bit.ly, tinyurl.com)
- RDAP (Registration Data Access Protocol) domain registration date & age in days
"""

from __future__ import annotations

import datetime as dt
import re
from typing import Any

import httpx
from rapidfuzz.distance import Levenshtein

from app.extraction import CheckContext

# Popular URL shortener domains known for concealing destination links
SHORTENER_DOMAINS = {
    "bit.ly",
    "tinyurl.com",
    "t.co",
    "is.gd",
    "buff.ly",
    "ow.ly",
    "cutt.ly",
    "rb.gy",
    "shorturl.at",
    "tiny.cc",
    "goo.gl",
    "qr.ae",
    "shorte.st",
    "v.gd",
}

# Common scam / promo keywords often stuffed into brand lookalike domains
BRAND_STUFFING_KEYWORDS = {
    "outlet",
    "sale",
    "deals",
    "deal",
    "store",
    "shop",
    "offers",
    "offer",
    "discount",
    "official",
    "support",
    "login",
    "verify",
    "rewards",
    "reward",
    "bonus",
    "claim",
    "cashback",
    "pay",
    "customer-care",
    "care",
}

# Homoglyph character substitutions (e.g., Cyrillic / Greek characters visually identical to Latin)
HOMOGLYPH_MAP = {
    "\u0430": "a",  # Cyrillic small letter a
    "\u0441": "c",  # Cyrillic small letter es
    "\u0435": "e",  # Cyrillic small letter ie
    "\u043e": "o",  # Cyrillic small letter o
    "\u0440": "p",  # Cyrillic small letter er
    "\u0455": "s",  # Cyrillic small letter dze
    "\u0456": "i",  # Cyrillic small letter byelorussian-ukrainian i
    "\u0458": "j",  # Cyrillic small letter je
    "\u0443": "y",  # Cyrillic small letter u
    "\u0445": "x",  # Cyrillic small letter ha
    "\u03bf": "o",  # Greek small letter omicron
    "\u03bd": "v",  # Greek small letter nu
}


def normalize_substitutions(text: str) -> str:
    """Normalize digit/char tricks like 0 -> o, 1 -> i, 3 -> e, 5 -> s, @ -> a, etc."""
    sub_map = {
        "0": "o",
        "1": "i",
        "3": "e",
        "4": "a",
        "5": "s",
        "@": "a",
        "$": "s",
        "-": "",
        "_": "",
    }
    res = []
    for ch in text.lower():
        res.append(sub_map.get(ch, ch))
    return "".join(res)


def check_punycode_or_homoglyphs(domain: str) -> tuple[bool, str]:
    """Check if domain uses Punycode (xn--) or contains homoglyphs mimicking Latin letters."""
    if "xn--" in domain.lower():
        try:
            decoded = domain.encode("ascii").decode("idna")
            return True, f"Punycode encoded internationalized domain ({decoded})"
        except (UnicodeError, ValueError):
            return True, "Malformed Punycode internationalized domain"

    for ch in domain:
        if ch in HOMOGLYPH_MAP:
            return True, f"Homoglyph character detected: '{ch}' mimicking Latin '{HOMOGLYPH_MAP[ch]}'"

    return False, ""


def check_lookalike(
    candidate_label: str,
    official_domains: list[str],
    brand_names: list[str],
) -> tuple[bool, str]:
    """Check if candidate domain label is a lookalike of official brand domains or brand names."""
    cand = candidate_label.lower()
    norm_cand = normalize_substitutions(cand)

    for off_domain in official_domains:
        off_label = off_domain.split(".")[0].lower()
        norm_off = normalize_substitutions(off_label)

        # 1. Exact match with official domain label is NOT a lookalike
        if cand == off_label:
            continue

        # 2. Levenshtein edit distance check (1 or 2 typos)
        if len(off_label) >= 4:
            dist = Levenshtein.distance(cand, off_label)
            if 1 <= dist <= 2:
                return True, f"Typo lookalike: '{cand}' is within distance {dist} of official '{off_label}'"

        # 3. Digit / hyphen substitution check (e.g. 'amaz0n' -> 'amazon', 'flip-kart' -> 'flipkart')
        if norm_cand == norm_off and cand != off_label:
            return True, f"Substitution trick: '{cand}' normalizes to official '{off_label}'"

        # 4. Brand stuffing: official brand label embedded with words or hyphens (e.g. 'nike-outlet-shop')
        if off_label in cand:
            rem = cand.replace(off_label, "").strip("-")
            for kw in BRAND_STUFFING_KEYWORDS:
                if kw in rem:
                    return True, f"Brand-stuffing: official brand token '{off_label}' combined with '{kw}' in '{cand}'"
            if len(rem) > 0 and ("-" in cand or len(rem) >= 3):
                return True, f"Brand name embedded in suspicious domain: '{cand}' contains '{off_label}'"

    # Also check against brand names / slugs
    for b_name in brand_names:
        clean_name = re.sub(r"[^\w]", "", b_name.lower())
        if len(clean_name) >= 4 and clean_name in cand and cand != clean_name:
            for kw in BRAND_STUFFING_KEYWORDS:
                if kw in cand:
                    return True, f"Brand name '{b_name}' stuffed with keyword '{kw}' in '{cand}'"

    return False, ""


async def fetch_rdap_registration_date(
    domain: str,
    client: httpx.AsyncClient | None = None,
    timeout_s: float = 2.5,
) -> dt.datetime | None:
    """Fetch domain registration date via RDAP protocol using an async HTTP request."""
    url = f"https://rdap.org/domain/{domain}"
    should_close = False
    if client is None:
        client = httpx.AsyncClient(timeout=timeout_s, follow_redirects=True)
        should_close = True

    try:
        response = await client.get(url, headers={"Accept": "application/rdap+json, application/json"})
        if response.status_code != 200:
            return None

        data = response.json()
        events = data.get("events", [])
        for ev in events:
            action = ev.get("eventAction", "").lower()
            if action in ("registration", "registered", "created"):
                date_str = ev.get("eventDate")
                if date_str:
                    # Clean ISO format
                    clean_date = date_str.replace("Z", "+00:00")
                    return dt.datetime.fromisoformat(clean_date)
        return None
    except (httpx.HTTPError, ValueError):
        return None
    finally:
        if should_close:
            await client.aclose()


async def domain_scorer(
    context: CheckContext,
    http_client: httpx.AsyncClient | None = None,
    reference_date: dt.date | None = None,
) -> dict[str, Any]:
    """Score extracted domains against brand records, lookalike patterns, shorteners, and RDAP age."""
    if not context.urls:
        return {
            "status": "not_applicable",
            "risk": None,
            "reasons": [],
            "flags": [],
            "evidence": {"details": "No URLs or domains provided."},
        }

    reasons: list[str] = []
    flags: list[str] = []
    evidence: dict[str, Any] = {
        "domains": [u.get("registrable_domain") for u in context.urls],
        "lookalike_hits": [],
    }

    brand_info = context.brand
    has_registry_brand = bool(brand_info and brand_info.get("in_registry") and brand_info.get("brand_data"))
    brand_data = brand_info.get("brand_data") if has_registry_brand else None

    official_domains: list[str] = []
    brand_names: list[str] = []
    if brand_data:
        official_domains = [d.lower() for d in brand_data.get("official_domains", [])]
        brand_names = [brand_data.get("name", ""), *(brand_data.get("aliases") or [])]
    elif brand_info and brand_info.get("claimed"):
        brand_names = [brand_info["claimed"]]

    highest_risk = 0.10
    has_official_match = False
    has_lookalike = False
    has_shortener = False
    has_new_domain = False
    rdap_failed = False

    ref_dt = reference_date or dt.datetime.now(dt.timezone.utc).date()

    for item in context.urls:
        registrable = item.get("registrable_domain", "").lower()
        domain_label = item.get("domain_label", "").lower()

        # 1. Exact official domain match
        if registrable in official_domains:
            has_official_match = True
            if "OFFICIAL_DOMAIN_MATCH" not in reasons:
                reasons.append("OFFICIAL_DOMAIN_MATCH")
            evidence[f"{registrable}_match"] = "official"
            continue

        # 2. URL Shortener detection
        if registrable in SHORTENER_DOMAINS:
            has_shortener = True
            if "URL_SHORTENER" not in reasons:
                reasons.append("URL_SHORTENER")
            evidence[f"{registrable}_shortener"] = True
            highest_risk = max(highest_risk, 0.50)

        # 3. Punycode and Homoglyphs
        punycode_hit, punycode_desc = check_punycode_or_homoglyphs(registrable)
        if punycode_hit:
            has_lookalike = True
            evidence["lookalike_hits"].append({
                "domain": registrable,
                "type": "punycode_or_homoglyph",
                "details": punycode_desc,
            })

        # 4. Typo and brand-stuffing lookalike checks
        if official_domains or brand_names:
            is_lookalike, lookalike_desc = check_lookalike(domain_label, official_domains, brand_names)
            if is_lookalike:
                has_lookalike = True
                evidence["lookalike_hits"].append({
                    "domain": registrable,
                    "type": "lookalike",
                    "details": lookalike_desc,
                })

        # 5. RDAP Domain Registration Date & Age
        # Don't check RDAP for known shorteners
        if registrable not in SHORTENER_DOMAINS:
            reg_date = await fetch_rdap_registration_date(registrable, client=http_client)
            if reg_date is not None:
                # Compare naive dates
                reg_d = reg_date.date() if isinstance(reg_date, dt.datetime) else reg_date
                age_days = (ref_dt - reg_d).days
                evidence[f"{registrable}_age_days"] = age_days
                evidence[f"{registrable}_registered_on"] = reg_d.isoformat()

                if age_days < 30:
                    has_new_domain = True
                    if "NEW_DOMAIN" not in reasons:
                        reasons.append("NEW_DOMAIN")
                    highest_risk = max(highest_risk, 0.65)
                elif age_days < 180:
                    highest_risk = max(highest_risk, 0.35)
            else:
                evidence[f"{registrable}_rdap"] = "unresolved_or_unavailable"
                rdap_failed = True

    # Lookalike handling
    if has_lookalike:
        flags.append("LOOKALIKE_DOMAIN")
        reasons.append("LOOKALIKE_DOMAIN")
        highest_risk = max(highest_risk, 0.90)

    # Official domain match handling
    if has_official_match and not has_lookalike and not has_new_domain and not has_shortener:
        highest_risk = 0.0

    # If domain lookup completely failed and no decisive lookalike was identified, mark failed for resilience
    if rdap_failed and not has_lookalike and not has_official_match and not has_shortener:
        return {
            "status": "failed",
            "risk": None,
            "reasons": ["RDAP_LOOKUP_FAILED"],
            "flags": [],
            "evidence": evidence,
        }

    return {
        "status": "ok",
        "risk": round(highest_risk, 2),
        "reasons": reasons,
        "flags": flags,
        "evidence": evidence,
    }
