# PLAN.md: Build Plan for TrustShop AI

A phase-by-phase plan to go from an empty folder to a working, evaluated, documented scam-verification tool.
Tick the boxes as you go (`[ ]` → `[x]`). After each phase, add an entry to [`docs/BUILD_LOG.md`](docs/BUILD_LOG.md).

**Estimated effort:** about 5–6 weeks part-time (8–10 hours/week), including time to learn the tools as you go. Phases are independent enough to pause between them (exams, placement prep).
**Working rules:**
1. Every phase ends with something that **runs** and a **commit**.
2. Learn the minimum first, build the smallest version, then improve it.
3. Only write measured numbers in docs.

---

## The idea in one minute (read this first when you return)

A shopper gets a deal from a "seller" claiming to be a famous brand. They enter the seller's **number, chat, link, and payment details**. Five checks run in parallel (brand-identity registry match, payment payee match, message scam tactics, domain lookalike/age, number reputation). A decision layer returns a verdict (`MATCHES_OFFICIAL`, `UNVERIFIED`, `SUSPICIOUS`, `LIKELY_SCAM`) with plain-language reasons. The most important check is whether the contact is on the brand's **official list**. Never say "safe".

---

## Overview

| Phase | Goal | Deliverable | Est. time |
|---|---|---|---|
| 0 | Repo + environment | Skeleton repo, Docker Redis running | 0.5 day |
| 1 | Registry + extraction + brand-identity scorer | Core of the product works from a script | 5–7 days |
| 2 | API skeleton + decision layer + minimal web page | End-to-end check in the browser (some scorers stubbed) | 4–5 days |
| 3 | Remaining scorers | Payment, domain, message, number | 6–8 days |
| 4 | Resilience, caching, safety | Timeouts, breaker, rate limit, degraded logic, audit log | 3–4 days |
| 5 | Explanations, i18n, reports, admin, PWA polish | Malayalam/Hindi text, report flow, admin dashboard | 4–5 days |
| 6 | Evaluation + tests + latency | Labeled cases, metrics, pytest suite | 4–5 days |
| 7 | Docs, user testing, polish | README metrics, demo, resume bullets | 2–3 days |

---

## Phase 0: Repo and environment

**Goal:** a clean starting point.

- [x] Create GitHub repo `trustshop-ai` (MIT license, Python `.gitignore`)
- [x] Create the folder structure from the README
- [x] Create a virtualenv; add `requirements.txt` / `requirements-dev.txt` (see `docs/DEVELOPMENT.md`)
- [x] `docker-compose.yml` with **Redis only** for now
- [x] Add `config/settings.yaml`
- [x] Copy the docs from this folder into `docs/`
- [x] First commit: `chore: project skeleton`

**Done when:** `docker compose up redis -d` works and `redis-cli ping` returns `PONG`.

---

## Phase 1: Registry, extraction, and the brand-identity scorer

**Goal:** the core idea works: "does this contact belong to the brand?"

**Learn first (2–3 hours):** `phonenumbers` basics, `tldextract`, a little regex, YAML, SQLite/SQLAlchemy basics (TECH_STACK §3–5).

- [x] **Build the registry data** (this is real work; budget a full day)
  - [x] Pick about 10 commonly impersonated brands
  - [x] For each, collect official domains, published phone numbers (or none), legal names, payment policy
  - [x] Record `source URL` + `verified_on` for every entry; use only the brand's own site or app
  - [x] Save to `registry/brands.yaml`
- [x] `registry.py` + `scripts/seed_registry.py` (reject entries without source and date)
- [x] `extraction.py`:
  - [x] normalize phone numbers (E.164, valid?, type)
  - [x] extract URLs and registrable domains from text
  - [x] extract UPI-like IDs (and avoid treating emails as UPI IDs)
  - [x] detect claimed brand from user input, aliases, and domains
- [x] `agents/brand_identity.py`: outcomes `MATCH`, `MISMATCH`, `UNKNOWN_BRAND`, `NO_BRAND_CLAIM`; return the standard scorer shape (`status`, `risk`, `reasons`, `flags`, `evidence`)
- [x] A command-line script that takes a number/URL/brand and prints the scorer output
- [x] Unit tests for extraction and brand matching (include messy phone formats)
- [x] Commit: `feat: registry, extraction, brand identity scorer`

**Done when:** for your 10 brands, official contacts match, a wrong number gives `MISMATCH`, and an unknown brand gives `UNKNOWN_BRAND`.

**Watch out for:**
- Copying numbers from non-official sources (poisons the whole system).
- Treating "not found" as "scam": for a brand not in the registry the answer is "can't verify".
- Phone formats (`098765…`, `+91-98765…`, spaces, `00` prefix).

---

## Phase 2: API skeleton, decision layer, minimal web page

**Goal:** the whole path works in a browser before everything is smart.

**Learn first:** FastAPI tutorial (first sections), Pydantic validators (TECH_STACK §1–2).

