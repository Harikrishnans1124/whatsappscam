# Build Log

**Purpose:** a running record of what was actually built, which technologies were used, what was measured, and what was learned. Update it at the end of every work session. When you come back after weeks away (or prepare for an interview), read this file first.

> Rule: only write things that are **true and measured**. If you didn't run it, mark it `not done`.

---

## Summary snapshot (keep this current)

| Item | Status | Notes |
|---|---|---|
| Brand registry (N brands, all with sources) | ☐ | N = ___ |
| Extraction (phone / URL / UPI / brand detection) | ☐ | |
| Brand identity scorer | ☐ | |
| Payment scorer | ☐ | |
| Message scorer: rules | ☐ | |
| Message scorer: TF-IDF model | ☐ | PR-AUC public: ___ / own set: ___ |
| Domain scorer (RDAP + lookalike) | ☐ | |
| Number scorer + community reports | ☐ | |
| Decision layer (weights, floors, verdicts) | ☐ | |
| Timeouts + circuit breaker | ☐ | |
| Redis cache + rate limiting | ☐ | |
| Explanations (en / ml / hi) | ☐ | Native-speaker reviewed? ___ |
| Web app / PWA | ☐ | |
| Admin dashboard | ☐ | |
| Audit log + verify script | ☐ | |
| OpenTelemetry + Jaeger | ☐ | |
| Tests (count / coverage) | ☐ | |
| Evaluation set + results | ☐ | cases: ___ |
| Latency measurements | ☐ | |
| Docker Compose from a clean clone | ☐ | |
| README metrics filled in | ☐ | |
| Tried by real users (non-technical) | ☐ | feedback: ___ |

**Technologies actually used so far:** _(list them, e.g. FastAPI, Redis, phonenumbers…)_

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

### YYYY-MM-DD: short title

- **Goal:**
- **What I built / changed:**
- **Files touched:**
- **Tech / concepts used:** _(and the link or doc I learned it from)_
- **How to reproduce / run it:**
- **Result / evidence:** _(metric, screenshot, trace, test output)_
- **Problems hit and how I fixed them:**
- **What I learned (in my own words):**
- **Next step:**

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
