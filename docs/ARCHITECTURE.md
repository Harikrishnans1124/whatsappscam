# Architecture

This document explains **how TrustShop AI is put together and why**. If you're re-reading after a break, read [1](#1-the-one-paragraph-version), [2](#2-component-diagram) and [4](#4-decision-logic) first.

---

## 1. The one-paragraph version

A shopper submits what a "seller" gave them: a phone number, chat text, links, and payment details (UPI ID and the payee name shown in the UPI app). The API validates and normalizes the input, extracts phones, URLs, and payment IDs, and detects which brand the seller claims to be. Five scorers then run **in parallel**, each with its own timeout: **brand identity** (is this contact on the brand's official list?), **payment**, **message**, **domain**, and **number**. The **decision layer** combines their risk scores with hard-flag rules and returns one of four verdicts (`MATCHES_OFFICIAL`, `UNVERIFIED`, `SUSPICIOUS`, `LIKELY_SCAM`) with reason codes and plain-language advice in English, Malayalam, or Hindi.

The design principle: **verify identity against an official source first, use ML only as supporting evidence.** A scammer can change their wording; they can't get their number onto the brand's official list.

---

## 2. Component diagram

```
 Browser (PWA)
     │  POST /v1/checks
     ▼
┌───────────────────────────────────────────────┐
│ FastAPI (app/main.py)                         │
│  • Pydantic validation (schemas.py)           │
│  • Rate limit (cache.py, Redis)               │
└──────────────────┬────────────────────────────┘
                   ▼
┌───────────────────────────────────────────────┐
│ Extraction (extraction.py)                    │
│  • phone → E.164 (phonenumbers)               │
│  • URLs, UPI IDs from message text            │
│  • claimed brand: user-given or detected      │──▶ Registry (SQLite)
└──────────────────┬────────────────────────────┘
                   │  asyncio.gather (parallel)
 ┌─────────┬───────┴────┬───────────┬───────────┐
 ▼         ▼            ▼           ▼           ▼
Brand     Payment     Message     Domain      Number
identity  scorer      scorer      scorer      scorer
registry  name match  rules +     RDAP +      libphone +
lookup    + VPA type  TF-IDF LR   lookalike   reports DB
 │         │            │           │           │
 └─────────┴────────────┴─────┬─────┴───────────┘
   each wrapped by breaker.py (timeout + circuit breaker)
                              ▼
┌───────────────────────────────────────────────┐
│ Decision layer (decision.py)                  │
│  weighted risk + hard-flag floors + verdict   │
└──────────────────┬────────────────────────────┘
                   ▼
┌───────────────────────────────────────────────┐
│ Explain (explain.py + i18n/*.yaml)            │
└──────────────────┬────────────────────────────┘
        ┌──────────┼───────────┐
        ▼          ▼           ▼
   Audit log    OTel spans   Response
   (hashes)     (Jaeger)
```

---

## 3. Components in detail

### 3.1 API layer (`main.py`, `schemas.py`, `errors.py`)
- **Validation:** at least one of `phone_number`, `message_text`, `urls`, `payment.upi_id` is required. Limits: message up to 5,000 characters, up to 5 URLs.
- **Errors:** `application/problem+json` per [RFC 9457](https://www.rfc-editor.org/rfc/rfc9457).
- **Rate limiting:** per-IP limit in Redis. This also slows scammers who might probe the tool to learn how to evade it.

### 3.2 Extraction (`extraction.py`)
| Task | How |
|---|---|
| Normalize phone | `phonenumbers.parse(raw, "IN")` → E.164, validity, number type |
| Find URLs in text | regex, then `tldextract` to get the registrable domain |
| Find UPI IDs in text | regex for `name@handle`. Note this also matches emails, so filter by known UPI handle suffixes or by context |
| Detect claimed brand | user-supplied value, else match brand names/aliases from the registry against message text and domains |

Outputs a clean `CheckContext` object that every scorer receives.

### 3.3 Brand registry (`registry.py`, `registry/brands.yaml`)

The registry is the backbone of the product. One entry per brand:

```yaml
- slug: acme-footwear            # fictional brand
  name: Acme Footwear
  aliases: ["acme shoes", "acme"]
  legal_names: ["Acme Footwear Private Limited"]
  official_domains: ["acmefootwear.com"]
  official_phones: ["+911800XXXXXXX"]       # only numbers the brand itself publishes
  payment_policy: "Pays only through the official website/app checkout; never asks for payment to personal accounts."
  sources:
    - url: "https://www.acmefootwear.com/contact"
      verified_on: "2026-10-01"
```

Rules for entries:
1. **Only add data you can verify on the brand's own official site or app.** Record the source URL and date.
2. Mark entries **stale** after 90 days (`scripts/check_registry_freshness.py`) and lower their weight until re-verified.
3. If a brand doesn't publish a WhatsApp or sales number, the registry says so (`official_phones: []`). Then "this number isn't official" is naturally true, and the advice becomes "this brand does not sell through WhatsApp numbers; use the official site".
4. Start with about 10 brands, grow to 30–50. Everything else returns `UNVERIFIED`.

### 3.4 Scorers (`app/agents/`)

All scorers return:

```python
{
  "status": "ok" | "not_applicable" | "failed",
  "risk": float | None,        # 0 = no concern, 1 = very risky (None unless status=="ok")
  "reasons": list[str],        # reason codes
  "flags": list[str],          # hard flags that trigger floors in the decision layer
  "evidence": dict             # small facts for the explanation (e.g. domain_age_days)
}
```

`not_applicable` (the user didn't provide that input) is deliberately different from `failed` (the check broke), because they affect the verdict differently.

**Brand identity scorer** (`brand_identity.py`)
- Looks up the claimed brand. Compares the normalized phone and each URL's registrable domain against the official sets.
- Outcomes: `MATCH`, `MISMATCH` (brand in registry, channel not official), `UNKNOWN_BRAND`, `NO_BRAND_CLAIM`.
- `MISMATCH` raises flag `BRAND_CHANNEL_MISMATCH`. `UNKNOWN_BRAND` gives a neutral risk and reason `BRAND_NOT_IN_REGISTRY`.

**Payment scorer** (`payment.py`)
- Compares the user-entered **payee display name** to the brand's `legal_names`/`name` with `rapidfuzz.fuzz.token_set_ratio` (e.g. ≥ 80 counts as a match).
- Flags `PERSONAL_PAYEE` if a brand is claimed and the payee name doesn't match it and looks like a personal name (no company tokens like *Pvt, Ltd, Private, Limited, LLP, Enterprises, Stores*).
- Weak signal: a UPI ID that is a phone number plus a bank handle (`9876543210@ybl`) suggests a personal account. Many handles (`@ybl`, `@okhdfcbank`…) serve both personal and business users, so this alone never decides.
- Limitation: it depends on the user typing the payee name. The UI should explain why and where to find it (the name shown just before confirming payment).

**Message scorer** (`message.py`)
- **Rules (main weight in v1):** regex/keyword patterns for urgency ("today only", "last 2 pieces"), too-good discounts, advance-payment requests, moving the conversation to a personal chat or number, requests for an OTP (flag `OTP_REQUEST`), requests to install remote-access apps such as AnyDesk or TeamViewer (flag `REMOTE_ACCESS_REQUEST`).
- **ML (supporting weight):** TF-IDF + logistic regression trained on public SMS spam data plus your own labeled examples. Its output is a probability that adds a small amount of risk.
- Caveat: SMS spam and WhatsApp seller scams differ. Evaluate the classifier on your own cases, not just on the public set. Messages in Malayalam, Hindi, or Manglish aren't handled well in v1.

**Domain scorer** (`domain.py`)
- **Age:** RDAP lookup for the registration date (coverage varies by TLD; document fallbacks). Young domains (for example under 30 days) add risk. Cache results in Redis.
- **Lookalike:** compare the domain's label to registry brands' official domains using Levenshtein distance (`rapidfuzz`), brand name stuffing (`acmefootwear-outlet.shop`), hyphen/digit tricks, and look-alike Unicode characters in IDNs (Punycode). A hit raises flag `LOOKALIKE_DOMAIN`.
- **Other signals:** URL shorteners, odd TLDs (a weak signal; never decisive).
- **Optional:** Google Safe Browsing lookup if you add an API key.
- **v1 deliberately does not fetch the submitted page.** Fetching user-supplied URLs creates SSRF and malware risks. Only allowlisted APIs (RDAP, Safe Browsing) are called.

**Number scorer** (`number.py`)
- Validity and type via `phonenumbers` (invalid → high risk; a personal mobile number claiming to be a big brand is a weak signal).
- Community reports: `HMAC(secret, e164_number)` → report count and number of distinct reporters. Several independent reports add risk; the UI says "reported by N users", never "is a scammer".

### 3.5 Timeouts and circuit breakers (`breaker.py`)
- Local scorers (brand, payment, message, number): about 150 ms timeout.
- Domain scorer (network): about 2,500 ms timeout.
- One breaker per external dependency (RDAP, Safe Browsing). After N consecutive failures the scorer is skipped immediately for a cooldown, then probed again.
- Scorers run with `asyncio.gather`, so total time ≈ the slowest scorer, not the sum. CPU-bound work (model inference) goes through `asyncio.to_thread`.

### 3.6 Cache and rate limits (`cache.py`)
- RDAP results: key `rdap:{domain}`, TTL 24 h. Safe Browsing results: short TTL.
- Rate limit: fixed window per IP.
- If Redis is down, the system works without caching and notes degraded performance.

### 3.7 Explanations (`explain.py`, `i18n/`)
- Each reason code has a plain-language template per language (`en`, `ml`, `hi`). Missing translation falls back to English.
- Advice is chosen from the verdict (what to do next), including the official-site recommendation and, for `LIKELY_SCAM`, the reporting steps.
- No LLM is used in v1: templates are predictable and safe. Have a native speaker review Malayalam and Hindi text.

### 3.8 Audit log (`audit.py`)
Hash-chained, append-only: `entry_hash = SHA-256(prev_hash || canonical_json(entry))`. Entries hold the verdict, risk score, reason codes, and **HMAC-hashed identifiers only**, never raw chats. `scripts/verify_audit.py` re-checks the chain. This is tamper-evident, not tamper-proof; real immutability needs WORM storage or external anchoring.

### 3.9 Observability (`telemetry.py`)
OpenTelemetry spans: `check` → `extract`, `agent.brand_identity`, `agent.payment`, `agent.message`, `agent.domain`, `agent.number`, `decision`. Exported to Jaeger. No PII in span attributes.

---

## 4. Decision logic

All scorer outputs are **risk** values (0 = no concern, 1 = very risky). *(The earlier shop-side design used a "trust score" where 1 was safe; risk is more natural for a scam checker.)*

### Step 1: weighted risk
Only scorers with `status == "ok"` count. Default weights (`config/settings.yaml`):

```
brand_identity 0.35 | payment 0.20 | message 0.20 | domain 0.15 | number 0.10
risk_weighted = Σ(w_i · risk_i) / Σ(w_i)       # over scorers with status "ok"
```

Weights of `not_applicable` and `failed` scorers are dropped and the rest are renormalized.

### Step 2: hard-flag floors
Some single facts are strong enough that averaging shouldn't dilute them:

| Flag | Minimum risk |
|---|---|
| `BRAND_CHANNEL_MISMATCH` (known brand, contact not official) | 0.55 |
| `PERSONAL_PAYEE` (known brand, payee is a personal name) | 0.70 |
| `LOOKALIKE_DOMAIN` (resembles a registry brand's domain) | 0.85 |
| `OTP_REQUEST` | 0.85 |
| `REMOTE_ACCESS_REQUEST` | 0.85 |

`risk = max(risk_weighted, highest floor triggered)`

### Step 3: verdict

| Condition | Verdict |
|---|---|
| `risk >= 0.65` | `LIKELY_SCAM` |
| `0.35 <= risk < 0.65` | `SUSPICIOUS` |
| `risk < 0.35` **and** at least one submitted channel (phone or domain) matched the registry, **none** mismatched, and **every** submitted input was successfully checked | `MATCHES_OFFICIAL` |
| otherwise (`risk < 0.35`) | `UNVERIFIED` |

Key safety rules:
- `MATCHES_OFFICIAL` can **only** come from a registry match. Low risk alone is `UNVERIFIED`, never "safe".
- If any applicable scorer failed (degraded), `MATCHES_OFFICIAL` is not allowed.
- A stale registry entry (older than 90 days) caps the verdict at `UNVERIFIED`.

### Tuning
The thresholds (0.35, 0.65) and weights are starting points. Tune them on `eval/cases.jsonl` and keep the **unsafe-pass count at 0**. Record the chosen values and reasoning in `docs/BUILD_LOG.md`.

---

## 5. Failure modes

| Failure | Behavior |
|---|---|
| Invalid payload | `422` problem+json |
| Rate limit exceeded | `429` |
| Domain lookup (RDAP) times out or fails | Domain scorer `failed`; response `degraded: true`; verdict can't be `MATCHES_OFFICIAL` |
| Breaker open for an external service | Scorer skipped fast; same degraded handling |
| Redis down | No caching or rate limiting; still answers; slower |
| Registry DB unavailable | Brand scorer `failed`; verdict `UNVERIFIED` with `REGISTRY_UNAVAILABLE` |
| All scorers fail | `UNVERIFIED` with `DEGRADED_MODE` and advice to verify on the official site |
| Audit write fails | Request still answered; error logged |

---

## 6. Data and evaluation

| Asset | Source | Notes |
|---|---|---|
| Brand registry | Hand-curated from official brand sites | Source URL + date for every entry |
| Message classifier data | UCI SMS Spam Collection plus your own labeled examples | Public data is SMS, not WhatsApp seller scams. Expect domain shift |
| Evaluation cases | `eval/cases.jsonl`, written by you | Aim for 100–200 cases |

Evaluation cases should cover:
1. Genuine contact that matches the registry
2. Impersonation with a wrong number
3. Lookalike domain
4. Personal UPI payee for a known brand
5. **Genuine small shop not in the registry** (tests false alarms)
6. Message-only scams (no number or link)
7. Edge cases: mixed channels, missing inputs, typos

Write scam examples based on public awareness material and your own wording. Don't copy real victims' chats or personal data into the repo.

**Metrics:** scam recall, false-alarm rate on genuine cases, verdict accuracy, and **unsafe passes** (a scam marked `MATCHES_OFFICIAL`; must be 0). Report the small sample size honestly.

---

## 7. Security, privacy, and abuse model

| Concern | Mitigation |
|---|---|
| **SSRF** (tricking the server into fetching internal addresses) | v1 never fetches user-supplied URLs. Outbound calls only to allowlisted hosts. See OWASP's SSRF cheat sheet |
| **Personal data** (numbers, UPI IDs, chats) | HMAC-hash identifiers, don't store raw chats by default, short retention, no PII in logs or traces |
| **False reports** against genuine sellers | Need multiple distinct reporters, show "reported by N users", provide a dispute path, rate-limit reporting |
| **Scammers probing the tool** | Rate limiting; the main signal (official registry) can't be gamed by rewording |
| **Defamation / over-claiming** | Wording: "does not match", "red flags found", never "this person is a scammer". Verdicts are estimates |
| **Wrong "safe"** | `MATCHES_OFFICIAL` requires a registry match; the unsafe-pass metric is tracked; advice always recommends confirming in the official app |
| **Registry poisoning** (bad entries) | Admin-only writes (API key), source URL + date required, freshness checks |
| **Secrets** | `HMAC_SECRET`, `ADMIN_API_KEY` from environment variables, never committed |

---

## 8. What changed from the original design

| Original PIPELINE.md / first docs | Now | Why |
|---|---|---|
| Shop-side checkout fraud (order JSON from a shop's backend) | Shopper-side impersonation checker (user submits number, chat, link, payment) | Matches the real problem: fake sellers using trusted brand names |
| "Multi-agent" | Five scorers | They are rules/lookups/ML, not LLM agents |
| Behavioral fraud scorer (LightGBM on transaction data) | Brand identity, payment, message, number scorers | There's no buyer behavior data in this flow |
| Catalog authenticity (embeddings vs counterfeit listings) | Domain/lookalike and message checks | Main risk is a fake channel, not a fake product page |
| Confidence / trust score (1 = safe) | `risk_score` (1 = risky) + four verdicts | Clearer for users; avoids saying "safe" |
| 120 ms / 25,000 req/s targets | Measured latency; external lookups cached | Network lookups take longer; unverified numbers removed |
| Idempotency keys | Rate limiting + caching | Not a payment API |
| RFC-7807 "schema validation" | Pydantic validation, RFC 9457 error format | 7807 is an error format spec |