- [ ] `schemas.py`: request/response models per `docs/API.md` (at-least-one-input validator)
- [ ] `main.py`: `POST /v1/checks`, `/healthz`, `/readyz`
- [ ] `config.py`: load `settings.yaml` and env vars
- [ ] Stub the other four scorers (`not_applicable` or fixed values)
- [ ] `decision.py`:
  - [ ] weighted risk over `ok` scorers (renormalize weights)
  - [ ] hard-flag floors
  - [ ] verdict rules (`MATCHES_OFFICIAL` only with a registry match, no mismatch, no degradation, fresh entry)
- [ ] `errors.py`: RFC 9457 handlers
- [ ] `frontend/index.html` + `app.js`: form (number, paste chat, link, UPI ID, payee name) and a result card (verdict in words + icon + colour, reasons, advice)
- [ ] Dockerfile; add `api` to `docker-compose.yml`
- [ ] Commit: `feat: api, decision layer, minimal web page`

**Done when:** you can type a wrong number for a registry brand in the browser and see a `SUSPICIOUS` result with a reason, and the official number gives `MATCHES_OFFICIAL`.

---

## Phase 3: Remaining scorers

**Goal:** replace the stubs with real checks.

**Learn first:** `rapidfuzz`, RDAP/`httpx`, scikit-learn text classification (TECH_STACK §5–7).

### 3a. Payment scorer
- [ ] Payee-name fuzzy match against the brand's legal names
- [ ] `PERSONAL_PAYEE` flag for known brand + non-matching personal-looking name
- [ ] Weak signal for phone-number-style UPI IDs (never decisive)
- [ ] Tests, including company-name variations (`Pvt Ltd` vs `Private Limited`)

### 3b. Domain scorer
- [ ] Lookalike detection: typo distance, brand-stuffing, hyphen/digit tricks, Punycode/mixed-script check
- [ ] RDAP domain-age lookup with `httpx` (timeout, error handling; `None` → `failed`)
- [ ] URL shortener list
- [ ] Mock RDAP in tests (`respx`)
- [ ] Unit tests: exact official domain, typo, `brand-outlet.shop`, young domain

### 3c. Message scorer
- [ ] Rule set (urgency, advance payment, move to personal chat, OTP, remote-access apps) with tests for hits and non-hits
- [ ] Download UCI SMS Spam data; write about 100–200 of your own labeled examples
- [ ] Train TF-IDF + logistic regression; evaluate on public **and** your own data; save with `joblib`
- [ ] Load the model once at startup; predict via `asyncio.to_thread`
- [ ] Combine: rules main weight, model supporting weight

### 3d. Number scorer
- [ ] Validity/type checks (`phonenumbers`)
- [ ] `reports` table with HMAC-hashed identifiers; count distinct reporters
- [ ] `POST /v1/reports` (dedupe, minimum distinct reporters before it affects risk)

- [ ] Commit: `feat: payment, domain, message, number scorers`

**Done when:** three hand-made examples (genuine, suspicious, obvious scam) get sensible verdicts and reason codes.

---

## Phase 4: Resilience, caching, and safety

**Goal:** the production-minded features.

**Learn first:** `asyncio.gather`/`wait_for`, circuit breaker pattern, HMAC, SSRF basics (TECH_STACK §8–11).

- [ ] `breaker.py`: per-scorer timeouts (150 ms local, 2,500 ms domain) and a small circuit-breaker class you write yourself
- [ ] Run scorers with `asyncio.gather`; separate `failed` from `not_applicable`
- [ ] Verify: slow/broken RDAP → `200`, `degraded: true`, never `MATCHES_OFFICIAL`
- [ ] `cache.py`: Redis cache for RDAP (24 h TTL), fixed-window rate limiting (`429`)
- [ ] Redis down → still answers (no cache)
- [ ] `safe_fetch.py`: outbound allowlist; confirm no user URL is ever fetched
- [ ] `audit.py`: hash-chained log with HMAC-hashed identifiers only; `scripts/verify_audit.py`
- [ ] Confirm raw chat text is not stored or logged
- [ ] Commit: `feat: resilience, caching, audit`

**Done when:** you can (1) block RDAP and still get a cautious answer, (2) hit the rate limit and get `429`, (3) tamper with the audit file and see the verifier fail.

---

## Phase 5: Explanations, translations, reports, admin, PWA

**Goal:** make it usable by non-technical people.

- [ ] `explain.py` + `i18n/en.yaml`: sentence per reason code, advice per verdict
- [ ] `i18n/ml.yaml` and `i18n/hi.yaml` (get a native speaker to review the wording)
- [ ] Frontend: language selector, "where do I find the payee name?" help text, big clear verdict, "open the official site" action first, report button
- [ ] PWA: `manifest.json` + service worker (installable on a phone)
- [ ] `GET /v1/brands` and `/v1/brands/{slug}` so users can see the registry and its sources
- [ ] Admin endpoints (`X-API-Key`) and `dashboard/admin.py` (Streamlit): add/update brands, stale entries list, report queue
- [ ] `scripts/check_registry_freshness.py`
- [ ] Add OpenTelemetry + Jaeger (spans per scorer) and screenshot one trace
- [ ] Commit: `feat: explanations, i18n, reports, admin, tracing`

