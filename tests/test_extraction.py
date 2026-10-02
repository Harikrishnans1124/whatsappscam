"""Unit tests for app.extraction module."""

import pytest

from app.extraction import (
    detect_claimed_brand,
    extract_phones_from_text,
    extract_upi_ids,
    extract_urls,
    is_valid_upi_id,
    normalize_phone,
)


class TestPhoneNormalization:
    def test_standard_indian_mobile(self):
        res = normalize_phone("+91 98765 43210")
        assert res["valid"] is True
        assert res["e164"] == "+919876543210"
        assert res["type"] == "MOBILE"

    def test_indian_mobile_with_hyphens(self):
        res = normalize_phone("+91-98765-43210")
        assert res["valid"] is True
        assert res["e164"] == "+919876543210"

    def test_indian_mobile_ten_digits_default_region(self):
        res = normalize_phone("9876543210")
        assert res["valid"] is True
        assert res["e164"] == "+919876543210"

    def test_indian_mobile_leading_zero(self):
        res = normalize_phone("09876543210")
        assert res["valid"] is True
        assert res["e164"] == "+919876543210"

    def test_indian_mobile_double_zero_prefix(self):
        res = normalize_phone("00919876543210")
        assert res["valid"] is True
        assert res["e164"] == "+919876543210"

    def test_toll_free_number(self):
        res = normalize_phone("1800 202 9898")
        assert res["valid"] is True
        assert res["e164"] == "+9118002029898"
        assert res["type"] == "TOLL_FREE"

    def test_international_number(self):
        res = normalize_phone("+1 415 555 2671", default_region="US")
        assert res["valid"] is True
        assert res["e164"] == "+14155552671"

    def test_invalid_and_empty_inputs(self):
        assert normalize_phone(None)["valid"] is False
        assert normalize_phone("")["valid"] is False
        assert normalize_phone("invalid123")["valid"] is False
        assert normalize_phone("123")["valid"] is False


class TestUrlExtraction:
    def test_extract_urls_from_text(self):
        text = "Visit our official store at https://tatacliq.com/deals or shop at flipkart.com/sale"
        res = extract_urls(text)
        domains = [r["registrable_domain"] for r in res]
        assert "tatacliq.com" in domains
        assert "flipkart.com" in domains

    def test_extract_registrable_domain_with_subdomains(self):
        res = extract_urls("Check out https://luxury.tatacliq.com/collection")
        assert len(res) == 1
        assert res[0]["registrable_domain"] == "tatacliq.com"
        assert res[0]["subdomain"] == "luxury"
        assert res[0]["domain_label"] == "tatacliq"

    def test_extract_explicit_urls(self):
        res = extract_urls(None, explicit_urls=["https://amazon.in/dp/B08N5WRWNW", "acmefootwear-outlet.shop"])
        domains = [r["registrable_domain"] for r in res]
        assert "amazon.in" in domains
        assert "acmefootwear-outlet.shop" in domains

    def test_extract_phones_from_chat_text(self):
        text = "Call me at +91 98765 43210 or 080-61561999 for inquiries"
        phones = extract_phones_from_text(text)
        e164s = [p["e164"] for p in phones]
        assert "+919876543210" in e164s
        assert "+918061561999" in e164s


class TestUpiIdExtraction:
    def test_valid_upi_ids(self):
        assert is_valid_upi_id("merchant@okhdfcbank") is True
        assert is_valid_upi_id("rakesh99@ybl") is True
        assert is_valid_upi_id("paytmuser@paytm") is True
        assert is_valid_upi_id("9876543210@ibl") is True

    def test_reject_emails(self):
        assert is_valid_upi_id("support@amazon.in") is False
        assert is_valid_upi_id("seller@gmail.com") is False
        assert is_valid_upi_id("john.doe@yahoo.co.in") is False
        assert is_valid_upi_id("contact@company.org") is False
        assert is_valid_upi_id("info@brand.com") is False

    def test_extract_upi_from_text(self):
        text = "Pay advance to seller99@ybl or contact us at help@store.com"
        upis = extract_upi_ids(text)
        assert "seller99@ybl" in upis
        assert "help@store.com" not in upis

    def test_explicit_upi_input(self):
        upis = extract_upi_ids(None, explicit_upi="official@okhdfcbank")
        assert upis == ["official@okhdfcbank"]


class TestBrandDetection:
    @pytest.fixture
    def mock_registry(self):
        return [
            {
                "slug": "flipkart",
                "name": "Flipkart",
                "aliases": ["Flipkart Internet", "Flipkart Plus"],
                "official_domains": ["flipkart.com"],
                "official_phones": ["+9118002029898"],
            },
            {
                "slug": "acme-footwear",
                "name": "Acme Footwear",
                "aliases": ["acme shoes", "acme"],
                "official_domains": ["acmefootwear.com"],
                "official_phones": ["+911800112233"],
            },
        ]

    def test_detect_by_user_input_exact(self, mock_registry):
        res = detect_claimed_brand("Flipkart", None, [], mock_registry)
        assert res is not None
        assert res["slug"] == "flipkart"
        assert res["in_registry"] is True

    def test_detect_by_alias(self, mock_registry):
        res = detect_claimed_brand("acme shoes", None, [], mock_registry)
        assert res is not None
        assert res["slug"] == "acme-footwear"
        assert res["in_registry"] is True

    def test_detect_unknown_brand(self, mock_registry):
        res = detect_claimed_brand("UnknownBoutique", None, [], mock_registry)
        assert res is not None
        assert res["slug"] is None
        assert res["name"] == "UnknownBoutique"
        assert res["in_registry"] is False

    def test_detect_from_message_text(self, mock_registry):
        res = detect_claimed_brand(None, "Exclusive Flipkart Plus sale today only!", [], mock_registry)
        assert res is not None
        assert res["slug"] == "flipkart"
        assert res["in_registry"] is True

    def test_detect_from_domain_tokens(self, mock_registry):
        urls = [{"domain_label": "acmefootwear-outlet", "registrable_domain": "acmefootwear-outlet.shop"}]
        res = detect_claimed_brand(None, None, urls, mock_registry)
        assert res is not None
        assert res["slug"] == "acme-footwear"
        assert res["in_registry"] is True

    def test_no_brand_detected(self, mock_registry):
        res = detect_claimed_brand(None, "Great shirts for sale, call me", [], mock_registry)
        assert res is None
