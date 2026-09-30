# Architecture

This document explains **how TrustShop AI is put together and why**. If you're re-reading this after a break, start with [1. The one-paragraph version](#1-the-one-paragraph-version) and [4. Decision logic](#4-decision-logic).

---

## 1. The one-paragraph version

A client sends an order to `POST /v1/orders/score`. The API validates it, checks the idempotency key, and pulls extra context from Redis (velocity counters, account history). Three scorers then run **in parallel**, each with its own timeout: a rule-based **merchant scorer**, an embedding-based **catalog authenticity scorer**, and a LightGBM **behavioral fraud scorer**. The **decision layer** combines their scores into one `trust_score`, applies veto rules, and returns `APPROVE`, `STEP_UP`, or `HOLD` with `reason_codes`. Every decision is written to a **hash-chained audit log** and traced with **OpenTelemetry**.

---

## 2. Component diagram

```
                 ┌──────────────────────────────────────────┐
  Client ───────▶│ FastAPI  (app/main.py)                   │
 (checkout)      │  • Pydantic validation (schemas.py)      │
                 │  • Idempotency check (idempotency.py)    │
                 └───────────────┬──────────────────────────┘
                                 │
                                 ▼
                 ┌──────────────────────────────────────────┐
                 │ Enrichment (enrichment.py)               │◀───▶ Redis
                 │  • velocity counters (INCR + EXPIRE)     │
                 │  • account history                       │
                 └───────────────┬──────────────────────────┘
                                 │  asyncio.gather (parallel)
        ┌────────────────────────┼─────────────────────────┐
        ▼                        ▼                         ▼
 ┌──────────────┐        ┌───────────────┐         ┌───────────────┐
 │ Merchant     │        │ Catalog       │         │ Behavioral    │
 │ scorer       │        │ scorer        │         │ scorer        │
 │ rules        │        │ MiniLM + FAISS│         │ LightGBM      │
 └──────┬───────┘        └───────┬───────┘         └───────┬───────┘
        │   each wrapped by breaker.py (timeout + circuit breaker)
        └────────────────────────┼─────────────────────────┘
                                 ▼
                 ┌──────────────────────────────────────────┐
                 │ Decision layer (decision.py)             │
                 │  weighted trust score + veto + degraded  │
                 └───────────────┬──────────────────────────┘
                                 │
              ┌──────────────────┼──────────────────┐
              ▼                  ▼                  ▼
        Audit log (audit.py)  OTel spans        Response
        hash-chained          (telemetry.py)    + Redis idempotency store
```

---

## 3. Components in detail

