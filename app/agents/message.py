"""Message Scorer for TrustShop AI.

Analyzes chat messages and message text using:
1. Rule-based regex pattern matcher:
   - OTP requests (hard flag: OTP_REQUEST)
   - Remote-access application requests (hard flag: REMOTE_ACCESS_REQUEST)
   - High-pressure urgency tactics (URGENCY_PRESSURE)
   - Advance payment demands (ADVANCE_PAYMENT_REQUEST)
   - Off-platform / personal chat migration (OFF_PLATFORM_MOVE)
   - Unrealistic lottery / prize claims (SUSPICIOUS_OFFER)
2. Machine Learning:
   - TF-IDF + Logistic Regression scam classifier (asyncio.to_thread).
"""

from __future__ import annotations

import asyncio
import re
from pathlib import Path
from typing import Any

import joblib

from app.extraction import CheckContext

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
MODEL_PATH = PROJECT_ROOT / "data" / "models" / "message_classifier.joblib"

_CACHED_MODEL = None
_MODEL_LOAD_ATTEMPTED = False

# Regex patterns for scam tactic rules
OTP_PATTERNS = [
    re.compile(r"\b(share|send|tell|give|enter|forward|provide|drop)\s+(me\s+)?(the\s+)?otp\b", re.IGNORECASE),
    re.compile(r"\b(one\s*time\s*password|verification\s*code|pin)\b.*\b(share|send|give|verify|enter|forward)\b", re.IGNORECASE),
    re.compile(r"\b(share|send|give|verify|enter|forward)\b.*\b(one\s*time\s*password|verification\s*code)\b", re.IGNORECASE),
    re.compile(r"\bread\s+out\s+(the\s+)?otp\b", re.IGNORECASE),
    re.compile(r"\b(otp|code)\s+sent\s+to\s+your\b", re.IGNORECASE),
]

REMOTE_ACCESS_PATTERNS = [
    re.compile(r"\b(anydesk|teamviewer|quicksupport|rustdesk|airdroid|ultraviewer)\b", re.IGNORECASE),
    re.compile(r"\b(screen\s*share|share\s+your\s+screen)\b", re.IGNORECASE),
    re.compile(r"\b(install|download)\s+.*(remote\s*access|support\s*app|\.apk)\b", re.IGNORECASE),
]

URGENCY_PATTERNS = [
    re.compile(r"\b(today\s+only|last\s+\d+\s+(pieces?|units?|items?|pairs?)|limited\s+time\s+deal|deal\s+expires|hurry\s+up|urgent|offer\s+ends\s+in|valid\s+only\s+for\s+today|act\s+fast|rush\s+now)\b", re.IGNORECASE),
    re.compile(r"\b(valid\s+for\s+\d+\s+minutes?\s+only)\b", re.IGNORECASE),
    re.compile(r"\b(flash\s+offer|flash\s+clearance|last\s+chance)\b", re.IGNORECASE),
]

ADVANCE_PAYMENT_PATTERNS = [
    re.compile(r"\b(advance\s+payment|token\s+amount|courier\s+charges?\s+in\s+advance|pay\s+advance|pay\s+first|full\s+payment\s+before\s+dispatch|registration\s+fee|processing\s+fee\s+first|refundable\s+deposit|security\s+deposit)\b", re.IGNORECASE),
    re.compile(r"\b(pay\s+rs\.?\s*\d+\s+now\s+to\s+hold)\b", re.IGNORECASE),
]

OFF_PLATFORM_PATTERNS = [
    re.compile(r"\b(inbox\s+me|dm\s+on\s+telegram|message\s+me\s+on\s+whatsapp|contact\s+personally|switch\s+to\s+personal|chat\s+privately|reach\s+me\s+on\s+telegram|ping\s+me\s+on\s+whatsapp)\b", re.IGNORECASE),
    re.compile(r"\b(message\s+me\s+privately|contact\s+manager\s+on\s+whatsapp)\b", re.IGNORECASE),
]

SUSPICIOUS_OFFER_PATTERNS = [
    re.compile(r"\b(congratulations|congrats)\b.*\b(won|winner|selected|prize|jackpot|reward|gift)\b", re.IGNORECASE),
    re.compile(r"\b(lucky\s*draw|lottery|jackpot|cash\s*prize)\b", re.IGNORECASE),
    re.compile(r"\bwon\s+.*(prize|cash|lakhs|crores|reward)\b", re.IGNORECASE),
    re.compile(r"\b(90%\s*off|free\s+iphone|claim\s+prize|claim\s+your\s+prize|guaranteed\s+returns?|earn\s+daily\s+rs\.?\s*\d+)\b", re.IGNORECASE),
    re.compile(r"\b(unclaimed\s+tax\s+refund|lucky\s+shopper\s+reward|festival\s+loot)\b", re.IGNORECASE),
]


