# PLAN.md: Build Plan for TrustShop AI

A step-by-step plan to go from an empty folder to a working, benchmarked, documented project.
Tick the boxes as you go. After each phase, update [`docs/BUILD_LOG.md`](docs/BUILD_LOG.md).

**Estimated effort:** about 3–4 weeks part-time (roughly 8–10 hours/week). Phases are independent enough to pause between them.
**Working rule:** every phase ends with something that **runs** and a **commit**. Don't start the next phase on top of broken code.

---

## Overview

| Phase | Goal | Deliverable | Est. time |
|---|---|---|---|
| 0 | Repo + environment | Skeleton repo, Docker Redis running | 0.5 day |
| 1 | Data + behavioral model | Trained model + PR curve + metrics | 4–6 days |
| 2 | API skeleton end to end | `/v1/orders/score` returns a decision using stub scorers | 3–4 days |
| 3 | Real scorers + decision layer | Merchant, catalog, behavioral scorers + reason codes | 4–5 days |
| 4 | Resilience + audit + idempotency | Timeouts, breaker, hash-chained log, replay-safe API | 3–4 days |
| 5 | Observability + review queue | Jaeger traces, `/v1/holds`, Streamlit dashboard | 2–3 days |
| 6 | Tests + load test + Docker | pytest suite, k6 results, one-command run | 3–4 days |
| 7 | Docs + polish | README metrics filled, demo GIF, resume bullets | 1–2 days |

---

## Phase 0: Repo and environment

**Goal:** a clean starting point.

- [ ] Create GitHub repo `trustshop-ai` (add MIT license, Python `.gitignore`)
- [ ] Create the folder structure from the README (`app/`, `training/`, `tests/`, `docs/`, `config/`, `loadtest/`, `scripts/`, `dashboard/`, `models/`, `data/`)
- [ ] Create virtualenv, add `requirements.txt` / `requirements-dev.txt` (see `docs/DEVELOPMENT.md`)
- [ ] Add `docker-compose.yml` with **Redis only** for now
- [ ] Add `config/thresholds.yaml`
- [ ] Copy the docs from this folder into `docs/`
- [ ] First commit: `chore: project skeleton`

**Done when:** `docker compose up redis -d` works and `redis-cli ping` returns `PONG`.

---

## Phase 1: Data and behavioral model

**Goal:** a trained fraud model with honest evaluation.

**Learn first (1–2 hours):** LightGBM basics, PR curves, class imbalance (see `docs/TECH_STACK.md` §4).

- [ ] Get a Kaggle token; download IEEE-CIS into `data/`
- [ ] Explore: class balance, missing values, column meanings (notebook `training/eda.ipynb`)
- [ ] **Decide the serving feature set.** Choose only features you can compute from the API request + Redis (amount, product/category, card network/type, email domain, device type, hour of day, velocity counts). Write this list down in `training/features.py`.
- [ ] Implement `features.py` (one function used for both training and serving)
- [ ] Time-based split (train on the earlier period, validate on the later period)
- [ ] Train LightGBM baseline with `scale_pos_weight`
- [ ] Evaluate: PR-AUC, recall at 90% precision, PR curve plot
- [ ] Pick provisional thresholds using a cost assumption (write the assumption in BUILD_LOG)
- [ ] Save `models/behavioral.joblib`
- [ ] Commit notebook + `features.py`: `feat: behavioral model training`

**Done when:** you have a saved model and a PR-AUC number you can explain, and you can state what is *not* in the model (e.g. clickstream).

**Watch out for:**
- Random split leaking future information (use time-based).
- Using features at training time that you can't get at request time (training/serving skew).
- Reporting accuracy (meaningless with ~3.5% fraud).

---

## Phase 2: API skeleton, end to end with stubs

**Goal:** the full request path works before any smart logic exists.

**Learn first:** FastAPI tutorial, Pydantic models, `redis.asyncio` (TECH_STACK §1–3).

