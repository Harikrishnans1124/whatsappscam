# Build Log

**Purpose:** a running record of what was actually built, what tech was used, what results were measured, and what was learned. Update it at the end of every work session. When you come back to this project after weeks away (or prepare for an interview), read this file first.

> Rule: only write things that are **true and measured**. If you didn't run it, mark it `not done`.

---

## Summary snapshot (keep this current)

| Item | Status | Notes |
|---|---|---|
| Behavioral model trained | ☐ | PR-AUC: ___ |
| API skeleton (`/v1/orders/score`) | ☐ | |
| Redis enrichment | ☐ | |
| Merchant scorer | ☐ | |
| Catalog scorer (MiniLM + FAISS) | ☐ | |
| Decision layer + reason codes | ☐ | |
| Timeouts + circuit breaker | ☐ | |
| Idempotency | ☐ | |
| Audit log + verify script | ☐ | |
| OpenTelemetry + Jaeger | ☐ | |
| Review queue + dashboard | ☐ | |
| Tests (count / coverage) | ☐ | |
| Load test results | ☐ | |
| Docker Compose deployment | ☐ | |
| README metrics filled in | ☐ | |

**Technologies actually used so far:** _(list them; e.g. FastAPI, Redis, LightGBM…)_

---

## Key results (fill with measured numbers)

**Model**

| Metric | Value | Date |
|---|---|---|
| Dataset / split | IEEE-CIS, time-based split at ___ | |
| PR-AUC | | |
| Recall @ 90% precision | | |
| Thresholds chosen (approve / step-up) | | |
| Reason thresholds were chosen | _(cost assumptions, curve)_ | |

**Service performance**

| Metric | Value | Conditions (machine, workers, load) |
|---|---|---|
| Sustained req/s | | |
| p50 latency | | |
| p99 latency | | |
| Error rate | | |
| Degraded rate under slow-scorer test | | |

---

## Session entries

Copy this block for each work session.

### YYYY-MM-DD: short title

- **Goal:**
- **What I built / changed:**
- **Files touched:**
- **Tech / concepts used:** _(and the link or doc I learned it from)_
- **How to reproduce / run it:**
- **Result / evidence:** _(metric, screenshot, trace link, test output)_
- **Problems hit and how I fixed them:**
- **What I learned (in my own words):**
- **Next step:**

---

## Decisions log

Record every non-obvious decision so future-you understands *why*.

| Date | Decision | Alternatives considered | Reason |
|---|---|---|---|
| | Time-based train/validation split | Random split | Avoid leakage; mimics production |
| | `trust_score` where 1 = safe | "confidence" | Unambiguous direction |
| | Scorers instead of LLM agents | LLM agents | 120 ms latency budget |
| | | | |

---

## Problems and fixes (troubleshooting diary)

| Symptom | Cause | Fix |
|---|---|---|
| | | |

---

## Interview cheat sheet (fill in as you go)

Be able to answer each in 1–2 minutes:

1. **What does the system do and why?**
2. **Walk me through a request end to end.**
3. **How did you choose the thresholds?** _(PR curve, cost of false decline vs missed fraud)_
4. **How do you handle a scorer timing out?** _(parallel gather, per-scorer timeout, breaker, degraded mode never approves)_
5. **What is training/serving skew and how did you avoid it?** _(shared `features.py`, same window definitions as Redis)_
6. **Why time-based split?** _(no future leakage)_
7. **Why is the audit log tamper-evident but not tamper-proof?** _(hash chain vs WORM/external anchoring)_
8. **How does idempotency work and why does it matter?** _(retries after network failures must not double-process)_
9. **What would break at 10x load?** _(single-node Redis, CPU-bound inference, audit-log serialization; how you'd fix each)_
10. **What are the limitations?** _(catalog data is small/synthetic, fixed-window counters, no drift monitoring yet)_

---

## Resume bullet drafts (only use real numbers)

- Built a real-time e-commerce risk-scoring service (FastAPI, Redis, LightGBM) that runs three parallel scorers with per-scorer timeouts and a circuit-breaker fallback; achieved **PR-AUC ___** on IEEE-CIS and **p99 ___ ms at ___ req/s** in k6 load tests.
- Designed a tamper-evident hash-chained audit log, RFC 9457 error handling, and idempotent APIs; instrumented end-to-end tracing with OpenTelemetry/Jaeger.
- Implemented an embedding-based (MiniLM + FAISS) listing-authenticity scorer and an explainable decision layer returning reason codes; shipped with Docker Compose and ___ pytest tests.
