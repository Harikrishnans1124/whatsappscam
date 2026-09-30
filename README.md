# TrustShop AI

> A real-time e-commerce risk scoring service. Send it an order, and in well under a second it tells you whether to **approve** it, ask the customer for **extra verification**, or **hold** it for human review, and tells you *why*.

![status](https://img.shields.io/badge/status-in%20development-orange)
![python](https://img.shields.io/badge/python-3.11+-blue)
![license](https://img.shields.io/badge/license-MIT-green)

---

## Table of contents

1. [What problem does this solve?](#what-problem-does-this-solve)
2. [How it works (30-second version)](#how-it-works-30-second-version)
3. [Features](#features)
4. [Tech stack](#tech-stack)
5. [Quick start](#quick-start)
6. [Using the API](#using-the-api)
7. [Project structure](#project-structure)
8. [Documentation index](#documentation-index)
9. [Performance and evaluation](#performance-and-evaluation)
10. [Design decisions and known limitations](#design-decisions-and-known-limitations)
11. [Roadmap](#roadmap)
12. [License](#license)

---

## What problem does this solve?

Online shops lose money in two opposite ways:

- **Missed fraud**: a stolen card or a counterfeit-selling merchant slips through and the shop eats the chargeback.
- **False declines**: a genuine customer gets blocked and never comes back.

TrustShop AI sits between checkout and the payment gateway. For every order it combines three independent signals into one **trust score** and picks an action:

| Trust score | Action | Meaning |
|---|---|---|
| `>= 0.88` | `APPROVE` | Looks safe. Let the payment go through. |
| `0.50 – 0.87` | `STEP_UP` | Unsure. Ask for 2FA / extra verification. |
| `< 0.50` | `HOLD` | Looks risky. Block and push to a review queue. |

(Thresholds are configurable, see [`config/thresholds.yaml`](config/thresholds.yaml).)

---

## How it works (30-second version)

```
 POST /v1/orders/score
          │
          ▼
 ┌─────────────────────────┐
 │ Validate + idempotency  │  Pydantic, Idempotency-Key header
 └───────────┬─────────────┘
             ▼
 ┌─────────────────────────┐
 │ Enrich from Redis       │  velocity counters, account history
 └───────────┬─────────────┘
             ▼      (run in parallel, each with a timeout)
 ┌───────────┬─────────────┬───────────────┐
 │ Merchant  │ Catalog     │ Behavioral    │
 │ scorer    │ authenticity│ fraud scorer  │
 │ (rules)   │ (embeddings)│ (LightGBM)    │
 └─────┬─────┴──────┬──────┴───────┬───────┘
       └────────────┼──────────────┘
                    ▼
        ┌────────────────────────┐
        │ Decision layer         │  weighted score + veto rules
        │ → decision + reasons   │
        └───────────┬────────────┘
                    ▼
     APPROVE / STEP_UP / HOLD  +  tamper-evident audit log
```

If a scorer is slow or broken, a **circuit breaker** trips and the system falls back to the safe option (`STEP_UP`) instead of failing open or crashing. Full details are in [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

---

## Features

- Parallel scoring by three independent scorers (merchant, catalog, behavioral)
- Explainable output: every decision carries `reason_codes`
- Per-scorer timeouts plus a circuit breaker with a safe fallback
- Idempotent API: retrying the same request never double-processes an order
- Hash-chained audit log (tamper-evident) with a verify script
- Distributed tracing with OpenTelemetry (view in Jaeger)
- RFC 9457 `application/problem+json` error responses
- Review-queue endpoint and a small Streamlit dashboard for held orders
- Reproducible model training and evaluation notebook
- Load-test scripts (k6) with recorded results

> Check the boxes in [`PLAN.md`](PLAN.md) to see which of these are done.

---

## Tech stack

| Layer | Technology |
|---|---|
| API | Python 3.11, FastAPI, Pydantic v2, Uvicorn |
| Feature store / cache | Redis |
| Behavioral model | LightGBM, scikit-learn, imbalanced-learn |
| Catalog authenticity | sentence-transformers (MiniLM), FAISS |
| Resilience | asyncio timeouts, pybreaker (circuit breaker) |
| Observability | OpenTelemetry, Jaeger |
| Testing | pytest, k6 (load testing) |
| Dashboard | Streamlit |
| Packaging | Docker, Docker Compose |
| Data | Kaggle IEEE-CIS Fraud Detection (plus a small hand-built counterfeit set) |

Why each was chosen, where it's used, and where to learn it: [`docs/TECH_STACK.md`](docs/TECH_STACK.md).

---

## Quick start

**Prerequisites:** Docker + Docker Compose, Python 3.11+ (only needed for training).

```bash
# 1. Clone
git clone https://github.com/<your-username>/trustshop-ai.git
cd trustshop-ai

# 2. Start everything (API + Redis + Jaeger)
docker compose up --build

# 3. Check it's alive
curl http://localhost:8000/healthz
```

Open:
- API docs (Swagger): http://localhost:8000/docs
- Jaeger traces: http://localhost:16686

To train the model yourself and run tests/load tests, see [`docs/DEVELOPMENT.md`](docs/DEVELOPMENT.md).

---

## Using the API

Score an order:

```bash
curl -X POST http://localhost:8000/v1/orders/score \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: order-1001-attempt-1" \
  -d '{
    "order_id": "1001",
    "amount": 129.99,
    "currency": "USD",
    "customer": { "account_id": "acc_42", "account_age_days": 3, "email_domain": "gmail.com" },
    "device":   { "fingerprint": "fp_abc123", "ip": "203.0.113.7", "type": "mobile" },
    "merchant": { "merchant_id": "m_9", "domain": "cheap-brands-outlet.shop", "domain_age_days": 12, "rating": 2.9, "refund_rate": 0.21 },
    "items": [ { "sku": "S1", "title": "Original Nike Air Max 1:1 quality", "price": 19.99 } ],
    "session": { "clicks_last_minute": 42, "checkout_seconds": 6 }
  }'
```

Example response:

```json
{
  "order_id": "1001",
  "decision": "HOLD",
  "trust_score": 0.31,
  "scores": { "merchant": 0.22, "catalog": 0.18, "behavioral": 0.47 },
  "reason_codes": ["NEW_MERCHANT_DOMAIN", "COUNTERFEIT_LISTING_SIMILARITY", "FAST_CHECKOUT"],
  "degraded": false,
  "latency_ms": 41.7,
  "audit_id": "a_01HXYZ..."
}
```

Full request/response schemas, error formats, and all endpoints: [`docs/API.md`](docs/API.md).

---

## Project structure

```
trustshop-ai/
├── app/
│   ├── main.py            # FastAPI app + routes
│   ├── schemas.py         # Pydantic request/response models
│   ├── config.py          # loads config/thresholds.yaml + env vars
│   ├── enrichment.py      # Redis feature lookups + velocity counters
│   ├── agents/
│   │   ├── merchant.py    # rule-based merchant scorer
│   │   ├── catalog.py     # embedding + FAISS authenticity scorer
│   │   └── behavioral.py  # LightGBM fraud scorer
│   ├── decision.py        # combines scores → decision + reason codes
│   ├── breaker.py         # timeouts + circuit breaker wrappers
│   ├── audit.py           # hash-chained audit log
│   ├── idempotency.py     # Idempotency-Key handling
│   ├── errors.py          # RFC 9457 problem+json handlers
│   └── telemetry.py       # OpenTelemetry setup
├── training/
│   ├── features.py        # feature engineering (shared with serving)
│   ├── train_behavioral.ipynb
│   └── build_catalog_index.py
├── models/                # trained model + FAISS index (git-ignored, see docs)
├── config/thresholds.yaml
├── dashboard/review_queue.py   # Streamlit
├── scripts/verify_audit.py
├── tests/
├── loadtest/score.js      # k6
├── docs/
├── docker-compose.yml
├── PLAN.md
└── README.md
```

---

## Documentation index

| Doc | What's in it |
|---|---|
| [`PLAN.md`](PLAN.md) | Step-by-step build plan with checkboxes |
| [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | Components, data flow, decision logic, failure handling |
| [`docs/API.md`](docs/API.md) | Endpoints, schemas, errors, examples |
| [`docs/TECH_STACK.md`](docs/TECH_STACK.md) | Every technology: why, where, how, and learning links |
| [`docs/DEVELOPMENT.md`](docs/DEVELOPMENT.md) | Setup, training, testing, load testing |
| [`docs/BUILD_LOG.md`](docs/BUILD_LOG.md) | What was actually built, in order, with results |

---

## Performance and evaluation

> Fill these in with **measured** values after Phase 4 of [`PLAN.md`](PLAN.md). Don't leave estimates here.

**Model (behavioral scorer), IEEE-CIS hold-out set**

| Metric | Value |
|---|---|
| PR-AUC | _TBD_ |
| Recall @ 90% precision | _TBD_ |
| Chosen approve threshold / step-up threshold | _TBD_ |

**Service (k6 load test, machine: _TBD_)**

| Metric | Value |
|---|---|
| Requests/sec sustained | _TBD_ |
| p50 latency | _TBD_ |
| p99 latency | _TBD_ |
| Error rate | _TBD_ |
| Degraded-mode rate (a scorer timed out) | _TBD_ |

Design target: **p99 < 120 ms**. This is a goal to verify, not a claim.

---

## Design decisions and known limitations

- **"Agents" are scorers, not LLM agents.** A 120 ms budget rules out live LLM calls. Each scorer is a fast rule set or ML model. An optional LLM explanation for held orders is a possible future add-on (off the hot path).
- **Training/serving parity.** The behavioral model only uses features that can be computed identically at request time (see `training/features.py`).
- **Catalog data is small and partly synthetic.** No public labeled "counterfeit listing" dataset fits this exactly, so the index is hand-curated. Treat catalog scores as a demonstration of the technique.
- **Single-node design.** Horizontal scaling (multiple Uvicorn workers or replicas behind a load balancer) is supported by the stateless API, but is not deployed here.
- **Not production fraud software.** It is a learning and portfolio project. Don't use it to make real financial decisions without proper validation, monitoring, and compliance review.

---

## Roadmap

- [ ] Image-based counterfeit detection (CLIP embeddings)
- [ ] Learned decision layer (logistic-regression stacker) replacing fixed weights
- [ ] Feedback loop: reviewer labels from the dashboard feed retraining
- [ ] Drift monitoring for the behavioral model
- [ ] Optional LLM explanation for held orders

---

## License

MIT. See `LICENSE`.