- [ ] `schemas.py`: request and response Pydantic models (match `docs/API.md`)
- [ ] `main.py`: `POST /v1/orders/score`, `/healthz`, `/readyz`
- [ ] `config.py`: load `thresholds.yaml` and env vars
- [ ] `enrichment.py`: Redis velocity counters (device 10 min, account 1 h, distinct IPs 24 h)
- [ ] Stub scorers in `agents/` returning fixed scores
- [ ] `decision.py`: weighted score, thresholds, veto, degraded rule, reason codes
- [ ] `errors.py`: RFC 9457 handlers (422, 400, 409)
- [ ] Add `Dockerfile` and put `api` into `docker-compose.yml`
- [ ] Commit: `feat: api skeleton with stub scorers`

**Done when:** the curl example returns a valid response and different stub values produce `APPROVE`, `STEP_UP`, and `HOLD`.

---

## Phase 3: Real scorers and decision layer

**Goal:** replace stubs with real logic.

### 3a. Merchant scorer
- [ ] Implement rules (domain age, rating, refund rate) with reason codes
- [ ] Unit tests for each rule and boundary

### 3b. Behavioral scorer
- [ ] Load model at startup (not per request)
- [ ] Build feature vector via `features.py` + Redis velocity values
- [ ] Return `1 - fraud_probability` + reasons
- [ ] Add heuristic adjustment for `checkout_seconds` / `clicks_last_minute`
- [ ] Run inference in a thread (`asyncio.to_thread`)

### 3c. Catalog authenticity scorer
- [ ] Hand-write ~100–300 counterfeit-style listing texts in `training/counterfeit_examples.csv` (and ~100 clearly normal ones for sanity checks)
- [ ] `build_catalog_index.py`: embed with MiniLM, build FAISS index
- [ ] Scorer: embed item text, nearest-neighbor similarity, price-plausibility rule
- [ ] Sanity test: counterfeit-looking listings score low, normal listings score high
- [ ] Measure embedding latency (write it in BUILD_LOG)

### 3d. Decision layer refinements
- [ ] Weight redistribution when a scorer is `None`
- [ ] Reason code ranking (top 3)
- [ ] Commit: `feat: real scorers`

**Done when:** three hand-made example orders (clean, suspicious, very suspicious) get sensible decisions and reasons.

---

## Phase 4: Resilience, idempotency, audit

**Goal:** the "production-minded" features.

**Learn first:** circuit breaker pattern, idempotency keys, hash chains (TECH_STACK §6–7).

- [ ] `breaker.py`: `asyncio.wait_for` (80 ms) + circuit breaker per scorer (pybreaker or your own small class)
- [ ] Run the three scorers with `asyncio.gather`
- [ ] Add an env flag to artificially slow a scorer (for testing)
- [ ] Verify: slow scorer → response is `200`, `degraded: true`, decision is not `APPROVE`
- [ ] `idempotency.py`: Redis `SET NX EX`, replay returns stored response, conflict returns `409`
- [ ] `audit.py`: hash-chained append, single-writer safety (lock)
- [ ] `scripts/verify_audit.py`: verifies the chain, reports the first broken link
- [ ] Hash or truncate IP/fingerprint in the audit entry
- [ ] Commit: `feat: resilience, idempotency, audit chain`

**Done when:** you can (1) kill Redis and still get a degraded answer, (2) slow a scorer and see fallback, (3) tamper with the audit file and see the verifier fail.

---

## Phase 5: Observability and review queue

**Goal:** see what's happening; give humans something to act on.

- [ ] `telemetry.py`: OpenTelemetry setup, FastAPI auto-instrumentation
- [ ] Manual spans for `enrich`, each scorer, `decision`
- [ ] Add Jaeger to `docker-compose.yml`; confirm traces in the UI at `:16686`
- [ ] Store held orders (Redis list/hash or SQLite) → `GET /v1/holds`
- [ ] `POST /v1/holds/{order_id}/resolve` (`confirmed_fraud` / `legitimate`)
- [ ] `dashboard/review_queue.py` (Streamlit): table plus resolve buttons
- [ ] Screenshot a Jaeger trace and the dashboard for the README
- [ ] Commit: `feat: tracing and review queue`

**Done when:** one request shows a trace with parallel scorer spans, and a held order can be resolved from the dashboard.

