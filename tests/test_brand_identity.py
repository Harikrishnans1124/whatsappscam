"""Unit tests for app.agents.brand_identity module."""

import datetime as dt

import pytest

from app.agents.brand_identity import evaluate_brand_identity
from app.extraction import extract_check_context


@pytest.fixture
def mock_registry_brands():
    return [
        {
            "slug": "flipkart",
            "name": "Flipkart",
            "aliases": ["Flipkart Internet"],
            "official_domains": ["flipkart.com"],
            "official_phones": ["+9118002029898", "+9104445614700"],
            "payment_policy": "Pay strictly on app/web.",
            "sources": [{"url": "https://flipkart.com/help", "verified_on": "2026-10-01"}],
        },
        {
            "slug": "amazon-india",
            "name": "Amazon India",
            "aliases": ["Amazon", "Amazon.in"],
            "official_domains": ["amazon.in", "amazon.com"],
            "official_phones": [],  # Amazon India publishes no WhatsApp/sales phone numbers
            "payment_policy": "Pay only on website checkout.",
            "sources": [{"url": "https://amazon.in/help", "verified_on": "2026-10-01"}],
        },
        {
            "slug": "stale-brand",
            "name": "Stale Brand",
            "aliases": [],
            "official_domains": ["stalebrand.com"],
            "official_phones": ["+911800999999"],
            "payment_policy": "Pay on site.",
            "sources": [{"url": "https://stalebrand.com", "verified_on": "2025-01-01"}],
        },
    ]


class TestBrandIdentityScorer:
    def test_official_match_phone_and_domain(self, mock_registry_brands):
        ctx = extract_check_context(
            phone_number="+91 1800 202 9898",
            urls=["https://flipkart.com/deal"],
            claimed_brand="Flipkart",
            registry_brands=mock_registry_brands,
        )
        res = evaluate_brand_identity(ctx, reference_date=dt.date(2026, 10, 2))

        assert res["status"] == "ok"
        assert res["risk"] == 0.0
        assert "BRAND_CHANNEL_MATCH" in res["reasons"]
        assert len(res["flags"]) == 0
        assert res["evidence"]["outcome"] == "MATCH"
        assert res["evidence"]["phone_matched"] is True
        assert res["evidence"]["domain_matched"] is True

    def test_impersonation_mismatch_phone(self, mock_registry_brands):
        ctx = extract_check_context(
            phone_number="+91 98765 43210",  # Fake mobile pretending to be Flipkart
            claimed_brand="Flipkart",
            registry_brands=mock_registry_brands,
        )
        res = evaluate_brand_identity(ctx, reference_date=dt.date(2026, 10, 2))

        assert res["status"] == "ok"
        assert res["risk"] == 0.85
        assert "BRAND_CHANNEL_MISMATCH" in res["reasons"]
        assert "BRAND_CHANNEL_MISMATCH" in res["flags"]
        assert res["evidence"]["outcome"] == "MISMATCH"
        assert "+919876543210" in res["evidence"]["mismatched_phones"]

    def test_impersonation_brand_with_no_published_phones(self, mock_registry_brands):
        # Amazon India has official_phones: []
        # Any WhatsApp number claiming to be Amazon is a mismatch
        ctx = extract_check_context(
            phone_number="+91 98765 43210",
            claimed_brand="Amazon India",
            registry_brands=mock_registry_brands,
        )
        res = evaluate_brand_identity(ctx, reference_date=dt.date(2026, 10, 2))

        assert res["status"] == "ok"
        assert res["risk"] == 0.85
        assert "BRAND_CHANNEL_MISMATCH" in res["flags"]
        assert res["evidence"]["outcome"] == "MISMATCH"

    def test_impersonation_mismatch_domain(self, mock_registry_brands):
        ctx = extract_check_context(
            urls=["https://flipkart-discount-deals.net/offer"],
            claimed_brand="Flipkart",
            registry_brands=mock_registry_brands,
        )
        res = evaluate_brand_identity(ctx, reference_date=dt.date(2026, 10, 2))

        assert res["status"] == "ok"
        assert res["risk"] == 0.85
        assert "BRAND_CHANNEL_MISMATCH" in res["reasons"]
        assert "BRAND_CHANNEL_MISMATCH" in res["flags"]
        assert "flipkart-discount-deals.net" in res["evidence"]["mismatched_domains"]

    def test_unknown_brand(self, mock_registry_brands):
        ctx = extract_check_context(
            phone_number="+91 98765 43210",
            claimed_brand="SuperUnknownStore123",
            registry_brands=mock_registry_brands,
        )
        res = evaluate_brand_identity(ctx, reference_date=dt.date(2026, 10, 2))

        assert res["status"] == "ok"
        assert res["risk"] == 0.20  # Neutral risk
        assert "BRAND_NOT_IN_REGISTRY" in res["reasons"]
        assert len(res["flags"]) == 0
        assert res["evidence"]["outcome"] == "UNKNOWN_BRAND"

    def test_no_brand_claim(self, mock_registry_brands):
        ctx = extract_check_context(
            phone_number="+91 98765 43210",
            message_text="Just selling normal shoes, no brand mentioned.",
            registry_brands=mock_registry_brands,
        )
        res = evaluate_brand_identity(ctx)

        assert res["status"] == "not_applicable"
        assert res["risk"] is None
        assert res["reasons"] == []
        assert res["flags"] == []
        assert res["evidence"]["outcome"] == "NO_BRAND_CLAIM"

    def test_stale_registry_entry_flagged(self, mock_registry_brands):
        ctx = extract_check_context(
            phone_number="+91 1800 999 999",
            claimed_brand="Stale Brand",
            registry_brands=mock_registry_brands,
        )
        # 2026-10-02 vs 2025-01-01 is > 600 days old
        res = evaluate_brand_identity(ctx, reference_date=dt.date(2026, 10, 2))

        assert "REGISTRY_STALE" in res["reasons"]
        assert res["evidence"]["is_stale"] is True

    def test_scorer_shape_contract(self, mock_registry_brands):
        ctx = extract_check_context(
            phone_number="+91 1800 202 9898",
            claimed_brand="Flipkart",
            registry_brands=mock_registry_brands,
        )
        res = evaluate_brand_identity(ctx)

        # Standard scorer dictionary contract:
        assert isinstance(res, dict)
        assert set(res.keys()) == {"status", "risk", "reasons", "flags", "evidence"}
        assert res["status"] in {"ok", "not_applicable", "failed"}
        assert isinstance(res["reasons"], list)
        assert isinstance(res["flags"], list)
        assert isinstance(res["evidence"], dict)
