"""Tests for Phase 4: Hash-Chained Audit Log and Tamper Detection."""

import json

import pytest

from app.audit import (
    GENESIS_HASH,
    append_audit_entry,
    build_audit_identifiers,
    verify_audit_log,
)


@pytest.fixture
def temp_audit_file(tmp_path):
    return tmp_path / "test_audit_log.jsonl"


def test_audit_log_append_and_chain(temp_audit_file):
    # Entry 1
    ids1 = build_audit_identifiers(phone_e164="+919876543210", domains=["deal.shop"])
    e1 = append_audit_entry(
        check_id="c_test01",
        verdict="SUSPICIOUS",
        risk_score=0.55,
        reason_codes=["BRAND_CHANNEL_MISMATCH"],
        flags=["BRAND_CHANNEL_MISMATCH"],
        hashed_identifiers=ids1,
        log_path=temp_audit_file,
    )
    assert e1["prev_hash"] == GENESIS_HASH
    assert len(e1["entry_hash"]) == 64

    # Entry 2
    ids2 = build_audit_identifiers(phone_e164="+9118002029898")
    e2 = append_audit_entry(
        check_id="c_test02",
        verdict="MATCHES_OFFICIAL",
        risk_score=0.03,
        reason_codes=["BRAND_CHANNEL_MATCH"],
        flags=[],
        hashed_identifiers=ids2,
        log_path=temp_audit_file,
    )
    assert e2["prev_hash"] == e1["entry_hash"]

    # Verify chain
    is_valid, count, msg = verify_audit_log(temp_audit_file)
    assert is_valid is True
    assert count == 2
    assert "verified successfully" in msg


def test_audit_log_privacy_guarantee(temp_audit_file):
    raw_phone = "+919876543210"
    raw_chat = "Please send OTP to complete your secret refund"
    raw_upi = "secret_scam_user@ybl"

    ids = build_audit_identifiers(phone_e164=raw_phone, upi_id=raw_upi)
    append_audit_entry(
        check_id="c_privacy_check",
        verdict="LIKELY_SCAM",
        risk_score=0.85,
        reason_codes=["OTP_REQUEST"],
        flags=["OTP_REQUEST"],
        hashed_identifiers=ids,
        log_path=temp_audit_file,
    )

    with temp_audit_file.open("r", encoding="utf-8") as f:
        content = f.read()

    # Raw identifiers and chat must NEVER exist in plain text
    assert raw_phone not in content
    assert raw_chat not in content
    assert raw_upi not in content
    # Only HMAC hashes should exist
    assert "phone_hmac" in content
    assert "upi_hmac" in content


def test_audit_log_tamper_detection(temp_audit_file):
    # Add 2 legitimate entries
    append_audit_entry("c_01", "SUSPICIOUS", 0.55, ["CODE1"], [], {}, log_path=temp_audit_file)
    append_audit_entry("c_02", "LIKELY_SCAM", 0.85, ["CODE2"], [], {}, log_path=temp_audit_file)

    # Confirm valid initially
    assert verify_audit_log(temp_audit_file)[0] is True

    # Tamper with first entry: change verdict from SUSPICIOUS to MATCHES_OFFICIAL
    lines = temp_audit_file.read_text(encoding="utf-8").splitlines()
    data0 = json.loads(lines[0])
    data0["verdict"] = "MATCHES_OFFICIAL"  # Malicious tampering!
    lines[0] = json.dumps(data0)
    temp_audit_file.write_text("\n".join(lines) + "\n", encoding="utf-8")

    # Verifier must detect tampering and fail!
    is_valid, line_num, msg = verify_audit_log(temp_audit_file)
    assert is_valid is False
    assert line_num == 1
    assert "entry_hash mismatch" in msg or "tampered" in msg
