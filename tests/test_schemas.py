"""Unit tests for app.schemas module."""

import pytest
from pydantic import ValidationError

from app.schemas import CheckRequest, PaymentInput


class TestSchemas:
    def test_valid_phone_only(self):
        req = CheckRequest(phone_number="+91 98765 43210")
        assert req.phone_number == "+91 98765 43210"

    def test_valid_message_only(self):
        req = CheckRequest(message_text="Hello from seller")
        assert req.message_text == "Hello from seller"

    def test_valid_url_only(self):
        req = CheckRequest(urls=["https://flipkart.com"])
        assert len(req.urls) == 1

    def test_valid_payment_only(self):
        req = CheckRequest(payment=PaymentInput(upi_id="merchant@okhdfcbank"))
        assert req.payment is not None
        assert req.payment.upi_id == "merchant@okhdfcbank"

    def test_reject_empty_request(self):
        with pytest.raises(ValidationError) as exc:
            CheckRequest()
        assert "Provide at least one of" in str(exc.value)

    def test_reject_whitespace_only_inputs(self):
        with pytest.raises(ValidationError) as exc:
            CheckRequest(phone_number="   ", message_text="   ")
        assert "Provide at least one of" in str(exc.value)

    def test_reject_excessive_urls(self):
        with pytest.raises(ValidationError):
            CheckRequest(urls=[f"https://example{i}.com" for i in range(10)])

    def test_reject_excessive_message_length(self):
        with pytest.raises(ValidationError):
            CheckRequest(message_text="A" * 5001)
