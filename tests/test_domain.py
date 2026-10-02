"""Tests for Phase 3b: Domain Scorer."""

import datetime as dt

import httpx
import pytest
import respx

from app.agents.domain import (
    check_lookalike,
    check_punycode_or_homoglyphs,
    domain_scorer,
    normalize_substitutions,
)
from app.extraction import CheckContext, normalize_phone


@pytest.fixture
def amazon_context():
    return CheckContext(
        phone=normalize_phone(None),
        extracted_phones=[],
        urls=[],
        upi_ids=[],
        payment={},
        brand={
            "claimed": "Amazon India",
            "slug": "amazon-india",
            "name": "Amazon India",
            "in_registry": True,
            "brand_data": {
                "name": "Amazon India",
                "official_domains": ["amazon.in", "amazon.com"],
                "aliases": ["Amazon", "Amazon Pay"],
            },
        },
    )


def test_normalize_substitutions():
    assert normalize_substitutions("amaz0n") == "amazon"
    assert normalize_substitutions("fl1pkart") == "flipkart"
    assert normalize_substitutions("pay-tm") == "paytm"


def test_check_punycode_or_homoglyphs():
    # Regular Latin domain
    hit, _ = check_punycode_or_homoglyphs("amazon.in")
    assert hit is False

    # Punycode domain
    hit, desc = check_punycode_or_homoglyphs("xn--flipkrt-2ya.com")
    assert hit is True
    assert "Punycode" in desc

    # Cyrillic small 'a' (\u0430) instead of ASCII 'a'
    homoglyph_domain = "аmazon.in"
    hit, desc = check_punycode_or_homoglyphs(homoglyph_domain)
    assert hit is True
    assert "Homoglyph" in desc


def test_check_lookalike():
    official_domains = ["amazon.in", "flipkart.com", "myntra.com"]
    brand_names = ["Amazon India", "Flipkart", "Myntra"]

    # 1. Typo lookalike
    hit, desc = check_lookalike("flipkrt", official_domains, brand_names)
    assert hit is True
    assert "Typo" in desc

    # 2. Digit trick
    hit, desc = check_lookalike("amaz0n", official_domains, brand_names)
    assert hit is True

    # 3. Brand stuffing
    hit, desc = check_lookalike("flipkart-offers-deal", official_domains, brand_names)
    assert hit is True
    assert "Brand-stuffing" in desc or "Brand name" in desc

    # 4. Legitimate official label should not be lookalike of itself
    hit, _ = check_lookalike("amazon", official_domains, brand_names)
    assert hit is False


@pytest.mark.asyncio
async def test_domain_not_applicable(amazon_context):
    res = await domain_scorer(amazon_context)
    assert res["status"] == "not_applicable"
    assert res["risk"] is None
    assert len(res["reasons"]) == 0


@pytest.mark.asyncio
async def test_domain_exact_official_match(amazon_context):
    amazon_context.urls = [{
        "original": "https://www.amazon.in/dp/B08N5WRWNW",
        "url": "https://www.amazon.in/dp/B08N5WRWNW",
        "registrable_domain": "amazon.in",
        "domain_label": "amazon",
        "subdomain": "www",
        "suffix": "in",
    }]
    res = await domain_scorer(amazon_context)
    assert res["status"] == "ok"
    assert res["risk"] == 0.0
    assert "OFFICIAL_DOMAIN_MATCH" in res["reasons"]
    assert "LOOKALIKE_DOMAIN" not in res["flags"]


@pytest.mark.asyncio
async def test_domain_typo_lookalike(amazon_context):
    amazon_context.urls = [{
        "original": "https://amaz0n.in/deal",
        "url": "https://amaz0n.in/deal",
        "registrable_domain": "amaz0n.in",
        "domain_label": "amaz0n",
        "subdomain": "",
        "suffix": "in",
    }]
    res = await domain_scorer(amazon_context)
    assert res["status"] == "ok"
    assert res["risk"] >= 0.85
    assert "LOOKALIKE_DOMAIN" in res["flags"]
    assert "LOOKALIKE_DOMAIN" in res["reasons"]


