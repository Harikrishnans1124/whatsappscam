"""Decision Layer for TrustShop AI.

Combines scorer risk scores using normalized weights, enforces hard-flag floors,
and applies safety-first verdict rules.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.config import settings
from app.extraction import CheckContext

DEFAULT_WEIGHTS = {
    "brand_identity": 0.35,
    "payment": 0.20,
    "message": 0.20,
    "domain": 0.15,
    "number": 0.10,
}

DEFAULT_FLOORS = {
    "BRAND_CHANNEL_MISMATCH": 0.55,
    "PERSONAL_PAYEE": 0.70,
    "LOOKALIKE_DOMAIN": 0.85,
    "OTP_REQUEST": 0.85,
    "REMOTE_ACCESS_REQUEST": 0.85,
}

DEFAULT_THRESHOLDS = {
    "suspicious_from": 0.35,
    "likely_scam_from": 0.65,
}


@dataclass
class DecisionResult:
    verdict: str  # "MATCHES_OFFICIAL", "UNVERIFIED", "SUSPICIOUS", "LIKELY_SCAM"
    risk_score: float | None
    reason_codes: list[str]
    flags: list[str]
    degraded: bool
    highest_floor_applied: str | None = None


def calculate_decision(
    context: CheckContext,
    scores: dict[str, dict[str, Any]],
    custom_settings: dict[str, Any] | None = None,
) -> DecisionResult:
    cfg = custom_settings or settings
    weights_cfg = cfg.get("weights", DEFAULT_WEIGHTS)
    floors_cfg = cfg.get("floors", DEFAULT_FLOORS)
    verdict_cfg = cfg.get("verdict", DEFAULT_THRESHOLDS)

    suspicious_threshold = verdict_cfg.get("suspicious_from", 0.35)
    likely_scam_threshold = verdict_cfg.get("likely_scam_from", 0.65)

    # 1. Collect flags, reasons, and check for degraded status
    all_flags: list[str] = []
    all_reasons: list[str] = []
    degraded = False

    for scorer_name, res in scores.items():
        if res.get("status") == "failed":
            degraded = True
        for f in res.get("flags", []):
            if f not in all_flags:
                all_flags.append(f)
        for r in res.get("reasons", []):
            if r not in all_reasons:
                all_reasons.append(r)

    if degraded and "DEGRADED_MODE" not in all_reasons:
        all_reasons.append("DEGRADED_MODE")

    # 2. Weighted risk calculation over scorers with status == "ok"
    active_weighted_sum = 0.0
    active_weight_total = 0.0

    for scorer_name, weight in weights_cfg.items():
        res = scores.get(scorer_name)
        if res and res.get("status") == "ok" and res.get("risk") is not None:
            active_weighted_sum += weight * float(res["risk"])
            active_weight_total += weight

    risk_weighted: float | None = None
    if active_weight_total > 0:
        risk_weighted = active_weighted_sum / active_weight_total

    # 3. Apply hard-flag floors
    highest_floor = 0.0
    floor_flag: str | None = None
    for flag in all_flags:
        if flag in floors_cfg:
            fl_val = float(floors_cfg[flag])
            if fl_val > highest_floor:
                highest_floor = fl_val
                floor_flag = flag

    final_risk: float | None = None
    if risk_weighted is not None:
        if highest_floor > risk_weighted:
            final_risk = highest_floor
        else:
            final_risk = risk_weighted
            floor_flag = None
    elif highest_floor > 0:
        final_risk = highest_floor

    if final_risk is not None:
        final_risk = round(final_risk, 2)

    # 4. Check brand registry state for verdict eligibility
    brand_res = scores.get("brand_identity", {})
    evidence = brand_res.get("evidence", {})
    brand_outcome = evidence.get("outcome")
    is_stale = bool(evidence.get("is_stale", False))

    has_registry_match = (brand_outcome == "MATCH")
    has_mismatch = (
        brand_outcome == "MISMATCH" or "BRAND_CHANNEL_MISMATCH" in all_flags
    )

    # 5. Verdict determination
    if final_risk is not None and final_risk >= likely_scam_threshold:
        verdict = "LIKELY_SCAM"
    elif final_risk is not None and final_risk >= suspicious_threshold:
        verdict = "SUSPICIOUS"
    elif final_risk is None:
        verdict = "UNVERIFIED"
    else:
        # final_risk < suspicious_threshold (low risk)
        # MATCHES_OFFICIAL requires:
        # 1. At least one channel matched registry
        # 2. No channels mismatched
        # 3. Not degraded
        # 4. Registry entry is not stale
        if has_registry_match and not has_mismatch and not degraded and not is_stale:
            verdict = "MATCHES_OFFICIAL"
        else:
            verdict = "UNVERIFIED"

    return DecisionResult(
        verdict=verdict,
        risk_score=final_risk,
        reason_codes=all_reasons,
        flags=all_flags,
        degraded=degraded,
        highest_floor_applied=floor_flag,
    )
