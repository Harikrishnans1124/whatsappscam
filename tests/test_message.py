"""Tests for Phase 3c: Message Scorer."""

import pytest

from app.agents.message import (
    evaluate_message_rules,
    message_scorer,
)
from app.extraction import CheckContext, normalize_phone


@pytest.fixture
def base_context():
    return CheckContext(
        phone=normalize_phone(None),
        extracted_phones=[],
        urls=[],
        upi_ids=[],
        payment={},
        brand=None,
    )


def test_evaluate_message_rules_otp():
    text = "Please share the OTP you just received from your bank to verify."
    risk, reasons, flags, hits = evaluate_message_rules(text)
    assert "OTP_REQUEST" in flags
    assert "OTP_REQUEST" in reasons
    assert "otp_request" in hits
    assert risk >= 0.85


def test_evaluate_message_rules_remote_access():
    text = "Download TeamViewer QuickSupport or AnyDesk so our executive can assist."
    risk, reasons, flags, hits = evaluate_message_rules(text)
    assert "REMOTE_ACCESS_REQUEST" in flags
    assert "REMOTE_ACCESS_REQUEST" in reasons
    assert "remote_access_request" in hits
    assert risk >= 0.85


def test_evaluate_message_rules_urgency_and_advance():
    text = "Today only mega sale! Last 2 pairs in stock. Pay token amount of Rs 500 now."
    risk, reasons, flags, hits = evaluate_message_rules(text)
    assert "URGENCY_PRESSURE" in reasons
    assert "ADVANCE_PAYMENT_REQUEST" in reasons
    assert len(flags) == 0
    assert "urgency_pressure" in hits
    assert risk >= 0.50


@pytest.mark.asyncio
async def test_message_not_applicable(base_context):
    base_context.message_text = ""
    res = await message_scorer(base_context)
    assert res["status"] == "not_applicable"
    assert res["risk"] is None
    assert len(res["reasons"]) == 0


@pytest.mark.asyncio
async def test_message_otp_scam(base_context):
    base_context.message_text = "Dear customer, read out the OTP sent to your phone to complete order."
    res = await message_scorer(base_context)
    assert res["status"] == "ok"
    assert "OTP_REQUEST" in res["flags"]
    assert "OTP_REQUEST" in res["reasons"]
    assert res["risk"] >= 0.85


@pytest.mark.asyncio
async def test_message_remote_access(base_context):
    base_context.message_text = "Install AnyDesk app on your phone to resolve your refund issue."
    res = await message_scorer(base_context)
    assert res["status"] == "ok"
    assert "REMOTE_ACCESS_REQUEST" in res["flags"]
    assert "REMOTE_ACCESS_REQUEST" in res["reasons"]
    assert res["risk"] >= 0.85


@pytest.mark.asyncio
async def test_message_off_platform(base_context):
    base_context.message_text = "Message me on WhatsApp or DM on Telegram for secret discount."
    res = await message_scorer(base_context)
    assert res["status"] == "ok"
    assert "OFF_PLATFORM_MOVE" in res["reasons"]


@pytest.mark.asyncio
async def test_message_lottery_scam(base_context):
    base_context.message_text = "Congratulations! Your mobile number won 25 Lakhs cash prize in lucky draw."
    res = await message_scorer(base_context)
    assert res["status"] == "ok"
    assert "SUSPICIOUS_OFFER" in res["reasons"]
    assert res["risk"] >= 0.40


@pytest.mark.asyncio
async def test_message_legitimate_customer_inquiry(base_context):
    base_context.message_text = "Hello, do you have this shirt in medium size and blue color? Also what is your return policy?"
    res = await message_scorer(base_context)
    assert res["status"] == "ok"
    assert len(res["flags"]) == 0
    assert len(res["reasons"]) == 0
    assert res["risk"] <= 0.15
