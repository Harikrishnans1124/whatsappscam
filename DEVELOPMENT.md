# Development Guide

How to set up, run, seed, train, test, and evaluate TrustShop AI on your own machine.

---

## 1. Prerequisites

| Tool | Version | Used for |
|---|---|---|
| Python | 3.11+ | API, training, scripts |
| Docker + Docker Compose | recent | Redis, Jaeger, full stack |
| Git | n/a | version control |
| A modern browser | n/a | testing the web app / PWA |

Optional: a Google Safe Browsing API key (stretch), Tesseract (OCR stretch).

---

## 2. Local setup

```bash
git clone https://github.com/<your-username>/trustshop-ai.git
cd trustshop-ai

python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

Suggested `requirements.txt`:

```
fastapi
uvicorn[standard]
pydantic>=2
httpx
redis>=5
sqlalchemy>=2
pyyaml
phonenumbers
tldextract
rapidfuzz
scikit-learn
joblib
numpy
pandas
opentelemetry-api
opentelemetry-sdk
opentelemetry-exporter-otlp
opentelemetry-instrumentation-fastapi
```

Suggested `requirements-dev.txt`:

```
pytest
pytest-asyncio
respx
jupyter
matplotlib
streamlit
requests
ruff
```

---

## 3. Build the brand registry (do this first)

The registry is the most important data in the project. Do it carefully.

1. Pick **about 10 brands** to start (well-known brands that are commonly impersonated).
2. For each brand, open the brand's **own official website or app** and record:
   - official domain(s)
   - customer-care or sales phone numbers the brand itself publishes (many brands publish none for WhatsApp sales, and that's fine: use `[]`)
   - legal company name(s) (usually in the website footer, "About", or terms page)
   - the brand's stated payment policy (for example "pay only on the website")
   - the **source URL** and **today's date**
3. Add entries to `registry/brands.yaml` (format in [`ARCHITECTURE.md`](ARCHITECTURE.md#33-brand-registry-registrypy-registrybrandsyaml)).
4. Never copy a number from a forum, a social post, or a search result snippet. Only from the brand's own channels.
5. Load it:

```bash
python scripts/seed_registry.py registry/brands.yaml
# rejects entries without a source URL and verified_on date
```

6. Check for stale entries any time:

```bash
python scripts/check_registry_freshness.py --max-age-days 90
```

---

## 4. Message classifier (supporting model)

1. Download the **UCI SMS Spam Collection** from https://archive.ics.uci.edu/dataset/228/sms+spam+collection and place the file in `data/`.
2. Create `training/own_examples.csv` with your own labeled messages (`text,label`): scam-style seller messages and normal shopping chat. Write them yourself from public awareness material. **Don't paste real victims' chats or anyone's personal details.**
3. Open `training/message_classifier.ipynb` and run all cells. It should:
   - train TF-IDF + logistic regression
   - report precision/recall and PR-AUC on a held-out split of the public data **and separately on your own examples**
   - save `models/message_clf.joblib`
4. Record both results in `docs/BUILD_LOG.md`. A big gap between them is expected and worth explaining.

---

## 5. Run the service

### Option A: full stack with Docker

```bash
docker compose up --build
docker compose exec api python scripts/seed_registry.py registry/brands.yaml
```

| Service | URL |
|---|---|
| Web app | http://localhost:8000 |
| Swagger docs | http://localhost:8000/docs |
| Jaeger UI | http://localhost:16686 |
| Redis | localhost:6379 |

### Option B: API locally, Redis/Jaeger in Docker

```bash
docker compose up redis jaeger -d
export REDIS_URL=redis://localhost:6379/0
export DATABASE_URL=sqlite:///data/trustshop.db
export HMAC_SECRET=change-me
export ADMIN_API_KEY=change-me-too
export OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317
uvicorn app.main:app --reload --port 8000
```

### Smoke test

```bash
curl http://localhost:8000/healthz
curl http://localhost:8000/readyz
curl http://localhost:8000/v1/brands
```

Then try the example request in the [README](../README.md#using-the-api).

---

## 6. Configuration

`config/settings.yaml`:

```yaml
verdict:
  suspicious_from: 0.35
  likely_scam_from: 0.65
weights:
  brand_identity: 0.35
  payment: 0.20
  message: 0.20
  domain: 0.15
  number: 0.10
floors:
  BRAND_CHANNEL_MISMATCH: 0.55
  PERSONAL_PAYEE: 0.70
  LOOKALIKE_DOMAIN: 0.85
  OTP_REQUEST: 0.85
  REMOTE_ACCESS_REQUEST: 0.85
timeouts_ms:
  brand_identity: 150
  payment: 150
  message: 150
  number: 150
  domain: 2500
breaker:
  fail_max: 5
  reset_timeout_s: 30
cache:
  rdap_ttl_s: 86400
rate_limit:
  per_minute: 30
registry:
  stale_after_days: 90
reports:
  min_distinct_reporters: 3