### 3.1 API layer (`app/main.py`, `schemas.py`, `errors.py`)
- **Validation:** Pydantic v2 models reject bad payloads with `422`-style problems.
- **Errors:** all errors are returned as `application/problem+json` following [RFC 9457](https://www.rfc-editor.org/rfc/rfc9457).
  - *Note:* the original design doc said "RFC-7807 JSON schema validation". RFC 7807 (obsoleted by 9457) defines the **error response format**, not payload validation. Validation is done by Pydantic / JSON Schema; RFC 9457 is used for error output.
- **Idempotency:** the `Idempotency-Key` header maps to a stored response in Redis (TTL 24 h). A retry with the same key and same body returns the stored response. Same key with a different body returns `409`.

### 3.2 Enrichment (`app/enrichment.py`)
Fetches or updates features from Redis **before** scoring:

| Feature | Redis pattern | Notes |
|---|---|---|
| Orders per device in last 10 min | `vel:dev:{fingerprint}:10m` (INCR, EXPIRE 600) | fixed-window counter |
| Orders per account in last 1 h | `vel:acc:{account_id}:1h` | fixed-window counter |
| Distinct IPs per account in 24 h | `ips:acc:{account_id}` (SET, EXPIRE 86400) | `SADD` then `SCARD` |
| Account history | `acc:{account_id}` (HASH) | order count, chargebacks |

Fixed-window counters are simple and fast. A sliding window (sorted sets) is more accurate and is listed as a future improvement.

### 3.3 Scorers (`app/agents/`)

All scorers return the same shape:

```python
{"score": float in [0,1], "reasons": list[str]}   # 1.0 = very trustworthy, 0.0 = very risky
```

**Merchant scorer (`merchant.py`), rule-based.**
Inputs: domain age, seller rating, refund rate.
Example logic (tune the numbers with your data):

```
score = 1.0
if domain_age_days < 30:   score -= 0.35; reasons += NEW_MERCHANT_DOMAIN
elif domain_age_days < 180: score -= 0.15
if rating < 3.5:           score -= 0.25; reasons += LOW_MERCHANT_RATING
if refund_rate > 0.15:     score -= 0.25; reasons += HIGH_REFUND_RATE
score = clamp(score, 0, 1)
```

**Catalog authenticity scorer (`catalog.py`), embeddings + FAISS.**
1. At build time (`training/build_catalog_index.py`): embed a hand-curated set of counterfeit-style listings (phrases like "1:1 mirror quality", "AAA replica", "not original but same quality") with `all-MiniLM-L6-v2` and store them in a FAISS index.
2. At request time: embed each item's `title + description`, find the nearest counterfeit exemplar, and compute `similarity`.
3. `score = 1 - max_similarity_over_items`, then apply a **price-plausibility** rule (a well-known brand priced far below a category floor lowers the score).
4. Embeddings for the counterfeit set are **precomputed**; only the incoming text is embedded live (~10–30 ms on CPU for short text; measure it).

**Behavioral fraud scorer (`behavioral.py`), LightGBM + heuristics.**
- The model outputs `fraud_probability`; `model_trust = 1 - fraud_probability`.
- Features come from `training/features.py`, **the same function is used in training and serving** (training/serving parity).
- Clickstream fields with no equivalent in the public training data (`clicks_last_minute`, `checkout_seconds`) feed a small **heuristic adjustment** (e.g. checkout in under 8 s with high click velocity subtracts from the score) rather than the model.

### 3.4 Timeouts and circuit breaker (`app/breaker.py`)
Each scorer call is wrapped with:
1. `asyncio.wait_for(scorer(...), timeout=0.080)` (80 ms).
2. A `pybreaker` circuit breaker per scorer (e.g. `fail_max=5`, `reset_timeout=30`).

If a scorer times out, raises, or its breaker is open, it returns `None` and the response is marked `degraded: true`.

> **Latency budget:** because scorers run in parallel, worst-case scoring time ≈ max(scorer times), not the sum. That's what makes an 80 ms per-scorer timeout compatible with a 120 ms end-to-end target.

### 3.5 Decision layer (`app/decision.py`), see next section.

### 3.6 Audit log (`app/audit.py`)
Append-only log where each entry contains the hash of the previous entry:

```
entry_hash = SHA-256( prev_hash || canonical_json(entry_payload) )
```

Editing or deleting any past entry breaks every hash after it. `scripts/verify_audit.py` re-computes the chain and reports the first broken link.

- This is **tamper-evident**, not tamper-proof. For real immutability, store the log in WORM storage (for example S3 Object Lock) and anchor the latest hash externally.
- Do not log raw PII. Store hashes or truncated values for IP and fingerprint.

### 3.7 Observability (`app/telemetry.py`)
OpenTelemetry spans: `score_request` (root) → `enrich`, `agent.merchant`, `agent.catalog`, `agent.behavioral`, `decision`. Exported over OTLP to Jaeger. Span attributes include `decision`, `trust_score`, `degraded`. Avoid putting PII in span attributes.

---

## 4. Decision logic

Trust score: **1.0 = safe, 0.0 = very risky**. (The original doc called this "confidence"; renamed to avoid the ambiguity of "confidence in what?".)

### Step 1: combine
Default weights (in `config/thresholds.yaml`):

```
trust = 0.50 * behavioral + 0.25 * merchant + 0.25 * catalog
```

If a scorer is missing (timeout/breaker), its weight is redistributed proportionally across the remaining scorers and `degraded = true`.

### Step 2: veto rules
- If **any** scorer returns `< 0.20`, decision is `HOLD` regardless of the weighted average (one strongly bad signal shouldn't be averaged away).

### Step 3: map to an action

| Condition | Decision |
|---|---|
| veto triggered | `HOLD` |
| `trust >= 0.88` and not degraded | `APPROVE` |
| `trust >= 0.88` and **degraded** | `STEP_UP` (never auto-approve on partial information) |
| `0.50 <= trust < 0.88` | `STEP_UP` |
| `trust < 0.50` | `HOLD` |

### Step 4: reason codes
Collect reasons from each scorer plus decision-level codes such as `DEGRADED_MODE` and `VETO_LOW_SCORE`. Return the top few by contribution.

### Tuning the thresholds
Do **not** treat 0.88 / 0.50 as magic numbers. Choose them on a validation set:
1. Plot the precision-recall curve for `1 - trust`.
2. Estimate business cost: `cost_missed_fraud` vs `cost_false_decline`.
3. Pick thresholds that minimize expected cost (or hit a target precision).
4. Record the chosen values and the reasoning in `docs/BUILD_LOG.md`.

### Future: learned combiner
Replace the fixed weights with a logistic-regression stacker trained on the three scorers' outputs (and calibrated, e.g. with isotonic regression). Keep the veto rules.

---

## 5. Failure modes and how they're handled

| Failure | Behavior |
|---|---|
| Invalid payload | `422` problem+json, nothing scored |
| Duplicate request (same idempotency key + body) | Stored response returned, no re-scoring |
| Same key, different body | `409` problem+json |
| One scorer times out / errors | Marked degraded; weights redistributed; can't `APPROVE` |
| Scorer breaker open | Scorer skipped immediately (fast-fail), degraded mode |
| All scorers fail | `STEP_UP` with `DEGRADED_MODE`, `trust_score: null` |
| Redis down | Enrichment features default to neutral values, degraded mode, request still answered |
| Audit write fails | Request still answered; error is logged and alerted (decision: availability over audit completeness; revisit for regulated use) |

---

## 6. Data and models

| Asset | Source | Where it lives |
|---|---|---|
| Behavioral training data | [Kaggle IEEE-CIS Fraud Detection](https://www.kaggle.com/c/ieee-fraud-detection) | `data/` (git-ignored) |
| Behavioral model | trained in `training/train_behavioral.ipynb` | `models/behavioral.joblib` |
| Counterfeit exemplars | hand-curated (`training/counterfeit_examples.csv`) | committed (small) |
| FAISS index | built by `build_catalog_index.py` | `models/catalog.faiss` |

**Class imbalance:** fraud is rare (~3.5% in IEEE-CIS). Use LightGBM `scale_pos_weight` or class weights, evaluate with **PR-AUC and recall at fixed precision**, not accuracy. Split by **time**, not randomly, to avoid leakage.

**Training/serving parity:** any feature used by the model must be computable from the API request plus Redis at serving time. Velocity features in training are computed from timestamps with the same window definitions as the Redis counters.

---

## 7. Security and privacy notes

- IP address and device fingerprint are personal data in many jurisdictions; store hashed/truncated where possible and set retention limits.
- Never log full card data. This service should never receive PANs.
- Rate-limit and authenticate the scoring endpoint in any real deployment (API key / mTLS).
- The audit log records decisions, not raw personal data.

---

## 8. What changed from the original PIPELINE.md

| Original | Now | Why |
|---|---|---|
| "Multi-agent" | Three scorers | They are rules/ML models, not LLM agents |
| "Confidence" | `trust_score` (1 = safe) | Unambiguous direction |
| RFC-7807 schema validation | Pydantic for validation, RFC 9457 for errors | 7807 is an error format spec |
| 25,000 req/s | Measured value, reported in README | Unverified claim replaced by a benchmark |
| "Consensus" (undefined) | Weighted score + veto rules | Explicit, testable logic |
| Immutable logs | Hash-chained, tamper-evident log | Accurate claim; WORM storage noted for real immutability |
| Circuit breaker → step-up | Same, plus "never auto-approve when degraded" | Safer failure behavior |
