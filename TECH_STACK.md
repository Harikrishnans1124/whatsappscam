# Tech Stack: what, why, where, how, and where to learn

For each technology: **what it does here**, **where in the repo**, **how to do it** (minimal snippet), and **references**.

Contents: [FastAPI](#1-fastapi) · [Pydantic](#2-pydantic-v2) · [phonenumbers](#3-phonenumbers) · [Registry + SQLite](#4-sqlite--sqlalchemy-registry-and-reports) · [tldextract + rapidfuzz](#5-tldextract--rapidfuzz-domains-and-names) · [RDAP](#6-rdap-domain-age) · [Message classifier](#7-message-scorer-rules--tf-idf--logistic-regression) · [Redis](#8-redis-cache-and-rate-limit) · [asyncio + breaker](#9-asyncio-timeouts--circuit-breaker) · [HMAC hashing + audit chain](#10-hmac-hashing-and-the-audit-chain) · [SSRF safety](#11-ssrf-and-safe-outbound-requests) · [OpenTelemetry](#12-opentelemetry--jaeger) · [RFC 9457](#13-rfc-9457-problem-details) · [i18n](#14-explanations-and-translations) · [Frontend/PWA](#15-frontend-pwa) · [pytest](#16-pytest-and-mocking-external-services) · [Docker](#17-docker--docker-compose) · [Streamlit](#18-streamlit-admin) · [Stretch tech](#19-stretch-technologies) · [Books](#20-books-and-general-reading)

---

## 1. FastAPI
- **What:** async Python web framework; serves the API and the frontend files, and auto-generates `/docs`.
- **Where:** `app/main.py`
- **How:**
```python
from fastapi import FastAPI
app = FastAPI(title="TrustShop AI")

@app.post("/v1/checks")
async def create_check(body: CheckRequest) -> CheckResponse:
    ctx = extract(body)
    results = await run_scorers(ctx)
    return decide_and_explain(ctx, results)
```
- **Run:** `uvicorn app.main:app --reload`
- **References:** https://fastapi.tiangolo.com/tutorial/ · async explained: https://fastapi.tiangolo.com/async/ · static files: https://fastapi.tiangolo.com/tutorial/static-files/

## 2. Pydantic v2
- **What:** request/response validation and typing.
- **Where:** `app/schemas.py`
- **How:**
```python
from pydantic import BaseModel, Field, model_validator

class Payment(BaseModel):
    upi_id: str | None = None
    display_name: str | None = None
    amount: float | None = Field(default=None, gt=0)

class CheckRequest(BaseModel):
    claimed_brand: str | None = None
    phone_number: str | None = None
    message_text: str | None = Field(default=None, max_length=5000)
    urls: list[str] = Field(default_factory=list, max_length=5)
    payment: Payment | None = None
    language: str = "en"

    @model_validator(mode="after")
    def need_something(self):
        if not (self.phone_number or self.message_text or self.urls or (self.payment and self.payment.upi_id)):
            raise ValueError("Provide at least one of phone_number, message_text, urls, payment.upi_id")
        return self
```
- **References:** https://docs.pydantic.dev/latest/ · validators: https://docs.pydantic.dev/latest/concepts/validators/

## 3. phonenumbers
- **What:** parse, validate, and normalize phone numbers (Python port of Google's libphonenumber).
- **Where:** `app/extraction.py`, `app/agents/number.py`
- **How:**
```python
import phonenumbers

def normalize_phone(raw: str, region="IN"):
    try:
        num = phonenumbers.parse(raw, region)
    except phonenumbers.NumberParseException:
        return None
    return {
        "valid": phonenumbers.is_valid_number(num),
        "e164": phonenumbers.format_number(num, phonenumbers.PhoneNumberFormat.E164),
        "type": phonenumbers.number_type(num),   # MOBILE, TOLL_FREE, FIXED_LINE...
    }
```
- **References:** https://pypi.org/project/phonenumbers/ · https://github.com/google/libphonenumber

## 4. SQLite + SQLAlchemy (registry and reports)
- **What:** stores the brand registry and community reports. SQLite needs no server and is fine for this scale.
- **Where:** `app/registry.py`, `app/reports.py`, `scripts/seed_registry.py`
- **How:** tables `brands`, `brand_sources`, `reports`. Keep list-like fields (domains, phones) in child tables or JSON columns. `seed_registry.py` loads `registry/brands.yaml` into the DB (and rejects entries without a source URL and date).
- **Registry practice:** treat it like a dataset. Every entry needs a source and a verification date, and a freshness script flags old entries.
- **References:** SQLAlchemy 2.0 tutorial: https://docs.sqlalchemy.org/en/20/tutorial/ · SQLite docs: https://www.sqlite.org/docs.html · PyYAML: https://pyyaml.org/wiki/PyYAMLDocumentation

## 5. tldextract + rapidfuzz (domains and names)
- **What:** `tldextract` gets the registrable domain correctly (handles `co.in`, `.shop`, etc.). `rapidfuzz` does fast fuzzy string matching for lookalike domains and payee names.
- **Where:** `app/agents/domain.py`, `app/agents/payment.py`
- **How:**
```python
import tldextract
from rapidfuzz import fuzz
from rapidfuzz.distance import Levenshtein

def registrable(url):
    e = tldextract.extract(url)
    return f"{e.domain}.{e.suffix}", e.domain

def is_lookalike(url, official_domains, brand_slug_tokens):
    reg, label = registrable(url)
    if reg in official_domains:
        return False                                  # it IS official
    for off in official_domains:
        off_label = off.split(".")[0]
        if Levenshtein.distance(label, off_label) <= 2: return True       # typo
        if off_label in label.replace("-", ""): return True               # acmefootwearoutlet
    return any(tok in label for tok in brand_slug_tokens)                 # brand name stuffing

def name_matches(payee, legal_names, threshold=80):
    return any(fuzz.token_set_ratio(payee.lower(), n.lower()) >= threshold for n in legal_names)
```
- **Unicode look-alikes:** convert internationalized domains to Punycode (`domain.encode("idna")`) and flag mixed scripts.
- **References:** tldextract: https://github.com/john-kurkowski/tldextract · RapidFuzz: https://rapidfuzz.github.io/RapidFuzz/ · Unicode confusables (UTS #39): https://www.unicode.org/reports/tr39/

## 6. RDAP (domain age)
- **What:** the modern, JSON-based replacement for WHOIS. Used to get a domain's registration date.
- **Where:** `app/agents/domain.py`, `app/safe_fetch.py`, cached in Redis
- **How:**
```python
import httpx, datetime as dt

async def domain_age_days(domain: str, client: httpx.AsyncClient):
    r = await client.get(f"https://rdap.org/domain/{domain}", follow_redirects=True, timeout=2.5)
    r.raise_for_status()
    events = r.json().get("events", [])
    reg = next((e["eventDate"] for e in events if e.get("eventAction") == "registration"), None)
    if not reg:
        return None
    return (dt.datetime.now(dt.timezone.utc) - dt.datetime.fromisoformat(reg.replace("Z", "+00:00"))).days
```
- **Caveats:** RDAP coverage differs by TLD. Handle "not found" and missing events (return `None`, mark the scorer `failed`, not "safe"). Be polite: cache for 24 h and respect rate limits.
- **References:** ICANN RDAP: https://www.icann.org/rdap · RFC 9083 (JSON responses): https://www.rfc-editor.org/rfc/rfc9083 · rdap.org: https://about.rdap.org/ · httpx: https://www.python-httpx.org/

## 7. Message scorer (rules + TF-IDF + logistic regression)
- **What:** detects scam tactics in pasted chats.
- **Where:** `app/agents/message.py`, `training/message_classifier.ipynb`
- **How (rules):**
```python
import re
RULES = {
  "URGENCY_PRESSURE": r"\b(today only|last \d+ (pieces|items)|hurry|limited stock|offer ends)\b",
  "ADVANCE_PAYMENT_REQUEST": r"\b(advance|pay (now|first)|token amount)\b",
  "OTP_REQUEST": r"\botp\b",
  "REMOTE_ACCESS_REQUEST": r"\b(anydesk|teamviewer|quicksupport)\b",
}
hits = [code for code, pat in RULES.items() if re.search(pat, text, re.I)]
```
- **How (ML):**
```python
from sklearn.pipeline import make_pipeline
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
clf = make_pipeline(TfidfVectorizer(ngram_range=(1,2), min_df=2), LogisticRegression(class_weight="balanced", max_iter=1000))
clf.fit(X_train, y_train)
```
  Evaluate with precision/recall and PR-AUC, not accuracy. Save with `joblib`.
- **Honest limits:** the public data is SMS spam; your target is WhatsApp seller scams in multiple languages. Rules carry most weight in v1. Build your own labeled set and report results on it.
- **References:** scikit-learn text tutorial: https://scikit-learn.org/stable/tutorial/text_analytics/working_with_text_data.html · UCI SMS Spam Collection: https://archive.ics.uci.edu/dataset/228/sms+spam+collection · metrics: https://scikit-learn.org/stable/modules/model_evaluation.html

## 8. Redis (cache and rate limit)
- **What:** caches RDAP lookups; per-IP rate limits.
- **Where:** `app/cache.py`
- **How:**
```python
# cache
await r.set(f"rdap:{domain}", json.dumps(result), ex=86400)

# fixed-window rate limit: 30 requests/minute per IP
key = f"rl:{ip}:{int(time.time() // 60)}"
n = await r.incr(key)
if n == 1: await r.expire(key, 60)
if n > 30: raise RateLimited()
```
- **References:** https://redis.io/docs/latest/ · redis-py (`redis.asyncio`): https://redis.readthedocs.io/ · free course: https://university.redis.io/

## 9. asyncio timeouts + circuit breaker
- **What:** run scorers in parallel, cap each one's time, and stop calling a service that keeps failing.
- **Where:** `app/breaker.py`
- **How:**
```python
import asyncio

async def guarded(name, coro, timeout_s):
    if breakers[name].is_open():
        return {"status": "failed", "risk": None, "reasons": ["SCORER_UNAVAILABLE"]}
    try:
        res = await asyncio.wait_for(coro, timeout_s)
        breakers[name].record_success()
        return res
    except Exception:
        breakers[name].record_failure()
        return {"status": "failed", "risk": None, "reasons": ["SCORER_UNAVAILABLE"]}

results = await asyncio.gather(
    guarded("brand_identity", brand_scorer(ctx), 0.15),
    guarded("payment",        payment_scorer(ctx), 0.15),
    guarded("message",        message_scorer(ctx), 0.15),
    guarded("domain",         domain_scorer(ctx), 2.5),
    guarded("number",         number_scorer(ctx), 0.15),
)
```
  Write the small `Breaker` class yourself (closed → open after N failures → half-open after a cooldown, ~30 lines). It's a good learning exercise and interview story.
- **CPU-bound work** (model prediction) → `await asyncio.to_thread(...)`.
- **References:** Fowler's circuit breaker: https://martinfowler.com/bliki/CircuitBreaker.html · Azure pattern: https://learn.microsoft.com/en-us/azure/architecture/patterns/circuit-breaker · asyncio tasks: https://docs.python.org/3/library/asyncio-task.html

## 10. HMAC hashing and the audit chain
- **HMAC for identifiers:** lets you look up "has this number been reported?" without storing the number.
```python
import hmac, hashlib
def h(value: str) -> str:
    return hmac.new(SECRET, value.encode(), hashlib.sha256).hexdigest()
```
  A plain unsalted hash of a phone number is easy to reverse by brute force (there are only so many numbers), so use a **keyed** hash (HMAC) and keep the key secret.
- **Audit chain:** each entry stores the previous entry's hash.
```python
import json
def canonical(o): return json.dumps(o, sort_keys=True, separators=(",", ":")).encode()
def append(entry, prev_hash):
    eh = hashlib.sha256(prev_hash.encode() + canonical(entry)).hexdigest()
    return {**entry, "prev_hash": prev_hash, "entry_hash": eh}
```
  `scripts/verify_audit.py` recomputes the chain from a genesis hash. Serialize appends (single writer or lock).
- **References:** Python `hmac`: https://docs.python.org/3/library/hmac.html · Merkle/hash chains: https://en.wikipedia.org/wiki/Merkle_tree · Certificate Transparency: https://certificate.transparency.dev/ · S3 Object Lock: https://docs.aws.amazon.com/AmazonS3/latest/userguide/object-lock.html

## 11. SSRF and safe outbound requests
- **What:** SSRF is when an attacker makes your server request internal or unintended addresses.
- **Where:** `app/safe_fetch.py`
- **v1 rule:** never fetch a URL the user typed. Only call a fixed allowlist (RDAP, Safe Browsing). Validate hostnames you build into requests.
- **If you add page fetching later (stretch):** resolve DNS and block private/loopback/link-local ranges, allow only http/https, cap redirects, size, and time, and don't send cookies or credentials.
- **References:** OWASP SSRF Prevention Cheat Sheet: https://cheatsheetseries.owasp.org/cheatsheets/Server_Side_Request_Forgery_Prevention_Cheat_Sheet.html · OWASP API Security Top 10: https://owasp.org/API-Security/

## 12. OpenTelemetry + Jaeger
- **What:** tracing to see where each millisecond goes (especially the slow domain lookup).
- **Where:** `app/telemetry.py`; Jaeger in `docker-compose.yml`
- **How:**
```python
from opentelemetry import trace
tracer = trace.get_tracer("trustshop")
with tracer.start_as_current_span("agent.domain") as span:
    res = await domain_scorer(ctx)
    span.set_attribute("status", res["status"])    # never put PII in attributes
```
  Auto-instrument FastAPI with `opentelemetry-instrumentation-fastapi`; export via OTLP to Jaeger (UI on `:16686`).
- **References:** https://opentelemetry.io/docs/languages/python/ · FastAPI instrumentation: https://opentelemetry-python-contrib.readthedocs.io/en/latest/instrumentation/fastapi/fastapi.html · Jaeger: https://www.jaegertracing.io/docs/

## 13. RFC 9457 (Problem Details)
- **What:** standard JSON format for HTTP API errors.
- **Where:** `app/errors.py`
- **How:** exception handlers return `JSONResponse(..., media_type="application/problem+json")` with `type`, `title`, `status`, `detail`, `instance`.
- **References:** https://www.rfc-editor.org/rfc/rfc9457 · https://fastapi.tiangolo.com/tutorial/handling-errors/

## 14. Explanations and translations
- **What:** reason code → plain-language sentence, per language.
- **Where:** `app/explain.py`, `app/i18n/en.yaml`, `ml.yaml`, `hi.yaml`
- **How:**
```yaml
# en.yaml
BRAND_CHANNEL_MISMATCH: "This number is not on {brand}'s official contact list."
PERSONAL_PAYEE: "The payment would go to a person's account, not to the company."
```
```python
text = i18n[lang].get(code) or i18n["en"][code]
```
  Have a native speaker review Malayalam and Hindi wording. Short, calm, concrete sentences work best for non-technical users.
- **References:** Python `string.Template`/format strings: https://docs.python.org/3/library/string.html · plain-language guidance: https://www.plainlanguage.gov/

## 15. Frontend (PWA)
- **What:** a simple mobile-first page with inputs (number, paste chat, link, UPI ID and payee name) and a clear result card.
- **Where:** `frontend/index.html`, `app.js`, `manifest.json`, served by FastAPI static files.
- **How:** plain HTML + `fetch("/v1/checks", ...)`. Colour-code verdicts but also use words and icons (don't rely on colour alone). Add a `manifest.json` and a service worker to make it installable.
- **UX notes:** explain where to find the payee name in the UPI app; show the "Open the brand's official site" action first; keep sentences short.
- **References:** MDN PWA guide: https://developer.mozilla.org/en-US/docs/Web/Progressive_web_apps · Fetch API: https://developer.mozilla.org/en-US/docs/Web/API/Fetch_API

## 16. pytest and mocking external services
- **What:** unit and integration tests. External calls (RDAP) are mocked so tests are fast and deterministic.
- **Where:** `tests/`
- **How:**
```python
@pytest.mark.parametrize("risk,matched,expected", [
    (0.20, True,  "MATCHES_OFFICIAL"),
    (0.20, False, "UNVERIFIED"),
    (0.50, True,  "SUSPICIOUS"),
    (0.80, False, "LIKELY_SCAM"),
])
def test_verdict(risk, matched, expected):
    assert decide(risk=risk, registry_match=matched, degraded=False).verdict == expected
```
  Use `httpx.AsyncClient` against the FastAPI app, and `respx` or `pytest-httpx` to mock outgoing calls.
- **References:** https://docs.pytest.org/ · https://fastapi.tiangolo.com/tutorial/testing/ · respx: https://lundberg.github.io/respx/

## 17. Docker + Docker Compose
- **What:** one command to run API + Redis + Jaeger.
- **Where:** `Dockerfile`, `docker-compose.yml`
- **How:** services `api`, `redis`, `jaeger` (all-in-one image; ports `16686` UI, `4317` OTLP). Slim Python base image, install dependencies before copying code (layer cache), mount `data/` as a volume for SQLite.
- **References:** https://docs.docker.com/compose/ · https://docs.docker.com/build/building/best-practices/

## 18. Streamlit (admin)
- **What:** small admin UI to add/edit registry entries, see stale entries, and review reports.
- **Where:** `dashboard/admin.py`
- **How:** call admin endpoints with the API key; table of brands with "verified_on" ages, a form to add an entry (source URL required), and a report queue.
- **References:** https://docs.streamlit.io/

## 19. Stretch technologies
| Feature | Tech | Reference |
|---|---|---|
| WhatsApp bot | WhatsApp Cloud API (needs Meta business setup and approval) | https://developers.facebook.com/docs/whatsapp/cloud-api |
| Screenshot → text | Tesseract (`pytesseract`) or EasyOCR | https://github.com/tesseract-ocr/tesseract · https://github.com/JaidedAI/EasyOCR |
| Multilingual message understanding | `sentence-transformers` multilingual models | https://www.sbert.net/docs/sentence_transformer/pretrained_models.html |
| Reputation of URLs | Google Safe Browsing / Web Risk | https://developers.google.com/safe-browsing |
| Safe page analysis | SSRF-safe fetcher + HTML parsing (`BeautifulSoup`) | https://www.crummy.com/software/BeautifulSoup/bs4/doc/ |

## 20. Books and general reading

| Resource | Why |
|---|---|
| *Designing Data-Intensive Applications*, Martin Kleppmann | Failure handling, logs, caching |
| *Designing Machine Learning Systems*, Chip Huyen | Evaluation, data issues, monitoring |
| Google "Rules of Machine Learning": https://developers.google.com/machine-learning/guides/rules-of-ml | Practical ML engineering rules |
| System Design Primer: https://github.com/donnemartin/system-design-primer | Interview-oriented design |
| OWASP API Security Top 10: https://owasp.org/API-Security/ | Securing the API |
| Cybercrime reporting (India): https://cybercrime.gov.in | Understand what victims are told to do |
| NPCI UPI safety awareness: https://www.npci.org.in | How UPI payee names and handles work from the user's side |
