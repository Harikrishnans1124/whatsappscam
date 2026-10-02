# Build Log

**Purpose:** a running record of what was actually built, which technologies were used, what was measured, and what was learned. Update it at the end of every work session. When you come back after weeks away (or prepare for an interview), read this file first.

> Rule: only write things that are **true and measured**. If you didn't run it, mark it `not done`.

---

## Summary snapshot (keep this current)

| Item | Status | Notes |
|---|---|---|
| Brand registry (N brands, all with sources) | ☑ | N = 11 (Amazon India, Flipkart, Myntra, Tata CLiQ, AJIO, Meesho, Nykaa, Zomato, Swiggy, Apple India, Acme Footwear) |
| Extraction (phone / URL / UPI / brand detection) | ☑ | Tested with Indian & international formats, UPI vs email filtering |
| Brand identity scorer | ☑ | Outcomes: MATCH (0.0), MISMATCH (0.85), UNKNOWN_BRAND (0.20), NO_BRAND_CLAIM (None) |
| Payment scorer | ☐ | Phase 3a |
| Message scorer: rules | ☐ | Phase 3c |
| Message scorer: TF-IDF model | ☐ | PR-AUC public: ___ / own set: ___ |
| Domain scorer (RDAP + lookalike) | ☐ | Phase 3b |
| Number scorer + community reports | ☐ | Phase 3d |
| Decision layer (weights, floors, verdicts) | ☐ | Phase 2 |
| Timeouts + circuit breaker | ☐ | Phase 4 |
| Redis cache + rate limiting | ☐ | Phase 4 |
| Explanations (en / ml / hi) | ☐ | Native-speaker reviewed? ___ |
| Web app / PWA | ☐ | Phase 2 & 5 |
| Admin dashboard | ☐ | Phase 5 |
| Audit log + verify script | ☐ | Phase 4 |
| OpenTelemetry + Jaeger | ☐ | Phase 5 |
| Tests (count / coverage) | ☑ | 37 unit tests passing (100% green) |
| Evaluation set + results | ☐ | cases: ___ |
| Latency measurements | ☐ | |
| Docker Compose from a clean clone | ☐ | Redis defined |
| README metrics filled in | ☐ | |
| Tried by real users (non-technical) | ☐ | feedback: ___ |

**Technologies actually used so far:** Python 3.13, SQLAlchemy 2.0, SQLite, PyYAML, phonenumbers, tldextract, rapidfuzz, pytest, pytest-asyncio, ruff

---

## Key results (fill with measured numbers)

**Evaluation set** (`eval/cases.jsonl`)

| Metric | Tuning subset | Held-out subset |
|---|---|---|
| Number of cases | | |
| Scam recall | | |
| False-alarm rate (genuine flagged) | | |
| **Unsafe passes** (target 0) | | |
| Verdict accuracy | | |

**Message classifier**

| Dataset | PR-AUC | Precision / recall at chosen threshold |
|---|---|---|
| Public SMS held-out | | |
| My own examples | | |

**Latency** (machine: ___)

| Scenario | p50 | p95 | Notes |
|---|---|---|---|
| All cached | | | |
| Uncached domain lookup | | | |
| RDAP timeout (degraded) | | | |

**Settings chosen** (and why): weights ___, floors ___, thresholds ___

---

## Session entries

Copy this block for each work session.

### 2026-10-02: Phase 0 (Skeleton) & Phase 1 (Registry, Extraction, and Brand Identity Scorer)

- **Goal:** Build the core foundation of TrustShop AI: verified brand registry, phone and URL/UPI extraction, and the brand identity verification scorer.
- **What I built / changed:**
  - Initialized repo skeleton: `.gitignore`, `requirements.txt`, `requirements-dev.txt`, `docker-compose.yml`, `config/settings.yaml`, and root documents.
  - Curated `registry/brands.yaml` with 11 brands (10 major impersonated brands in India plus benchmark test brand), strictly recording source URLs and verified dates.
  - Implemented `app/registry.py` with SQLAlchemy models (`Brand`, `BrandAlias`, `BrandLegalName`, `BrandDomain`, `BrandPhone`, `BrandSource`), strict validation, querying, and freshness logic.
  - Implemented `scripts/seed_registry.py` to seed and validate registry entries in SQLite database `data/trustshop.db`.
  - Implemented `scripts/check_registry_freshness.py` to flag entries older than 90 days.
  - Implemented `app/extraction.py`: phone normalization to E.164 with number types (`phonenumbers`), URL & registrable domain parsing (`tldextract`), UPI VPA extraction with email filter, and claimed brand detection.
  - Implemented `app/agents/brand_identity.py`: core scorer yielding `MATCH` (risk 0.0), `MISMATCH` (risk 0.85, flag `BRAND_CHANNEL_MISMATCH`), `UNKNOWN_BRAND` (risk 0.20), and `NO_BRAND_CLAIM` (`not_applicable`).
  - Implemented `scripts/check_brand.py`: CLI testing tool for end-to-end extraction and scorer checks.
  - Added full test suite in `tests/`: 37 unit tests covering messy phone numbers, URL extraction, UPI/email separation, brand detection, registry seeding/validation, freshness, and brand identity outcomes.
- **Files touched:**
  - `registry/brands.yaml`
  - `app/__init__.py`, `app/config.py`, `app/registry.py`, `app/extraction.py`, `app/agents/__init__.py`, `app/agents/brand_identity.py`
  - `scripts/seed_registry.py`, `scripts/check_registry_freshness.py`, `scripts/check_brand.py`
  - `tests/test_extraction.py`, `tests/test_registry.py`, `tests/test_brand_identity.py`, `pytest.ini`
  - `config/settings.yaml`, `docker-compose.yml`, `requirements.txt`, `requirements-dev.txt`, `.gitignore`
  - `PLAN.md`, `docs/PLAN.md`, `docs/BUILD_LOG.md`
