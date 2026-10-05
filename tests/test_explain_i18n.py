"""Unit tests for explanation generation and multilingual i18n (en, ml, hi)."""

from app.explain import generate_explanation, load_translations
from app.extraction import CheckContext


def test_i18n_files_load_properly():
    en = load_translations("en")
    ml = load_translations("ml")
    hi = load_translations("hi")

    assert "BRAND_CHANNEL_MATCH" in en["reasons"]
    assert "BRAND_CHANNEL_MATCH" in ml["reasons"]
    assert "BRAND_CHANNEL_MATCH" in hi["reasons"]

    assert "MATCHES_OFFICIAL" in en["summaries"]
    assert "MATCHES_OFFICIAL" in ml["summaries"]
    assert "MATCHES_OFFICIAL" in hi["summaries"]

    assert "LIKELY_SCAM" in en["advice"]
    assert "LIKELY_SCAM" in ml["advice"]
    assert "LIKELY_SCAM" in hi["advice"]


def test_english_explanation():
    ctx = CheckContext(
        brand={"name": "Flipkart", "claimed": "Flipkart", "in_registry": True},
        language="en",
    )
    explanation = generate_explanation(
        ctx,
        verdict="LIKELY_SCAM",
        reason_codes=["BRAND_CHANNEL_MISMATCH", "LOOKALIKE_DOMAIN", "OTP_REQUEST"],
        language="en",
    )

    assert "Flipkart" in explanation["summary"]
    assert "Warning: Strong indicators of impersonation" in explanation["summary"]
    assert len(explanation["reasons"]) == 3
    assert explanation["reasons"][0].code == "BRAND_CHANNEL_MISMATCH"
    assert "not on the brand's official published list" in explanation["reasons"][0].text
    assert any("1930" in adv for adv in explanation["advice"])


def test_malayalam_explanation():
    ctx = CheckContext(
        brand={"name": "Amazon India", "claimed": "Amazon India", "in_registry": True},
        language="ml",
    )
    explanation = generate_explanation(
        ctx,
        verdict="LIKELY_SCAM",
        reason_codes=["BRAND_CHANNEL_MISMATCH", "OTP_REQUEST"],
        language="ml",
    )

    assert "Amazon India" in explanation["summary"]
    assert "മുന്നറിയിപ്പ്:" in explanation["summary"]
    assert len(explanation["reasons"]) == 2
    assert "ഔദ്യോഗിക" in explanation["reasons"][0].text
    assert any("1930" in adv for adv in explanation["advice"])


def test_hindi_explanation():
    ctx = CheckContext(
        brand={"name": "Myntra", "claimed": "Myntra", "in_registry": True},
        language="hi",
    )
    explanation = generate_explanation(
        ctx,
        verdict="SUSPICIOUS",
        reason_codes=["PERSONAL_PAYEE", "URGENCY_PRESSURE"],
        language="hi",
    )

    assert "Myntra" in explanation["summary"]
    assert "सावधान:" in explanation["summary"]
    assert len(explanation["reasons"]) == 2
    assert "व्यक्तिगत खाता" in explanation["reasons"][0].text


def test_unsupported_language_fallback():
    ctx = CheckContext(
        brand={"name": "Acme Footwear"},
        language="fr",
    )
    explanation = generate_explanation(
        ctx,
        verdict="MATCHES_OFFICIAL",
        reason_codes=["BRAND_CHANNEL_MATCH"],
        language="fr",
    )

    # Should fall back cleanly to English
    assert "Acme Footwear" in explanation["summary"]
    assert "matches the official published channels" in explanation["summary"]