**Done when:** a non-technical person can use it on a phone and understand the result in their language.

---

## Phase 6: Evaluation, tests, latency

**Goal:** prove it works and know where it fails.

- [ ] Write `eval/cases.jsonl` (100–200 cases): genuine official, wrong-number impersonation, lookalike domain, personal payee, **genuine small shop not in registry**, message-only scams, mixed/missing inputs
- [ ] Split into tuning and held-out subsets
- [ ] `eval/run_eval.py`: scam recall, false-alarm rate, **unsafe passes**, accuracy, confusion matrix (external lookups mocked or replayed)
- [ ] Tune weights, floors, thresholds on the tuning subset; report held-out results
- [ ] **Unsafe passes = 0.** If not, fix the cause before moving on
- [ ] Complete the pytest suite (see `docs/DEVELOPMENT.md` §7)
- [ ] Latency: cached, uncached, RDAP-timeout scenarios (p50, p95, machine specs)
- [ ] Verify `docker compose up --build` from a clean clone
- [ ] Commit: `test: evaluation, test suite, latency results`

**Done when:** `pytest` is green, evaluation numbers are recorded honestly, and latency numbers exist for the three scenarios.

---

## Phase 7: Docs, user testing, polish

**Goal:** make it look and read like a real project, and check it works for real people.

- [ ] User test with 3–5 non-technical people: give them realistic examples, watch where they struggle, fix the top issues, log them in BUILD_LOG
- [ ] Fill in the README "Evaluation and performance" tables with measured values
- [ ] Update README features and roadmap to match reality (delete what you didn't build)
- [ ] Architecture diagram image (draw.io or Excalidraw)
- [ ] 60-second demo GIF (enter details → verdict → reasons → Jaeger trace)
- [ ] Complete `docs/BUILD_LOG.md`: snapshot, decisions, interview cheat sheet
- [ ] GitHub Actions: `ruff` + `pytest` on push
- [ ] Write resume bullets from real numbers; pin the repo on your GitHub
- [ ] Tag release `v0.1.0`

**Done when:** a stranger can clone, run, and understand the project from the README alone, and someone non-technical can use the web app.

---

## Stretch goals (only after the above)

- [ ] WhatsApp bot (forward a message, get a verdict) via WhatsApp Cloud API
- [ ] Screenshot upload + OCR to extract numbers, UPI IDs, and text
- [ ] Multilingual message understanding (Malayalam / Hindi / Manglish) with multilingual embeddings
- [ ] Google Safe Browsing lookup
- [ ] Safe page-content analysis with a proper SSRF-safe fetcher
- [ ] Browser extension
- [ ] Grow the registry to 30–50 brands with automated freshness reminders
- [ ] Public deployment with a short demo video

---

## Risks and how to handle them

| Risk | Mitigation |
|---|---|
| Wrong data in the registry | Official sources only; source URL + date required; freshness checks; admin-only writes |
| A scam marked as `MATCHES_OFFICIAL` | Registry match required; degraded can't match; track unsafe-pass metric (target 0) |
| Too many false alarms on genuine small shops | Include them in evaluation; `UNVERIFIED` (not `SUSPICIOUS`) when nothing is wrong |
| Message model doesn't transfer to WhatsApp scams | Rules carry v1; evaluate on your own data; be honest in docs |
| RDAP gaps or slowness | Cache, timeouts, `failed` status, degraded mode |
| Community report abuse | Distinct-reporter threshold, hashed identifiers, wording "reported by N users" |
| Privacy/legal exposure | Hash identifiers, no raw chats, short retention, careful wording, disclaimers |
| Scope creep | Finish phases in order; stretch goals are optional |
| Async/breaker friction | Write your own ~30-line breaker; keep it simple |
| Motivation dips | Small phases, frequent commits, BUILD_LOG each session |

---

## Weekly rhythm (suggested)

| Week | Focus |
|---|---|
| 1 | Phase 0 + Phase 1 (registry + brand scorer) |
| 2 | Phase 2 (API, decision layer, web page) |
| 3 | Phase 3 (remaining scorers) |
| 4 | Phase 4 + start of Phase 5 (resilience, audit, explanations) |
| 5 | Finish Phase 5 + Phase 6 (translations, admin, evaluation) |
| 6 | Phase 7 (user testing, docs, polish) |

Adjust around exams and placement prep. The plan works fine paused between phases.

---

## Definition of "finished v0.1"

- [ ] `docker compose up --build` starts API, Redis, Jaeger; the web app works on a phone
- [ ] Registry has at least 10 brands, each with a source and date
- [ ] Verdicts and reasons shown in English, Malayalam, and Hindi
- [ ] Degraded mode verified by test (never `MATCHES_OFFICIAL`)
- [ ] Evaluation reported on a held-out set, with **0 unsafe passes**
- [ ] Latency measured for cached, uncached, and timeout scenarios
- [ ] Raw chats not stored; identifiers hashed; audit chain verified
- [ ] 3–5 non-technical users tried it; top issues fixed
- [ ] README metrics are real numbers, no `TBD`
- [ ] BUILD_LOG is complete