def load_ml_model():
    """Load cached ML model pipeline from disk if available."""
    global _CACHED_MODEL, _MODEL_LOAD_ATTEMPTED
    if not _MODEL_LOAD_ATTEMPTED:
        _MODEL_LOAD_ATTEMPTED = True
        if MODEL_PATH.exists():
            try:
                _CACHED_MODEL = joblib.load(MODEL_PATH)
            except (OSError, ValueError, KeyError, AttributeError):
                _CACHED_MODEL = None
    return _CACHED_MODEL


def evaluate_message_rules(text: str) -> tuple[float, list[str], list[str], list[str]]:
    """Evaluate scam tactic rules against message text.
    Returns: (rule_risk, reasons, flags, rule_hits)
    """
    reasons: list[str] = []
    flags: list[str] = []
    hits: list[str] = []
    risk = 0.0

    # 1. OTP Request (Hard Flag)
    for p in OTP_PATTERNS:
        if p.search(text):
            flags.append("OTP_REQUEST")
            reasons.append("OTP_REQUEST")
            hits.append("otp_request")
            risk = max(risk, 0.90)
            break

    # 2. Remote Access Request (Hard Flag)
    for p in REMOTE_ACCESS_PATTERNS:
        if p.search(text):
            flags.append("REMOTE_ACCESS_REQUEST")
            reasons.append("REMOTE_ACCESS_REQUEST")
            hits.append("remote_access_request")
            risk = max(risk, 0.90)
            break

    # 3. Urgency Pressure
    for p in URGENCY_PATTERNS:
        if p.search(text):
            reasons.append("URGENCY_PRESSURE")
            hits.append("urgency_pressure")
            risk = max(risk, 0.35)
            break

    # 4. Advance Payment Demands
    for p in ADVANCE_PAYMENT_PATTERNS:
        if p.search(text):
            reasons.append("ADVANCE_PAYMENT_REQUEST")
            hits.append("advance_payment_request")
            risk = max(risk, 0.50)
            break

    # 5. Off-platform migration
    for p in OFF_PLATFORM_PATTERNS:
        if p.search(text):
            reasons.append("OFF_PLATFORM_MOVE")
            hits.append("off_platform_move")
            risk = max(risk, 0.30)
            break

    # 6. Suspicious offer / lottery
    for p in SUSPICIOUS_OFFER_PATTERNS:
        if p.search(text):
            reasons.append("SUSPICIOUS_OFFER")
            hits.append("suspicious_offer")
            risk = max(risk, 0.45)
            break

    return risk, reasons, flags, hits


def run_model_prediction(model: Any, text: str) -> float | None:
    """Synchronous model inference helper executed in thread pool."""
    try:
        prob = model.predict_proba([text])[0][1]
        return float(prob)
    except (ValueError, TypeError, AttributeError):
        return None


async def message_scorer(context: CheckContext) -> dict[str, Any]:
    """Score message text using rule patterns and TF-IDF logistic regression model."""
    text = context.message_text
    if not text or not text.strip():
        return {
            "status": "not_applicable",
            "risk": None,
            "reasons": [],
            "flags": [],
            "evidence": {"details": "No message text provided."},
        }

    cleaned_text = text.strip()

    # 1. Rule-based evaluation
    rule_risk, reasons, flags, hits = evaluate_message_rules(cleaned_text)

    # 2. ML model prediction via asyncio.to_thread (non-blocking)
    model = load_ml_model()
    ml_prob: float | None = None
    if model is not None:
        ml_prob = await asyncio.to_thread(run_model_prediction, model, cleaned_text)

    # 3. Combine scores
    evidence: dict[str, Any] = {
        "rule_hits": hits,
        "ml_scam_probability": round(ml_prob, 3) if ml_prob is not None else None,
        "ml_model_loaded": model is not None,
    }

    if "OTP_REQUEST" in flags or "REMOTE_ACCESS_REQUEST" in flags:
        final_risk = 0.90
    elif hits and ml_prob is not None:
        # Rules primary, ML supporting
        final_risk = min(0.95, max(rule_risk, 0.65 * rule_risk + 0.35 * ml_prob))
    elif hits:
        final_risk = rule_risk
    elif ml_prob is not None:
        # No explicit rule hit; pure ML probability with lower weight
        if ml_prob > 0.70:
            final_risk = 0.50
            reasons.append("SUSPICIOUS_OFFER")
        else:
            final_risk = min(0.20, ml_prob * 0.30)
    else:
        # Clean message with no rule hits
        final_risk = 0.05

    return {
        "status": "ok",
        "risk": round(final_risk, 2),
        "reasons": reasons,
        "flags": flags,
        "evidence": evidence,
    }