---

## Phase 6: Tests, load test, one-command run

**Goal:** prove it works and measure it.

**Learn first:** pytest, httpx testing, k6 (TECH_STACK §10–11).

- [ ] Unit tests: decision thresholds/veto/degraded, merchant rules, weight redistribution
- [ ] Integration tests: score endpoint, validation errors (problem+json), idempotency replay/conflict
- [ ] Failure tests: scorer timeout, breaker open/recover, Redis down
- [ ] Audit tests: valid chain passes, tampered chain fails
- [ ] `loadtest/score.js` (k6) with realistic randomized payloads
- [ ] Run load test; record req/s, p50, p99, error rate, machine specs
- [ ] Run slow-scorer load test; record degraded rate
- [ ] Optimize if needed (thread offloading, workers, model warm-up, caching), re-measure, note before/after in BUILD_LOG
- [ ] Verify `docker compose up --build` from a clean clone works
- [ ] Commit: `test: suite and load test results`

**Done when:** `pytest` is green, k6 numbers are recorded, and a fresh clone runs with one command.

---

## Phase 7: Documentation and polish

**Goal:** make it look and read like a real project.

- [ ] Fill in the README "Performance and evaluation" tables with **measured** values
- [ ] Update README feature checklist and roadmap to match reality (remove anything you didn't build)
- [ ] Add architecture diagram image (export from the ASCII, or draw in draw.io/Excalidraw)
- [ ] Record a 60-second demo GIF (curl → response → Jaeger trace → dashboard)
- [ ] Complete `docs/BUILD_LOG.md` (summary snapshot, decisions, interview cheat sheet)
- [ ] Add badges (tests passing via GitHub Actions is a nice touch)
- [ ] Add GitHub Actions workflow: `ruff` + `pytest` on push
- [ ] Write resume bullets from real numbers; pin the repo on your GitHub profile
- [ ] Tag release `v0.1.0`

**Done when:** a stranger can clone, run, and understand the project from the README alone.

---

## Stretch goals (only after everything above)

- [ ] Logistic-regression stacker replacing fixed weights (calibrated)
- [ ] Sliding-window velocity counters (Redis sorted sets)
- [ ] CLIP image embeddings for catalog images
- [ ] Feedback loop: reviewer labels → retrain script
- [ ] Drift monitoring (population stability index on key features)
- [ ] LLM-written explanation for held orders (off the hot path)
- [ ] Deploy to a cloud VM or Fly.io/Render with a public demo URL

---

## Risks and how to handle them

| Risk | Mitigation |
|---|---|
| Scope creep | Finish phases in order; stretch goals are optional |
| Latency target missed | Profile with Jaeger; offload inference to threads; add workers; report the honest number |
| Catalog dataset is weak | Be upfront in docs that it's a small curated set; the technique is what's demonstrated |
| Training/serving skew | Single shared `features.py`; add a test comparing feature output for a sample row |
| Async + breaker library friction | Write your own ~30-line breaker; it's simple and a good interview story |
| Motivation dips | Keep phases small, commit often, update BUILD_LOG each session |

---

## Weekly rhythm (suggested)

| Week | Focus |
|---|---|
| 1 | Phase 0 + Phase 1 (model) |
| 2 | Phase 2 + Phase 3 (API + scorers) |
| 3 | Phase 4 + Phase 5 (resilience, audit, tracing, dashboard) |
| 4 | Phase 6 + Phase 7 (tests, load test, docs, polish) |

Adjust around your exams and placement prep; the plan works fine paused between phases.

---

## Definition of "finished v0.1"

- [ ] `docker compose up --build` starts API, Redis, Jaeger
- [ ] Scoring endpoint returns decision + reason codes + degraded flag
- [ ] Behavioral model metrics documented (PR-AUC, recall@precision)
- [ ] Timeouts + breaker verified by test
- [ ] Idempotency verified by test
- [ ] Audit chain verified, tamper detected
- [ ] Traces visible in Jaeger
- [ ] k6 results recorded with machine specs
- [ ] README metrics are real numbers, no `TBD`
- [ ] BUILD_LOG is complete