@pytest.mark.asyncio
async def test_domain_brand_stuffing(amazon_context):
    amazon_context.urls = [{
        "original": "https://amazon-outlet-sale.shop/shoes",
        "url": "https://amazon-outlet-sale.shop/shoes",
        "registrable_domain": "amazon-outlet-sale.shop",
        "domain_label": "amazon-outlet-sale",
        "subdomain": "",
        "suffix": "shop",
    }]
    res = await domain_scorer(amazon_context)
    assert res["status"] == "ok"
    assert "LOOKALIKE_DOMAIN" in res["flags"]
    assert res["risk"] >= 0.85


@pytest.mark.asyncio
async def test_domain_url_shortener(amazon_context):
    amazon_context.urls = [{
        "original": "https://bit.ly/3xSpecialOffer",
        "url": "https://bit.ly/3xSpecialOffer",
        "registrable_domain": "bit.ly",
        "domain_label": "bit",
        "subdomain": "",
        "suffix": "ly",
    }]
    res = await domain_scorer(amazon_context)
    assert res["status"] == "ok"
    assert "URL_SHORTENER" in res["reasons"]
    assert res["risk"] >= 0.50


@pytest.mark.asyncio
@respx.mock
async def test_domain_rdap_young_domain(amazon_context):
    target_domain = "random-store-deals-xyz.com"
    respx.get(f"https://rdap.org/domain/{target_domain}").mock(
        return_value=httpx.Response(
            200,
            json={
                "events": [
                    {"eventAction": "registration", "eventDate": "2026-09-25T00:00:00Z"},
                    {"eventAction": "expiration", "eventDate": "2027-09-25T00:00:00Z"},
                ]
            },
        )
    )

    amazon_context.urls = [{
        "original": f"https://{target_domain}",
        "url": f"https://{target_domain}",
        "registrable_domain": target_domain,
        "domain_label": "random-store-deals-xyz",
        "subdomain": "",
        "suffix": "com",
    }]

    async with httpx.AsyncClient() as client:
        res = await domain_scorer(
            amazon_context,
            http_client=client,
            reference_date=dt.date(2026, 10, 2),
        )

    assert res["status"] == "ok"
    assert "NEW_DOMAIN" in res["reasons"]
    assert res["risk"] >= 0.65
    assert res["evidence"][f"{target_domain}_age_days"] == 7


@pytest.mark.asyncio
@respx.mock
async def test_domain_rdap_established_domain(amazon_context):
    target_domain = "trusted-partner-store.com"
    respx.get(f"https://rdap.org/domain/{target_domain}").mock(
        return_value=httpx.Response(
            200,
            json={
                "events": [
                    {"eventAction": "registration", "eventDate": "2020-01-01T00:00:00Z"}
                ]
            },
        )
    )

    amazon_context.urls = [{
        "original": f"https://{target_domain}",
        "url": f"https://{target_domain}",
        "registrable_domain": target_domain,
        "domain_label": "trusted-partner-store",
        "subdomain": "",
        "suffix": "com",
    }]

    async with httpx.AsyncClient() as client:
        res = await domain_scorer(
            amazon_context,
            http_client=client,
            reference_date=dt.date(2026, 10, 2),
        )

    assert res["status"] == "ok"
    assert "NEW_DOMAIN" not in res["reasons"]
    assert res["risk"] <= 0.20


@pytest.mark.asyncio
@respx.mock
async def test_domain_rdap_failure_degraded(amazon_context):
    target_domain = "unreachable-domain-service.org"
    respx.get(f"https://rdap.org/domain/{target_domain}").mock(
        return_value=httpx.Response(500)
    )

    amazon_context.urls = [{
        "original": f"https://{target_domain}",
        "url": f"https://{target_domain}",
        "registrable_domain": target_domain,
        "domain_label": "unreachable-domain-service",
        "subdomain": "",
        "suffix": "org",
    }]

    async with httpx.AsyncClient() as client:
        res = await domain_scorer(amazon_context, http_client=client)

    assert res["status"] == "failed"
    assert res["risk"] is None
    assert "RDAP_LOOKUP_FAILED" in res["reasons"]
