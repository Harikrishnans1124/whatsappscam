"""Pydantic v2 schemas for TrustShop AI API requests and responses."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator


class PaymentInput(BaseModel):
    """Payment details submitted by user."""

    upi_id: str | None = Field(default=None, description="UPI ID or VPA (e.g. name@handle)")
    display_name: str | None = Field(
        default=None, description="Payee name shown in UPI app before confirming payment"
    )
    amount: float | None = Field(default=None, gt=0, description="Transaction amount")


class CheckRequest(BaseModel):
    """Payload for POST /v1/checks."""

    claimed_brand: str | None = Field(
        default=None, description="Brand the seller claims to be (optional, auto-detected if omitted)"
    )
    phone_number: str | None = Field(
        default=None, description="Phone or WhatsApp number in any format"
    )
    message_text: str | None = Field(
        default=None, max_length=5000, description="Pasted chat message text"
    )
    urls: list[str] = Field(
        default_factory=list, max_length=5, description="Links or URLs sent by the seller"
    )
    payment: PaymentInput | None = Field(
        default=None, description="Payment information"
    )
    language: str = Field(
        default="en", description="Explanation language ('en', 'ml', 'hi')"
    )

    @model_validator(mode="after")
    def validate_at_least_one_input(self) -> CheckRequest:
        has_phone = bool(self.phone_number and self.phone_number.strip())
        has_text = bool(self.message_text and self.message_text.strip())
        has_urls = bool(self.urls and len(self.urls) > 0)
        has_upi = bool(self.payment and self.payment.upi_id and self.payment.upi_id.strip())

        if not (has_phone or has_text or has_urls or has_upi):
            raise ValueError(
                "Provide at least one of phone_number, message_text, urls, or payment.upi_id"
            )
        return self


class ChannelMatch(BaseModel):
    phone: bool | None = None
    domain: bool | None = None
    payment: bool | None = None


class BrandMatchResult(BaseModel):
    claimed: str | None = None
    in_registry: bool = False
    registry_verified_on: str | None = None
    match: ChannelMatch = Field(default_factory=ChannelMatch)


class ScorerResultItem(BaseModel):
    status: Literal["ok", "not_applicable", "failed"]
    risk: float | None = None
    reasons: list[str] = Field(default_factory=list)
    flags: list[str] = Field(default_factory=list)
    evidence: dict[str, Any] = Field(default_factory=dict)


class ReasonItem(BaseModel):
    code: str
    text: str


class CheckResponse(BaseModel):
    """Response returned by POST /v1/checks."""

    check_id: str
    verdict: Literal["MATCHES_OFFICIAL", "UNVERIFIED", "SUSPICIOUS", "LIKELY_SCAM"]
    risk_score: float | None = None
    brand: BrandMatchResult | None = None
    scores: dict[str, ScorerResultItem]
    reason_codes: list[str]
    reasons: list[ReasonItem]
    summary: str
    advice: list[str]
    degraded: bool = False
    latency_ms: float
    disclaimer: str = (
        "Automated estimate, not proof. Always confirm through the brand's official website or app."
    )


class BrandSourceResponse(BaseModel):
    url: str
    verified_on: str


class BrandResponse(BaseModel):
    slug: str
    name: str
    official_domains: list[str]
    official_phones: list[str]
    payment_policy: str
    sources: list[BrandSourceResponse]


class ProblemDetail(BaseModel):
    """RFC 9457 Problem Details for HTTP APIs."""

    type: str = "about:blank"
    title: str
    status: int
    detail: str
    instance: str | None = None


class ReportCreateRequest(BaseModel):
    identifier: str = Field(..., description="Phone number, domain/URL, or UPI ID being reported")
    identifier_type: Literal["phone", "domain", "upi"] = Field(
        default="phone", description="Type of identifier"
    )
    category: str = Field(default="scam", description="Scam category, e.g. impersonation, advance_fee")
    notes: str | None = Field(default=None, max_length=500, description="Optional brief description")


class ReportResponse(BaseModel):
    status: str = "received"
    identifier_type: str
    distinct_reporters: int
    total_reports: int
    message: str = "Report successfully registered."

