# Phase 4 Summary: Resilience, Caching, and Safety

**Date:** October 2, 2026  
**Status:** Completed & Verified  

---

## 1. Accomplishments Overview

Phase 4 hardens TrustShop AI into a production-grade, highly resilient, and privacy-preserving security engine:

### 4a. Circuit Breakers & Timeout Guards (`app/breaker.py`)
- **Per-Scorer Timeouts**: Configurable execution timeouts per scorer via `config/settings.yaml` (150 ms for local CPU/DB scorers: `brand_identity`, `payment`, `message`, `number`; 2,500 ms for network-dependent `domain` RDAP lookups).
- **Custom 3-State Circuit Breaker**: Hand-crafted `CircuitBreaker` pattern (`CLOSED`, `OPEN`, `HALF_OPEN`) tracking failure count and reset timeouts.
- **Fast Fail Rejection**: When a circuit opens (after 5 failures), subsequent calls fail fast without launching work or hanging, returning `SCORER_UNAVAILABLE`.
- **Clean Coroutine Lifecycle**: Coroutines are properly closed on fast rejection or cancellation to prevent Python task leakage.

### 4b. Outbound Safe Fetch & SSRF Protection (`app/safe_fetch.py`)
- **Strict Outbound Allowlist**: Outbound HTTP traffic is restricted strictly to trusted infrastructure: `rdap.org`, `client.rdap.org`, `safebrowsing.googleapis.com`.
- **SSRF Attack Blockers**: Automatically rejects attempts against loopback (`127.0.0.1`, `localhost`), RFC 1918 private subnets (`10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`), cloud metadata services (`169.254.169.254`), link-local, multicast, and direct IP addresses.
- **User URLs Never Fetched**: Guaranteed by design that arbitrary user-provided links are never contacted over the network.

### 4c. Redis Caching & Rate Limiting (`app/cache.py`)
- **RDAP Registration Caching**: 24-hour TTL caching for domain registration dates to minimize outbound latency and avoid RDAP server throttling.
- **Fixed-Window IP Rate Limiter**: Configurable request limits (default 30 req/min per client IP) returning RFC 9457 compliant HTTP 429 (`TOO_MANY_REQUESTS`).
- **Graceful Fail-Open / Degraded Operation**: When Redis is offline or unreachable, system automatically falls back to in-memory caching and fail-open rate limiting without dropping incoming traffic.

### 4d. Cryptographic Hash-Chained Audit Log (`app/audit.py`, `scripts/verify_audit.py`)
- **Tamper-Evident Hash Chain**: Each audit entry links to the preceding entry using `entry_hash = SHA256(prev_hash || canonical_json(entry))`.
- **Zero Raw PII Storage**: Chat text and plain phone numbers are strictly forbidden. Only HMAC-SHA256 hashed identifiers (`phone_hmac`, `domain_hmacs`, `upi_hmac`) are stored.
- **Integrity Verifier CLI**: `scripts/verify_audit.py` verifies the entire cryptographic chain on demand and pinpoints any tampered records.

### 4e. Degraded Mode & Safe Decisions (`app/decision.py`, `app/main.py`)
- **Degraded Flag**: If any external dependency or scorer fails, `degraded` is set to `True`.
- **Safety Invariant**: Under degraded mode, a check can **never** output `MATCHES_OFFICIAL`, capping confidence at `UNVERIFIED` and surfacing `DEGRADED_MODE` warnings to users.

---

## 2. Verification & Acceptance Criteria

1. **Slow/Broken RDAP Handling**:
   - Verified via `tests/test_api.py::test_api_broken_rdap_degraded_mode`.
   - Broken RDAP returns HTTP 200, `degraded: true`, verdict capped at `UNVERIFIED` (never `MATCHES_OFFICIAL`).
2. **Rate Limiting (HTTP 429)**:
   - Verified via `tests/test_cache.py::test_api_rate_limit_exceeded_returns_429`.
   - Exceeding the request quota triggers RFC 9457 `429 Too Many Requests`.
3. **Audit Log Tamper Detection**:
   - Verified via `tests/test_audit.py::test_audit_log_tamper_detection` and `scripts/verify_audit.py`.
   - Modifying a single character in `data/audit_log.jsonl` immediately halts verification with exit code 1.
4. **Three Real-World Scenarios**:
   - Genuine Flipkart Order $\rightarrow$ `MATCHES_OFFICIAL` (Risk `0.03`).
   - Unauthorized Mobile Impersonation $\rightarrow$ `SUSPICIOUS` (Risk `0.55`).
   - Obvious Scam (AnyDesk + OTP + Personal UPI + Lookalike Domain) $\rightarrow$ `LIKELY_SCAM` (Risk `0.85`).
5. **Test Suite Status**:
   - **115 / 115 tests passing** across all 11 test modules.
   - `ruff check .` passes with **0 errors**.