```

Environment variables:

| Variable | Default | Purpose |
|---|---|---|
| `REDIS_URL` | `redis://localhost:6379/0` | Cache and rate limiting |
| `DATABASE_URL` | `sqlite:///data/trustshop.db` | Registry and reports |
| `HMAC_SECRET` | none (required) | Keyed hashing of identifiers. Never commit it |
| `ADMIN_API_KEY` | none (required) | Protects admin endpoints |
| `MESSAGE_MODEL_PATH` | `models/message_clf.joblib` | Message classifier |
| `AUDIT_PATH` | `data/audit.jsonl` | Audit log file |
| `SAFE_BROWSING_API_KEY` | unset | Enables the optional Safe Browsing lookup |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | unset | Enables trace export |

---

## 7. Tests

```bash
pytest -q
ruff check .
```

Minimum coverage to aim for:

- **Extraction:** phone normalization (various Indian formats), URL and UPI extraction, emails not mistaken for UPI IDs
- **Brand identity:** match, mismatch, unknown brand, no claim, stale entry
- **Payment:** name match, personal payee, phone-based UPI ID (weak signal only)
- **Domain:** exact official domain, typo lookalike, brand-stuffed domain, shortener, young domain (RDAP mocked), RDAP failure → `failed`
- **Message:** each rule fires on an example and doesn't fire on normal chat
- **Decision layer:** weights renormalized when scorers are `not_applicable` or `failed`; every floor; threshold boundaries; **`MATCHES_OFFICIAL` never returned when degraded or when no registry match**
- **API:** validation errors are `application/problem+json`; 429 on rate limit; checks endpoint returns `200` + `degraded: true` when RDAP times out
- **Reports:** duplicate reports from one reporter ignored; threshold of distinct reporters enforced
- **Audit:** valid chain passes, tampered chain fails; entries contain no raw identifiers

---

## 8. Evaluation

```bash
python eval/run_eval.py eval/cases.jsonl
```

`eval/cases.jsonl` has one JSON object per line:

```json
{"id": "c001", "input": {"claimed_brand": "Acme Footwear", "phone_number": "+91 ...", "urls": ["..."]}, "expected": "LIKELY_SCAM", "category": "lookalike_domain"}
```

Categories to cover (aim for 100–200 cases total): genuine official contact, wrong-number impersonation, lookalike domain, personal UPI payee, genuine small shop not in the registry, message-only scam, mixed or missing inputs.

External lookups must be **mocked or replayed from saved responses** during evaluation so results are reproducible.

`run_eval.py` should print:

| Metric | How |
|---|---|
| Scam recall | share of scam cases that got `SUSPICIOUS` or `LIKELY_SCAM` |
| False-alarm rate | share of genuine cases that got `SUSPICIOUS` or `LIKELY_SCAM` |
| **Unsafe passes** | scam cases that got `MATCHES_OFFICIAL` (must be 0) |
| Verdict accuracy | exact match with `expected` |
| Confusion matrix | per verdict |

Tune weights, floors, and thresholds on a **tuning** subset, then report final numbers on a **held-out** subset you didn't tune on. Record both in `docs/BUILD_LOG.md`.

---

## 9. Latency measurement

External lookups dominate latency, so measure three situations:

1. All cached (second request for the same domain)
2. Uncached domain lookup (real RDAP, or a mock with a realistic delay)
3. RDAP timing out (confirms the fallback path and `degraded: true`)

Use a simple script with `httpx` and `time.perf_counter()`, or k6/Locust if you want load graphs. Record p50 and p95, the machine, and the cache hit rate. Use Jaeger traces to see which scorer is slowest.

---

## 10. Verify the audit log

```bash
python scripts/verify_audit.py data/audit.jsonl
# "OK: N entries verified" or the index of the first broken link
```

To prove it works, edit one line by hand and run it again. It should report the break.

---

## 11. Admin dashboard

```bash
export API_URL=http://localhost:8000
export ADMIN_API_KEY=change-me-too
streamlit run dashboard/admin.py
```

Shows registry entries (with "verified N days ago"), a form to add or update a brand (source URL required), and the community report queue.

---

## 12. Git hygiene

`.gitignore` should include:

```
.venv/
data/
models/*.joblib
__pycache__/
.ipynb_checkpoints/
.env
```

- Don't commit secrets (`HMAC_SECRET`, `ADMIN_API_KEY`, API keys).
- Don't commit raw datasets or any real chats or personal data.
- Do commit `registry/brands.yaml` (public facts with sources) and `eval/cases.jsonl` (synthetic or written by you).

Suggested commit style: `feat:`, `fix:`, `docs:`, `test:`, `data:`, `chore:` (https://www.conventionalcommits.org/).

---

## 13. Troubleshooting

| Problem | Likely cause / fix |
|---|---|
| `/readyz` returns 503 | DB not created / registry not seeded, or message model file missing |
| Every result is `UNVERIFIED` | Brand not in registry, or the claimed brand wasn't detected. Check aliases |
| `degraded: true` on every check | RDAP slow or blocked; check timeouts, network, and breaker state in Jaeger |
| Phone numbers fail to parse | Pass the default region (`IN`) and test odd formats (`098765…`, `+91-…`, spaces) |
| UPI regex matches emails | Filter by known UPI handle suffixes or by surrounding context |
| RDAP returns 404 for a TLD | That TLD may lack RDAP. Return `failed`, not "safe". Consider a documented fallback |
| Tests flaky | An external call isn't mocked. Mock all outbound HTTP |
| Audit verify fails after a crash | Partial last line; truncate the incomplete line and re-verify |
