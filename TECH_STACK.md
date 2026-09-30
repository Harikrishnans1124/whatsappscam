# Tech Stack: what, why, where, how, and where to learn

For each technology: **what it does here**, **where in the repo**, **how to do it** (with a minimal snippet), and **references**.

Contents: [FastAPI](#1-fastapi) · [Pydantic](#2-pydantic-v2) · [Redis](#3-redis) · [LightGBM](#4-lightgbm--imbalanced-learning) · [Embeddings + FAISS](#5-sentence-transformers--faiss) · [asyncio + circuit breaker](#6-asyncio-timeouts--circuit-breaker) · [Hash-chained audit log](#7-hash-chained-audit-log) · [OpenTelemetry + Jaeger](#8-opentelemetry--jaeger) · [RFC 9457](#9-rfc-9457-problem-details) · [pytest](#10-pytest) · [k6](#11-k6-load-testing) · [Docker Compose](#12-docker--docker-compose) · [Streamlit](#13-streamlit) · [Books and courses](#14-books-and-general-reading)

---

## 1. FastAPI
- **What:** async Python web framework; serves the scoring API and auto-generates `/docs`.
- **Where:** `app/main.py`
- **How:**
```python
from fastapi import FastAPI, Header
app = FastAPI(title="TrustShop AI")

@app.post("/v1/orders/score")
async def score(order: OrderRequest, idempotency_key: str = Header(...)):
    ...
```
- **Run:** `uvicorn app.main:app --reload`
- **References:**
  - Docs / tutorial: https://fastapi.tiangolo.com/tutorial/
  - Async explained: https://fastapi.tiangolo.com/async/
  - Uvicorn: https://www.uvicorn.org/

## 2. Pydantic v2
- **What:** request/response validation and typing.
- **Where:** `app/schemas.py`
- **How:**
```python
from pydantic import BaseModel, Field
class Item(BaseModel):
    sku: str
    title: str
    price: float = Field(gt=0)
```
- **References:** https://docs.pydantic.dev/latest/ · JSON Schema: https://json-schema.org/understanding-json-schema

## 3. Redis
- **What:** in-memory store used for velocity counters, account history, and idempotency records.
- **Where:** `app/enrichment.py`, `app/idempotency.py`
- **How (velocity counter):**
```python
# fixed-window counter: orders per device in 10 minutes
key = f"vel:dev:{fingerprint}:10m"
pipe = r.pipeline()
pipe.incr(key)
pipe.expire(key, 600, nx=True)   # set TTL only on first increment
count, _ = await pipe.execute()
```
- **Idempotency:** `SET idem:{key} {json} NX EX 86400`
- **Library:** `redis-py` (use `redis.asyncio`).
- **References:**
  - Redis docs: https://redis.io/docs/latest/
  - Rate-limiting / counter patterns: https://redis.io/glossary/rate-limiting/
  - redis-py: https://redis.readthedocs.io/
  - Free course: https://university.redis.io/

## 4. LightGBM + imbalanced learning
- **What:** gradient-boosted trees; predicts fraud probability for the behavioral scorer.
- **Where:** `training/train_behavioral.ipynb`, `app/agents/behavioral.py`, `training/features.py`
- **How (train + evaluate):**
```python
import lightgbm as lgb
from sklearn.metrics import average_precision_score, precision_recall_curve

model = lgb.LGBMClassifier(n_estimators=600, learning_rate=0.05,
                           scale_pos_weight=neg/pos, subsample=0.8, colsample_bytree=0.8)
model.fit(X_train, y_train, eval_set=[(X_val, y_val)], callbacks=[lgb.early_stopping(50)])

p = model.predict_proba(X_val)[:, 1]
print("PR-AUC:", average_precision_score(y_val, p))
```
- **Rules of thumb:**
  - Split **by time**, not randomly.
  - Report **PR-AUC** and **recall at fixed precision**, not accuracy.
  - Same feature code for training and serving (`features.py`).
  - Save with `joblib.dump(model, "models/behavioral.joblib")`.
- **References:**
  - LightGBM docs: https://lightgbm.readthedocs.io/
  - scikit-learn, metrics for imbalanced data: https://scikit-learn.org/stable/modules/model_evaluation.html#precision-recall-f-measure-metrics
  - Calibration: https://scikit-learn.org/stable/modules/calibration.html
  - imbalanced-learn: https://imbalanced-learn.org/stable/
  - Dataset: https://www.kaggle.com/c/ieee-fraud-detection (browse the public notebooks for feature ideas)

## 5. sentence-transformers + FAISS
- **What:** turn product text into vectors and find nearest "counterfeit-like" exemplars.
- **Where:** `app/agents/catalog.py`, `training/build_catalog_index.py`
- **How:**
```python
from sentence_transformers import SentenceTransformer
import faiss, numpy as np

model = SentenceTransformer("all-MiniLM-L6-v2")

# build (offline)
emb = model.encode(examples, normalize_embeddings=True).astype("float32")
index = faiss.IndexFlatIP(emb.shape[1])   # inner product == cosine on normalized vectors
index.add(emb)
faiss.write_index(index, "models/catalog.faiss")

# query (online)
q = model.encode([title], normalize_embeddings=True).astype("float32")
sim, _ = index.search(q, k=1)
catalog_score = 1.0 - float(sim[0][0])
```
- **Notes:** load model and index **once at startup**, not per request. Exact search (`IndexFlatIP`) is fine for thousands of vectors.
- **References:**
  - SBERT docs: https://www.sbert.net/
  - FAISS wiki: https://github.com/facebookresearch/faiss/wiki
  - Model card: https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2

## 6. asyncio timeouts + circuit breaker
- **What:** run scorers in parallel, cap each one's time, and stop calling a scorer that keeps failing.
- **Where:** `app/breaker.py`, used by `app/main.py`
- **How:**
```python
import asyncio, pybreaker

breakers = {name: pybreaker.CircuitBreaker(fail_max=5, reset_timeout=30) for name in ("merchant","catalog","behavioral")}

async def guarded(name, coro_fn, *args, timeout=0.080):
    try:
        # pybreaker.call_async needs tornado; simplest is to check state + record manually
        if breakers[name].current_state == "open":
            return None
        return await asyncio.wait_for(coro_fn(*args), timeout)
    except Exception:
        # count the failure
        try: breakers[name].call(lambda: (_ for _ in ()).throw(RuntimeError()))
        except Exception: pass
        return None

results = await asyncio.gather(
    guarded("merchant", merchant_score, order),
    guarded("catalog", catalog_score, order),
    guarded("behavioral", behavioral_score, order, feats),
)
```
  > `pybreaker`'s async support is awkward. If it fights you, write a ~30-line breaker class yourself (closed → open after N failures → half-open after a cooldown). That's a great learning exercise and a good interview talking point.
- **CPU-bound models:** LightGBM/SBERT inference blocks the event loop. Run them with `await asyncio.to_thread(...)` or `loop.run_in_executor`.
- **References:**
  - Circuit breaker pattern (Fowler): https://martinfowler.com/bliki/CircuitBreaker.html
  - Azure architecture pattern: https://learn.microsoft.com/en-us/azure/architecture/patterns/circuit-breaker
  - asyncio docs (`wait_for`, `gather`, `to_thread`): https://docs.python.org/3/library/asyncio-task.html
  - pybreaker: https://github.com/danielfm/pybreaker

## 7. Hash-chained audit log
- **What:** each log entry includes the previous entry's hash, making tampering detectable.
- **Where:** `app/audit.py`, `scripts/verify_audit.py`
- **How:**
```python
import hashlib, json

def canonical(obj) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":")).encode()

def append(entry: dict, prev_hash: str) -> dict:
    h = hashlib.sha256(prev_hash.encode() + canonical(entry)).hexdigest()
    return {**entry, "prev_hash": prev_hash, "entry_hash": h}
```
- **Verify:** re-compute from the first entry (genesis `prev_hash = "0"*64`) and compare every `entry_hash`.
- **Concurrency:** appends must be serialized (single writer, lock, or a Redis/DB transaction) so two requests don't share the same `prev_hash`.
- **References:**
  - Hash chains / Merkle trees (intro): https://en.wikipedia.org/wiki/Merkle_tree
  - Certificate Transparency (real-world append-only logs): https://certificate.transparency.dev/
  - Immutable storage: https://docs.aws.amazon.com/AmazonS3/latest/userguide/object-lock.html

## 8. OpenTelemetry + Jaeger
- **What:** distributed tracing so you can see where every millisecond of a request went.
- **Where:** `app/telemetry.py`; Jaeger in `docker-compose.yml`
- **How:**
```python
from opentelemetry import trace
tracer = trace.get_tracer("trustshop")

with tracer.start_as_current_span("agent.merchant") as span:
    result = await merchant_score(order)
    span.set_attribute("score", result["score"])
```
  Auto-instrument FastAPI with `opentelemetry-instrumentation-fastapi`; export via OTLP to Jaeger (UI at `:16686`).
- **References:**
  - OTel Python: https://opentelemetry.io/docs/languages/python/
  - FastAPI instrumentation: https://opentelemetry-python-contrib.readthedocs.io/en/latest/instrumentation/fastapi/fastapi.html
  - Jaeger: https://www.jaegertracing.io/docs/

## 9. RFC 9457 (Problem Details)
- **What:** standard JSON format for HTTP API errors.
- **Where:** `app/errors.py`
- **How:** register exception handlers returning `JSONResponse(..., media_type="application/problem+json")` with `type`, `title`, `status`, `detail`, `instance`.
- **References:** https://www.rfc-editor.org/rfc/rfc9457 · FastAPI exception handlers: https://fastapi.tiangolo.com/tutorial/handling-errors/

## 10. pytest
- **What:** unit and integration tests. Key tests: decision thresholds, veto rule, degraded-mode never approves, timeout fallback, idempotency replay/conflict, audit chain verification.
- **Where:** `tests/`
- **How:**
```python
@pytest.mark.parametrize("trust,expected", [(0.95,"APPROVE"),(0.70,"STEP_UP"),(0.30,"HOLD")])
def test_thresholds(trust, expected):
    assert decide(trust=trust, degraded=False, scores=[0.9,0.9,0.9]).decision == expected
```
  Use `httpx.AsyncClient` with FastAPI for endpoint tests.
- **References:** https://docs.pytest.org/ · FastAPI testing: https://fastapi.tiangolo.com/tutorial/testing/

## 11. k6 (load testing)
- **What:** generate load and measure p50/p99 latency and throughput.
- **Where:** `loadtest/score.js`
- **How:**
```javascript
import http from 'k6/http';
import { check } from 'k6';
export const options = {
  stages: [{ duration: '30s', target: 50 }, { duration: '1m', target: 200 }],
  thresholds: { http_req_duration: ['p(99)<120'] },
};
export default function () {
  const res = http.post('http://localhost:8000/v1/orders/score', JSON.stringify(payload()),
    { headers: { 'Content-Type': 'application/json', 'Idempotency-Key': `${__VU}-${__ITER}` } });
  check(res, { 'status 200': (r) => r.status === 200 });
}
```
  Record results in the README **with the machine specs**. Also test with a scorer artificially slowed to verify the fallback.
- **References:** https://grafana.com/docs/k6/latest/

## 12. Docker + Docker Compose
- **What:** one command to run API + Redis + Jaeger.
- **Where:** `Dockerfile`, `docker-compose.yml`
- **How:** services `api`, `redis`, `jaeger` (all-in-one image, expose `16686` UI and `4317` OTLP). Use a slim Python base image, install dependencies first (layer caching), copy `models/` in or mount as a volume.
- **References:** https://docs.docker.com/compose/ · Dockerfile best practices: https://docs.docker.com/build/building/best-practices/

## 13. Streamlit
- **What:** quick reviewer dashboard to see held orders and resolve them.
- **Where:** `dashboard/review_queue.py`
- **How:** call `GET /v1/holds` with `requests`, show a table, add buttons that `POST` to `/resolve`.
- **References:** https://docs.streamlit.io/

## 14. Books and general reading

| Resource | Why |
|---|---|
| *Designing Machine Learning Systems*, Chip Huyen | Serving, monitoring, drift, training/serving skew |
| *Designing Data-Intensive Applications*, Martin Kleppmann | Idempotency, logs, failure handling |
| System Design Primer: https://github.com/donnemartin/system-design-primer | Interview-oriented system design |
| Eugene Yan's blog: https://eugeneyan.com/ | Applied ML system write-ups |
| Stripe engineering blog: https://stripe.com/blog/engineering | Fraud (Radar), idempotency, API design |
| Google "Rules of Machine Learning": https://developers.google.com/machine-learning/guides/rules-of-ml | Practical ML engineering rules |
| OWASP API Security Top 10: https://owasp.org/API-Security/ | Securing the endpoint |