- **Tech / concepts used:** SQLAlchemy 2.0 ORM, SQLite, phonenumbers (Google libphonenumber port), tldextract (Public Suffix List), regex for VPA parsing, rapidfuzz, PyYAML, pytest, ruff.
- **How to reproduce / run it:**
  - `python scripts/seed_registry.py`
  - `python scripts/check_registry_freshness.py --max-age-days 90`
  - `python scripts/check_brand.py --brand Flipkart --phone "+91 1800 202 9898"` (MATCH)
  - `python scripts/check_brand.py --brand Flipkart --phone "+91 98765 43210"` (MISMATCH)
  - `pytest -v`
  - `ruff check .`
- **Result / evidence:**
  - 11 brands seeded successfully with 0 validation errors.
  - Freshness check confirms all 11 brands are verified within 90 days.
  - CLI tests correctly identified official contacts, impersonations, unknown brands, and no-claim cases.
  - 37 / 37 unit tests passing in pytest (0.97s).
  - Ruff linter check: All checks passed!
- **Problems hit and how I fixed them:**
  - CP1252 character map error on Windows when printing unicode checkmark `✓` in PowerShell; replaced with `[OK]`.
  - UPI regex initially matched email addresses; added strict negative rules rejecting `.com`, `.org`, and known email providers (`gmail.com`, etc.), while validating UPI handle syntax.
  - Pytest module discovery needed `pythonpath = .` in `pytest.ini`.
- **What I learned (in my own words):**
  - Distinguishing brand identity against verified official registry channels is much more robust than text heuristics alone: a fraudster can easily modify their pitch, but they cannot impersonate an official E.164 phone or official registrable domain.
- **Next step:** Phase 2: API skeleton with FastAPI, Pydantic schemas, RFC 9457 errors, decision layer with hard-flag floors and re-weighted scoring, and minimal web UI.

---

## Decisions log

Record every non-obvious decision so future-you understands *why*.

| Date | Decision | Alternatives considered | Reason |
|---|---|---|---|
| | Shopper-side checker (user submits number, chat, link, payment) | Shop-side checkout fraud API | Targets the real problem: fake sellers using trusted brand names |
| | Brand registry match is the primary signal | Pure ML classifier | Scammers can reword messages but can't make their number official |
| | Four verdicts; never "safe" | Binary safe/scam | A wrong "safe" is the most harmful error |
| | `MATCHES_OFFICIAL` only via registry match and no degradation | Low risk = safe | Avoid false reassurance |
| | `risk_score` (1 = risky) | `trust_score` | Clearer for a scam checker |
| | v1 doesn't fetch user-submitted URLs | Scrape pages | Avoids SSRF and malware risk |
| | HMAC-hashed identifiers, raw chats not stored | Store everything | Privacy; legal exposure |
| | Web/PWA first | WhatsApp bot first | Bot needs Meta business setup/approval; web is faster to ship |
| | Rules first, ML supporting | ML primary | Public data doesn't match the target (WhatsApp seller scams) |
| | | | |

---

## Registry change log

Track every brand added or updated, with its source.

| Date | Brand | Change | Source URL |
|---|---|---|---|
| | | | |

---

## Problems and fixes (troubleshooting diary)

| Symptom | Cause | Fix |
|---|---|---|
| | | |

---

## User testing notes

Ask 3–5 non-technical people (family, friends) to try it with realistic examples. Watch where they get stuck.

| Date | Who (role only) | What confused them | Change made |
|---|---|---|---|
| | | | |

---

## Interview cheat sheet (fill in as you go)

Be able to answer each in 1–2 minutes:

1. **What problem does this solve and why this design?** _(impersonation scams; verify identity against an official source first)_
2. **Walk me through a request end to end.**
3. **Why is the registry the primary signal and what are its weaknesses?** _(coverage, freshness, data entry accuracy)_
4. **What are the four verdicts and why is there no "safe"?**
5. **How does the decision layer work?** _(weighted risk, hard-flag floors, verdict rules, degraded rules)_
6. **What happens when the domain lookup is slow or down?** _(timeout, breaker, `failed` vs `not_applicable`, degraded cannot be MATCHES_OFFICIAL)_
7. **How did you evaluate it, and what's the "unsafe pass" metric?**
8. **What are the limits of your message classifier?** _(SMS data vs WhatsApp scams, languages)_
9. **How do you handle privacy?** _(HMAC hashing, no raw chats, retention, no PII in traces)_
10. **How could the system be abused and what did you do?** _(false reports, probing, SSRF, registry poisoning)_
11. **What would you do next with more time?** _(WhatsApp bot, OCR, multilingual model, larger registry)_

---

## Resume bullet drafts (only use real numbers)

- Built a scam-verification service (FastAPI, Redis, SQLite) that checks whether a seller's WhatsApp number, links, and UPI payee match a source-verified registry of **N** brands, returning explainable verdicts in English, Malayalam, and Hindi.
- Designed five parallel checks (registry match, payee-name matching, lookalike-domain detection via RDAP and edit distance, scam-tactic rules plus TF-IDF classifier, number reputation) with per-check timeouts, circuit breakers, and a conservative decision layer; achieved **__%** scam recall with **0** unsafe passes on a **N**-case hand-labeled evaluation set.
- Implemented privacy-by-design (HMAC-hashed identifiers, no raw-chat storage), SSRF-safe outbound requests, RFC 9457 errors, OpenTelemetry tracing, and a hash-chained audit log; shipped with Docker Compose and **N** pytest tests.
- Motivation line (optional, in your own words): built in response to the real-world rise of WhatsApp brand-impersonation scams.
