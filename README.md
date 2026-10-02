# TrustShop AI

> **Check before you pay.** Paste the phone number, chat message, link, or payment ID a "seller" gave you. TrustShop AI tells you whether it really belongs to the brand they claim to be, and explains why in plain language.

![status](https://img.shields.io/badge/status-in%20development-orange)
![python](https://img.shields.io/badge/python-3.11+-blue)
![license](https://img.shields.io/badge/license-MIT-green)

---

## Table of contents

1. [Why this exists](#why-this-exists)
2. [What it checks](#what-it-checks)
3. [How it works](#how-it-works)
4. [Verdicts](#verdicts)
5. [Features](#features)
6. [Tech stack](#tech-stack)
7. [Quick start](#quick-start)
8. [Using the API](#using-the-api)
9. [Project structure](#project-structure)
10. [Documentation index](#documentation-index)
11. [Evaluation and performance](#evaluation-and-performance)
12. [Safety, privacy, and limitations](#safety-privacy-and-limitations)
13. [If you've been scammed](#if-youve-been-scammed)
14. [Roadmap](#roadmap)
15. [License](#license)

---

## Why this exists

A common scam goes like this: a shopper knows and trusts a famous brand. Someone pretending to be that brand contacts them on WhatsApp (or sends a link), offers a good deal, and asks them to pay to a number or payment ID. The shopper trusts the **brand**, but never checks that this **number, link, or payee actually belongs to the brand**.

TrustShop AI is built around that gap. Its strongest check is not a fancy model but a simple question: *is this contact on the brand's official list?* Machine learning and rules then add extra evidence on top.

---

## What it checks

You can submit any combination of:

| Input | Example |
|---|---|
| Phone / WhatsApp number | `+91 98765 43210` |
| Message text (paste the chat) | "Limited stock! Pay advance on this number…" |
| Links | `https://acmefootwear-outlet.shop/deal` |
| Payment details | UPI ID and the **name your UPI app shows before you pay** |
| Brand they claim to be (optional, auto-detected if omitted) | "Acme Footwear" |

*(Acme Footwear is a fictional brand used throughout the docs.)*

Five independent checks run in parallel:

| Check | Question it answers |
|---|---|
| **Brand identity** | Is this number / domain on the brand's official list? |
| **Payment** | Does the payee name match the company, or is it a personal account? |
| **Message** | Does the text use known scam tactics (pressure, advance payment, move to a personal chat, OTP requests)? |
| **Domain** | Is the link new, a lookalike of the real domain, or a URL shortener? |
| **Number** | Is it a valid number, and have other users reported it? |

---

## How it works

```
 User submits number / message / link / payment details   (web page)
                         │
                         ▼
        ┌──────────────────────────────────┐
        │ 1. Validate + normalize          │  Pydantic, phonenumbers
        │ 2. Extract phones, URLs, UPI IDs,│
        │    detect claimed brand          │
        └────────────────┬─────────────────┘
                         ▼       (parallel, each with a timeout)
   ┌──────────┬──────────┬──────────┬──────────┬──────────┐
   │ Brand    │ Payment  │ Message  │ Domain   │ Number   │
   │ identity │          │          │          │          │
   │ registry │ name     │ rules +  │ RDAP +   │ libphone │
   │ lookup   │ match    │ TF-IDF   │ lookalike│ + reports│
   └────┬─────┴────┬─────┴────┬─────┴────┬─────┴────┬─────┘
        └──────────┴──────────┼──────────┴──────────┘
                              ▼
               ┌────────────────────────────┐
               │ Decision layer             │  weighted risk + hard-flag floors
               └─────────────┬──────────────┘
                             ▼
        Verdict + reasons + advice (English / Malayalam / Hindi)
```

If an outside service (like a domain lookup) is slow or down, the system says so and **never** upgrades the result to "matches official" on partial information. Details: [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

---

## Verdicts

| Verdict | Meaning | What the user should do |
|---|---|---|
| `MATCHES_OFFICIAL` | The submitted contact(s) match the brand's official registry entry, with no red flags | Still confirm inside the brand's official app or website before paying |
| `UNVERIFIED` | No red flags found, but it couldn't be verified (brand not in registry, or too little info) | Don't treat as safe. Verify on the brand's official website |
| `SUSPICIOUS` | One or more red flags | Don't pay. Contact the brand through its official website or app |
| `LIKELY_SCAM` | Strong evidence of impersonation | Don't pay. Report it (see [below](#if-youve-been-scammed)) |

The tool never says "100% safe". A wrong "safe" is the most dangerous mistake it can make, so it is designed to be cautious.

---

## Features

- Brand registry of official domains, phone numbers, and payment policy, each entry with a **source URL and verification date**
- Five parallel checks with per-check timeouts and circuit breakers
- Explainable results: `reason_codes` and plain-language explanations
- Explanations in English, Malayalam, and Hindi (template-based)
- Lookalike-domain detection (typos, brand-name stuffing, look-alike characters)
- UPI payee-name matching against the brand's registered names
- Community reports (hashed, deduplicated, abuse-resistant) feeding the number check
- Safe-by-design networking: no fetching of user-supplied URLs in v1 (avoids SSRF)
- Privacy-first storage: hashed identifiers, raw chats not stored by default
- Tamper-evident audit log of checks (hashes only)
- OpenTelemetry tracing, Redis caching and rate limiting
- Evaluation set with an "unsafe pass" metric (scams wrongly marked as official; target: 0)
- Mobile-friendly web page (installable PWA) and an admin dashboard for the registry and reports

> Tick the boxes in [`PLAN.md`](PLAN.md) to see what is built so far.

---

## Tech stack

| Layer | Technology |
|---|---|
| API | Python 3.11, FastAPI, Pydantic v2, Uvicorn |
| Cache and rate limiting | Redis |
| Registry and reports storage | SQLite via SQLAlchemy |
| Phone parsing | `phonenumbers` (port of Google libphonenumber) |
| Domain analysis | `tldextract`, `rapidfuzz`, RDAP lookups via `httpx` |
| Message classifier | scikit-learn (TF-IDF + logistic regression) plus rule engine |
| Resilience | asyncio timeouts, circuit breaker |
| Observability | OpenTelemetry, Jaeger |
| Frontend | HTML/JS PWA (served by FastAPI) |
| Admin | Streamlit |
| Testing | pytest, httpx (mocked external services) |
| Packaging | Docker, Docker Compose |

Why each was chosen, where it's used, and where to learn it: [`docs/TECH_STACK.md`](docs/TECH_STACK.md).

---

## Quick start

**Prerequisites:** Docker + Docker Compose. Python 3.11+ for development.

```bash
git clone https://github.com/<your-username>/trustshop-ai.git
cd trustshop-ai

# start API + Redis + Jaeger
docker compose up --build

# load the brand registry
docker compose exec api python scripts/seed_registry.py registry/brands.yaml
```

Open:
- Web app: http://localhost:8000
- API docs (Swagger): http://localhost:8000/docs
- Jaeger traces: http://localhost:16686

Training the message model, running tests, and evaluation: [`docs/DEVELOPMENT.md`](docs/DEVELOPMENT.md).

---

## Using the API

```bash
curl -X POST http://localhost:8000/v1/checks \
  -H "Content-Type: application/json" \
  -d '{
    "claimed_brand": "Acme Footwear",
    "phone_number": "+91 98765 43210",
    "message_text": "Special offer today only! 70% off. Pay advance on this number to confirm your order.",
    "urls": ["https://acmefootwear-outlet.shop/deal"],
    "payment": { "upi_id": "9876543210@ybl", "display_name": "Rakesh K", "amount": 1499 },
    "language": "en"
  }'
```

Example response (shortened):

```json
{
  "check_id": "c_000123",
  "verdict": "LIKELY_SCAM",
  "risk_score": 0.91,
  "brand": { "claimed": "Acme Footwear", "in_registry": true,
             "match": { "phone": false, "domain": false, "payment": false } },
  "summary": "This does not look like Acme Footwear. The number and website are not on the brand's official list, and the payment would go to a personal account.",
  "reason_codes": ["BRAND_CHANNEL_MISMATCH", "LOOKALIKE_DOMAIN", "PERSONAL_PAYEE", "ADVANCE_PAYMENT_REQUEST"],
  "advice": ["Do not pay.", "Open Acme Footwear's official website or app yourself and order there."],
  "degraded": false
}
```

Full schemas and errors: [`docs/API.md`](docs/API.md).

---

## Project structure

```
trustshop-ai/
├── app/
│   ├── main.py            # FastAPI app + routes
│   ├── schemas.py         # request/response models
│   ├── config.py          # settings.yaml + env vars
│   ├── extraction.py      # normalize phone, extract URLs/UPI IDs, detect brand
│   ├── registry.py        # brand registry access (SQLite)
│   ├── agents/
│   │   ├── brand_identity.py
│   │   ├── payment.py
│   │   ├── message.py
│   │   ├── domain.py
│   │   └── number.py
│   ├── decision.py        # combine scores, hard-flag floors, verdict
│   ├── breaker.py         # timeouts + circuit breaker
│   ├── cache.py           # Redis cache + rate limiting
│   ├── safe_fetch.py      # allowlisted outbound HTTP (RDAP etc.)
│   ├── reports.py         # community reports
│   ├── explain.py         # reason codes → plain-language text
│   ├── i18n/              # en.yaml, ml.yaml, hi.yaml
│   ├── audit.py           # hash-chained audit log
│   ├── errors.py          # RFC 9457 problem+json
│   └── telemetry.py       # OpenTelemetry
├── registry/brands.yaml   # official channels, with sources
├── training/              # message classifier notebook + features
├── eval/                  # labeled cases + run_eval.py
├── frontend/              # index.html, app.js, manifest.json
├── dashboard/admin.py     # Streamlit admin
├── scripts/               # seed_registry.py, verify_audit.py, check_registry_freshness.py
├── config/settings.yaml
├── tests/
├── docs/
├── docker-compose.yml
├── PLAN.md
└── README.md
```

---

## Documentation index

| Doc | What's in it |
|---|---|
| [`PLAN.md`](PLAN.md) | Phase-by-phase build plan with checkboxes |
| [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | Components, decision logic, failure handling, privacy and abuse model |
| [`docs/API.md`](docs/API.md) | Endpoints, schemas, reason codes, errors |
| [`docs/TECH_STACK.md`](docs/TECH_STACK.md) | Every technology: why, where, how, learning links |
| [`docs/DEVELOPMENT.md`](docs/DEVELOPMENT.md) | Setup, registry seeding, training, tests, evaluation |
| [`docs/BUILD_LOG.md`](docs/BUILD_LOG.md) | What was actually built, results, decisions, interview notes |

---

## Evaluation and performance

> Fill these in with **measured** values (Phase 6). Don't leave estimates here.

**Evaluation set** (`eval/cases.jsonl`, hand-labeled; N = _TBD_ cases)

| Metric | Value |
|---|---|
| Scam cases flagged `SUSPICIOUS` or `LIKELY_SCAM` (recall) | _TBD_ |
| Genuine cases wrongly flagged (false-alarm rate) | _TBD_ |
| **Unsafe passes** (scam marked `MATCHES_OFFICIAL`) | _TBD_ (target 0) |
| Verdict accuracy | _TBD_ |

**Message classifier** (auxiliary; trained on public SMS spam data, so expect domain shift)

| Metric | Value |
|---|---|
| PR-AUC on held-out set | _TBD_ |

**Latency** (machine: _TBD_)

| Scenario | p50 | p95 |
|---|---|---|
| All cached | _TBD_ | _TBD_ |
| Uncached domain lookup | _TBD_ | _TBD_ |

Design target: p95 under about 3 s for uncached checks. This is a goal to verify, not a claim.

---

## Safety, privacy, and limitations

- **Automated estimate, not proof.** Verdicts can be wrong. Always verify through the brand's official website or app.
- **Registry coverage is limited.** Only brands in the registry can be matched. Others get `UNVERIFIED`. Every entry needs a source URL and date, and the registry must be kept up to date.
- **No WhatsApp access.** The tool can't read chats or block numbers. Users paste or enter the details.
- **Scammers adapt.** Keyword rules can be evaded. That is why the official-registry match is the primary signal: a scammer can't make their number official.
- **Message model has a domain gap.** It is trained on public SMS spam, not WhatsApp seller scams. Rules carry most of the weight in v1.
- **Community reports can be abused** (false reports against genuine sellers). Reports are shown as "reported by N users", never as proof, and need multiple independent reporters.
- **Privacy.** Phone numbers, UPI IDs, and chats are personal data. Identifiers are stored hashed (HMAC), raw chats aren't stored by default, and retention is limited. Data-protection laws (for example India's DPDP Act, 2023) may apply to a deployed service; this is not legal advice.
- **Not a replacement for bank or police action.**

---

## If you've been scammed

In India:
1. Call **1930** (national cybercrime helpline) as soon as possible. Speed matters for freezing funds.
2. Report at **https://cybercrime.gov.in**.
3. Inform your bank and your UPI app provider immediately.
4. Keep screenshots, the phone number, payment receipts, and the chat.

---

## Roadmap

- [ ] WhatsApp bot (forward a suspicious message and get a verdict) via WhatsApp Cloud API
- [ ] Screenshot upload with OCR to extract numbers and payment IDs
- [ ] Malayalam / Hindi / Manglish message understanding with multilingual embeddings
- [ ] Safe page-content analysis (with SSRF protections)
- [ ] Browser extension
- [ ] Larger brand registry with automated freshness checks

---

## License

MIT. See `LICENSE`.
