"""Hash-chained, tamper-evident audit logger for TrustShop AI.

Privacy-by-design guarantees:
- HMAC-hashed identifiers only (phone, domain, UPI).
- Raw chat messages, user notes, and plain phone numbers are NEVER logged.
- Tamper-evident hash chain: entry_hash = SHA256(prev_hash || canonical_json(entry)).
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import threading
from pathlib import Path
from typing import Any

from app.registry import hmac_sha256

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_AUDIT_LOG_PATH = PROJECT_ROOT / "data" / "audit_log.jsonl"
GENESIS_HASH = "0" * 64

_AUDIT_LOCK = threading.Lock()


def canonical_json(obj: dict[str, Any]) -> bytes:
    """Format dictionary into deterministic, sorted canonical JSON bytes."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":")).encode("utf-8")


def get_last_entry_hash(log_path: Path | None = None) -> str:
    """Read the hash of the last entry in the audit log, or GENESIS_HASH if empty."""
    path = log_path or DEFAULT_AUDIT_LOG_PATH
    if not path.exists():
        return GENESIS_HASH

    last_line = ""
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                last_line = line.strip()

    if not last_line:
        return GENESIS_HASH

    try:
        data = json.loads(last_line)
        return data.get("entry_hash", GENESIS_HASH)
    except (json.JSONDecodeError, KeyError, OSError):
        return GENESIS_HASH


def build_audit_identifiers(
    phone_e164: str | None = None,
    domains: list[str] | None = None,
    upi_id: str | None = None,
) -> dict[str, Any]:
    """Create anonymized identifier dictionary using HMAC-SHA256 hashes only."""
    res: dict[str, Any] = {}
    if phone_e164:
        res["phone_hmac"] = hmac_sha256(phone_e164)
    if domains:
        res["domain_hmacs"] = [hmac_sha256(d) for d in sorted(domains)]
    if upi_id:
        res["upi_hmac"] = hmac_sha256(upi_id)
    return res


def append_audit_entry(
    check_id: str,
    verdict: str,
    risk_score: float | None,
    reason_codes: list[str],
    flags: list[str],
    hashed_identifiers: dict[str, Any],
    log_path: Path | None = None,
) -> dict[str, Any]:
    """Append a cryptographically chained audit record to the log."""
    path = log_path or DEFAULT_AUDIT_LOG_PATH
    path.parent.mkdir(parents=True, exist_ok=True)

    with _AUDIT_LOCK:
        prev_hash = get_last_entry_hash(path)
        timestamp = dt.datetime.now(dt.timezone.utc).isoformat()

        # Build entry content without entry_hash
        entry_payload = {
            "timestamp": timestamp,
            "check_id": check_id,
            "verdict": verdict,
            "risk_score": risk_score,
            "reason_codes": sorted(reason_codes),
            "flags": sorted(flags),
            "identifiers": hashed_identifiers,
            "prev_hash": prev_hash,
        }

        # Compute hash over prev_hash + canonical_json
        canonical_bytes = canonical_json(entry_payload)
        entry_hash = hashlib.sha256(prev_hash.encode("utf-8") + canonical_bytes).hexdigest()

        complete_entry = {
            **entry_payload,
            "entry_hash": entry_hash,
        }

        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(complete_entry) + "\n")

        return complete_entry


def verify_audit_log(log_path: Path | None = None) -> tuple[bool, int, str]:
    """Verify integrity of audit log by recalculating the hash chain from genesis."""
    path = log_path or DEFAULT_AUDIT_LOG_PATH
    if not path.exists():
        return True, 0, "Audit log does not exist yet (clean state)."

    expected_prev = GENESIS_HASH
    line_number = 0

    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line_str = line.strip()
            if not line_str:
                continue
            line_number += 1
            try:
                entry = json.loads(line_str)
            except (json.JSONDecodeError, KeyError, TypeError) as e:
                return False, line_number, f"Line {line_number} is not valid JSON: {e}"

            recorded_hash = entry.get("entry_hash")
            recorded_prev = entry.get("prev_hash")

            if recorded_prev != expected_prev:
                return (
                    False,
                    line_number,
                    f"Line {line_number}: prev_hash mismatch. Expected {expected_prev}, got {recorded_prev}",
                )

            # Reconstruct payload to recompute hash
            payload_to_verify = {k: v for k, v in entry.items() if k != "entry_hash"}
            canonical_bytes = canonical_json(payload_to_verify)
            computed_hash = hashlib.sha256(expected_prev.encode("utf-8") + canonical_bytes).hexdigest()

            if computed_hash != recorded_hash:
                return (
                    False,
                    line_number,
                    f"Line {line_number}: entry_hash mismatch. Content was modified or tampered!",
                )

            expected_prev = recorded_hash

    return True, line_number, f"Audit log verified successfully. {line_number} entries intact."
