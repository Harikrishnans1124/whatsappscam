# Phase 6 Implementation Summary: Evaluation, Tests, and Latency Profiling

## 1. Overview
Phase 6 delivered quantitative, reproducible evaluation on a 125-case benchmark dataset partitioned into tuning and held-out splits, validated 0 unsafe passes, completed the pytest test suite to 136 tests, and profiled latency across cached, uncached, and degraded execution scenarios.

---

## 2. Evaluation Dataset (`eval/cases.jsonl`)
A 125-case benchmark dataset was generated using `scripts/generate_eval_cases.py` across 6 diverse categories:
- **`genuine_official` (27 cases):** Official contacts matching verified brand registry records for 11 brands (Flipkart, Amazon India, Myntra, Tata CLiQ, AJIO, Meesho, Nykaa, Apple India, Acme Footwear, Zomato, Swiggy).
- **`genuine_small_shop` (24 cases):** Legitimate small businesses and local sellers (e.g. spice merchants, bakeries, handicrafts, tailors) with personal mobile numbers and UPI handles, but zero impersonation claims or scam tactics.
- **`wrong_number_impersonation` (16 cases):** Fraudulent sellers claiming to represent trusted brands while operating from personal, unauthorized mobile numbers.
- **`lookalike_domain` (24 cases):** Phishing websites employing typosquatting, brand stuffing (e.g. `flipkart-festivesale.shop`), and unauthorized TLDs.
- **`personal_payee` (14 cases):** Claims of official corporate orders demanding payment to individual, personal UPI accounts.
- **`message_only_scam` (20 cases):** Social engineering messages demanding OTPs, screen sharing / AnyDesk installation, fake lottery winnings, and urgent advance payments.

Split:
- **Tuning Subset:** 63 cases
- **Held-Out Subset:** 62 cases

---

## 3. Quantitative Evaluation Results

| Metric | Tuning Subset (N=63) | Held-Out Subset (N=62) | Target | Status |
|---|---|---|---|---|
| **Scam Recall** | **100.00%** (37/37) | **100.00%** (37/37) | >= 95% | **EXCEEDED** |
| **False-Alarm Rate** | **3.85%** (1/26) | **4.00%** (1/25) | <= 10% | **EXCEEDED** |
| **Unsafe Passes** | **0** | **0** | **0** | **MET (PERFECT)** |
| **Verdict Exact Accuracy** | **82.54%** (52/63) | **95.16%** (59/62) | >= 80% | **EXCEEDED** |

### Held-Out Category Breakdown
- `genuine_official`: 92.3% exact match (12/13)
- `genuine_small_shop`: **100.0% exact match (12/12) — 0 false alarms on genuine small businesses**
- `wrong_number_impersonation`: 100.0% exact match (8/8)
- `lookalike_domain`: 83.3% exact match (10/12)
- `personal_payee`: 100.0% exact match (7/7)
- `message_only_scam`: 100.0% exact match (10/10)

### Held-Out 4x4 Confusion Matrix
```
Expected \ Actual    MATCHES_OFFICIAL   UNVERIFIED   SUSPICIOUS   LIKELY_SCAM
-------------------------------------------------------------------------
MATCHES_OFFICIAL            12               0            0             1
UNVERIFIED                   0              12            0             0
SUSPICIOUS                   0               0            5             0
LIKELY_SCAM                  0               0            2            30
```

---

## 4. Latency Profiling Results
Benchmarked on Windows 11 with Intel Core i7 13th Gen, Python 3.13.7:

| Scenario | Iterations | p50 (ms) | p95 (ms) | Mean (ms) | Description |
|---|---|---|---|---|---|
| **All Cached** | 50 | **24.91 ms** | **34.35 ms** | 26.03 ms | Local SQLite + in-memory cache hit |
| **Uncached Domain** | 50 | **248.56 ms** | **287.37 ms** | 252.30 ms | Simulated RDAP registration resolution |
| **RDAP Timeout** | 10 | **141.42 ms** | **250.07 ms** | 140.36 ms | Circuit breaker degraded fallback |

---

## 5. Verification & Test Suite
- **Automated Pytest Suite:** 136 / 136 tests passing in 15.67s.
- **Ruff Code Quality:** 0 lint errors, strict formatting.
- **Zero Unsafe Passes:** Verified programmatically by `tests/test_eval.py` on every run.
