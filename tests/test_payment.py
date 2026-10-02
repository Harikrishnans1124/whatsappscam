"""Tests for Phase 3a: Payment Scorer."""

import pytest

from app.agents.payment import (
    is_personal_name,
    is_phone_number_upi,
    normalize_entity_name,
    payment_scorer,
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
                "legal_names": [
                    "Amazon Seller Services Private Limited",
                    "Amazon Wholesale (India) Private Limited",
                    "Amazon Pay (India) Private Limited",
                ],
                "aliases": ["Amazon", "Amazon.in", "Amazon Pay"],
            },
        },
    )


@pytest.fixture
def unverified_context():
    return CheckContext(
        phone=normalize_phone(None),
        extracted_phones=[],
        urls=[],
        upi_ids=[],
        payment={},
        brand={
            "claimed": "Local Corner Shop",
            "slug": None,
            "name": "Local Corner Shop",
            "in_registry": False,
            "brand_data": None,
        },
    )


def test_normalize_entity_name():
    assert normalize_entity_name("Amazon Seller Services Pvt. Ltd.") == "amazon seller services private limited"
    assert normalize_entity_name("Acme Footwear Corp.") == "acme footwear corporation"
    assert normalize_entity_name("Global Ventures Inc") == "global ventures incorporated"


def test_is_personal_name():
    # Personal names
    assert is_personal_name("Ramesh Kumar") is True
    assert is_personal_name("Suresh Pillai") is True
    assert is_personal_name("John Doe") is True
    assert is_personal_name("Ananya S") is True

    # Business / Corporate names
    assert is_personal_name("Amazon Seller Services Pvt Ltd") is False
    assert is_personal_name("Flipkart India Private Limited") is False
    assert is_personal_name("Acme Shoes Retail Store") is False
    assert is_personal_name("QuickTech Solutions") is False
    assert is_personal_name("Apex Enterprises") is False


def test_is_phone_number_upi():
    assert is_phone_number_upi("9876543210@ybl") is True
    assert is_phone_number_upi("+919876543210@paytm") is True
    assert is_phone_number_upi("919876543210@okaxis") is True
    assert is_phone_number_upi("amazonpay@icici") is False
    assert is_phone_number_upi("flipkart.merchant@hdfc") is False
    assert is_phone_number_upi("") is False


@pytest.mark.asyncio
async def test_payment_not_applicable(amazon_context):
    res = await payment_scorer(amazon_context)
    assert res["status"] == "not_applicable"
    assert res["risk"] is None
    assert len(res["reasons"]) == 0
    assert len(res["flags"]) == 0


@pytest.mark.asyncio
async def test_payment_exact_legal_name_match(amazon_context):
    amazon_context.payment = {
        "upi_id": "amazonseller@icici",
        "display_name": "Amazon Seller Services Private Limited",
    }
    res = await payment_scorer(amazon_context)
    assert res["status"] == "ok"
    assert res["risk"] <= 0.10
    assert "PAYEE_NAME_MATCH" in res["reasons"]
    assert "PAYEE_NAME_MISMATCH" not in res["reasons"]
    assert len(res["flags"]) == 0


@pytest.mark.asyncio
async def test_payment_abbreviation_variation_match(amazon_context):
    # 'Pvt Ltd' variation against 'Private Limited'
    amazon_context.payment = {
        "upi_id": "amazonpay@okhdfcbank",
        "display_name": "Amazon Pay (India) Pvt Ltd",
    }
    res = await payment_scorer(amazon_context)
    assert res["status"] == "ok"
    assert "PAYEE_NAME_MATCH" in res["reasons"]
    assert res["evidence"]["best_fuzzy_score"] >= 80


@pytest.mark.asyncio
async def test_payment_personal_payee_for_known_brand(amazon_context):
    # Known brand (Amazon India) but payment is demanded to an individual
    amazon_context.payment = {
        "upi_id": "9876543210@ybl",
        "display_name": "Ramesh Kumar",
    }
    res = await payment_scorer(amazon_context)
    assert res["status"] == "ok"
    assert res["risk"] >= 0.70
    assert "PERSONAL_PAYEE" in res["flags"]
    assert "PERSONAL_PAYEE" in res["reasons"]
    assert "PAYEE_NAME_MISMATCH" in res["reasons"]
    assert "PHONE_STYLE_UPI" in res["reasons"]


@pytest.mark.asyncio
async def test_payment_corporate_mismatch_for_known_brand(amazon_context):
    # Known brand (Amazon India) but payment is to another third-party company
    amazon_context.payment = {
        "upi_id": "abcenterprises@icici",
        "display_name": "ABC Global Enterprises LLP",
    }
    res = await payment_scorer(amazon_context)
    assert res["status"] == "ok"
    assert "PAYEE_NAME_MISMATCH" in res["reasons"]
    # Should not raise PERSONAL_PAYEE since it contains 'Enterprises' and 'LLP'
    assert "PERSONAL_PAYEE" not in res["flags"]


@pytest.mark.asyncio
async def test_payment_phone_style_upi_without_name(amazon_context):
    amazon_context.payment = {
        "upi_id": "9876543210@paytm",
    }
    res = await payment_scorer(amazon_context)
    assert res["status"] == "ok"
    assert "PHONE_STYLE_UPI" in res["reasons"]
    assert res["risk"] >= 0.35


@pytest.mark.asyncio
async def test_payment_unverified_brand_personal_payee(unverified_context):
    unverified_context.payment = {
        "upi_id": "9876543210@paytm",
        "display_name": "Suresh Pillai",
    }
    res = await payment_scorer(unverified_context)
    assert res["status"] == "ok"
    # Unverified/unregistered brand should NOT trigger hard floor PERSONAL_PAYEE flag
    assert "PERSONAL_PAYEE" not in res["flags"]
    assert "PHONE_STYLE_UPI" in res["reasons"]
    assert res["risk"] <= 0.40
