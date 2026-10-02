"""Unit tests for app.decision module."""

import pytest

from app.decision import calculate_decision
from app.extraction import CheckContext


@pytest.fixture
def dummy_context():
    return CheckContext(
        phone={"valid": True, "e164": "+9118002029898"},
        extracted_phones=[],
        urls=[{"registrable_domain": "flipkart.com"}],
        upi_ids=[],
        payment={},
        brand={"claimed": "Flipkart", "name": "Flipkart", "in_registry": True},
    )


class TestDecisionLayer:
    def test_official_match_yields_matches_official(self, dummy_context):
        scores = {
            "brand_identity": {
                "status": "ok",
                "risk": 0.0,
                "reasons": ["BRAND_CHANNEL_MATCH"],
                "flags": [],
                "evidence": {"outcome": "MATCH", "is_stale": False},
            },
            "payment": {"status": "not_applicable", "risk": None, "reasons": [], "flags": []},
            "message": {"status": "not_applicable", "risk": None, "reasons": [], "flags": []},
            "domain": {"status": "not_applicable", "risk": None, "reasons": [], "flags": []},
            "number": {"status": "not_applicable", "risk": None, "reasons": [], "flags": []},
        }

        dec = calculate_decision(dummy_context, scores)
        assert dec.verdict == "MATCHES_OFFICIAL"
        assert dec.risk_score == 0.0
        assert "BRAND_CHANNEL_MATCH" in dec.reason_codes
        assert dec.degraded is False

    def test_floor_brand_channel_mismatch(self, dummy_context):
        # Mismatch with fake phone raises flag BRAND_CHANNEL_MISMATCH
        scores = {
            "brand_identity": {
                "status": "ok",
                "risk": 0.85,
                "reasons": ["BRAND_CHANNEL_MISMATCH"],
                "flags": ["BRAND_CHANNEL_MISMATCH"],
                "evidence": {"outcome": "MISMATCH", "is_stale": False},
            },
            "payment": {"status": "not_applicable", "risk": None, "reasons": [], "flags": []},
            "message": {"status": "not_applicable", "risk": None, "reasons": [], "flags": []},
            "domain": {"status": "not_applicable", "risk": None, "reasons": [], "flags": []},
            "number": {"status": "not_applicable", "risk": None, "reasons": [], "flags": []},
        }

        dec = calculate_decision(dummy_context, scores)
        assert dec.verdict == "LIKELY_SCAM"
        assert dec.risk_score >= 0.65
        assert "BRAND_CHANNEL_MISMATCH" in dec.reason_codes

    def test_hard_flag_floors_enforced(self, dummy_context):
        # Even if weighted risk is low, hard flags enforce floor
        scores = {
            "brand_identity": {
                "status": "ok",
                "risk": 0.1,
                "reasons": [],
                "flags": [],
                "evidence": {"outcome": "MATCH", "is_stale": False},
            },
            "message": {
                "status": "ok",
                "risk": 0.1,
                "reasons": ["OTP_REQUEST"],
                "flags": ["OTP_REQUEST"],  # floor is 0.85
                "evidence": {},
            },
        }

        dec = calculate_decision(dummy_context, scores)
        assert dec.risk_score == 0.85
        assert dec.verdict == "LIKELY_SCAM"
        assert dec.highest_floor_applied == "OTP_REQUEST"

    def test_degraded_mode_never_matches_official(self, dummy_context):
        # Brand matches, but an applicable check failed (degraded)
        scores = {
            "brand_identity": {
                "status": "ok",
                "risk": 0.0,
                "reasons": ["BRAND_CHANNEL_MATCH"],
                "flags": [],
                "evidence": {"outcome": "MATCH", "is_stale": False},
            },
            "domain": {
                "status": "failed",
                "risk": None,
                "reasons": ["DOMAIN_LOOKUP_FAILED"],
                "flags": [],
                "evidence": {},
            },
        }

        dec = calculate_decision(dummy_context, scores)
        # Degraded cannot return MATCHES_OFFICIAL, must fallback to UNVERIFIED
        assert dec.verdict == "UNVERIFIED"
        assert dec.degraded is True
        assert "DEGRADED_MODE" in dec.reason_codes

    def test_stale_registry_entry_capped_at_unverified(self, dummy_context):
        # Brand matches, but entry is stale (> 90 days)
        scores = {
            "brand_identity": {
                "status": "ok",
                "risk": 0.0,
                "reasons": ["BRAND_CHANNEL_MATCH", "REGISTRY_STALE"],
                "flags": [],
                "evidence": {"outcome": "MATCH", "is_stale": True},
            },
        }

        dec = calculate_decision(dummy_context, scores)
        assert dec.verdict == "UNVERIFIED"

    def test_low_risk_without_registry_match_is_unverified(self, dummy_context):
        # No red flags found on unknown brand, but not officially registered
        scores = {
            "brand_identity": {
                "status": "ok",
                "risk": 0.2,
                "reasons": ["BRAND_NOT_IN_REGISTRY"],
                "flags": [],
                "evidence": {"outcome": "UNKNOWN_BRAND"},
            },
        }

        dec = calculate_decision(dummy_context, scores)
        # Never say safe / MATCHES_OFFICIAL without a verified registry match
        assert dec.verdict == "UNVERIFIED"
        assert dec.risk_score == 0.20
