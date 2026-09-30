# Development Guide

How to set up, run, train, test, and benchmark TrustShop AI on your own machine.

---

## 1. Prerequisites

| Tool | Version | Used for |
|---|---|---|
| Python | 3.11+ | API and training |
| Docker + Docker Compose | recent | Redis, Jaeger, full stack |
| k6 | recent | load testing (https://grafana.com/docs/k6/latest/set-up/install-k6/) |
| Kaggle account | n/a | downloading IEEE-CIS data |
| Git | n/a | version control |

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
redis>=5
lightgbm
scikit-learn
joblib
numpy
pandas
sentence-transformers
faiss-cpu
pybreaker
pyyaml
opentelemetry-api
opentelemetry-sdk
opentelemetry-exporter-otlp
opentelemetry-instrumentation-fastapi
```

Suggested `requirements-dev.txt`:

```
pytest
pytest-asyncio
httpx
imbalanced-learn
jupyter
matplotlib
streamlit
requests
ruff
```

---

## 3. Get the data and train the model

1. Create a Kaggle API token (Kaggle → Account → *Create New Token*) and place `kaggle.json` in `~/.kaggle/`.
2. Download the dataset:
   ```bash
   pip install kaggle
   kaggle competitions download -c ieee-fraud-detection -p data/
   unzip data/ieee-fraud-detection.zip -d data/
   ```
   You may need to accept the competition rules on the Kaggle website first.
3. Open `training/train_behavioral.ipynb` and run all cells. It should:
   - load and join `train_transaction.csv` + `train_identity.csv`
   - build features through `training/features.py`
   - split **by time**
   - train LightGBM with class weighting
   - print PR-AUC and recall at fixed precision, and plot the PR curve
   - save `models/behavioral.joblib`
4. Record the metrics in `docs/BUILD_LOG.md` and the README.

### Build the catalog index

```bash
python training/build_catalog_index.py
# reads training/counterfeit_examples.csv → writes models/catalog.faiss
```

The first run downloads the `all-MiniLM-L6-v2` model from Hugging Face (needs internet once).

---

## 4. Run the service

### Option A: full stack with Docker

```bash
docker compose up --build
```

| Service | URL |
|---|---|
| API | http://localhost:8000 |
| Swagger docs | http://localhost:8000/docs |
| Jaeger UI | http://localhost:16686 |
| Redis | localhost:6379 |

### Option B: API locally, Redis/Jaeger in Docker

```bash
docker compose up redis jaeger -d
export REDIS_URL=redis://localhost:6379/0
export OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317
uvicorn app.main:app --reload --port 8000
```

### Smoke test

```bash
curl http://localhost:8000/healthz
curl http://localhost:8000/readyz
```

Then try the example request from the [README](../README.md#using-the-api).

---

## 5. Configuration

`config/thresholds.yaml`:

```yaml
thresholds:
  approve: 0.88
  step_up: 0.50
weights:
  behavioral: 0.50
  merchant: 0.25
  catalog: 0.25
veto_below: 0.20
timeouts_ms:
  merchant: 80
  catalog: 80
  behavioral: 80
breaker:
  fail_max: 5
  reset_timeout_s: 30
idempotency_ttl_s: 86400
```

Environment variables:

| Variable | Default | Purpose |
|---|---|---|
| `REDIS_URL` | `redis://localhost:6379/0` | Redis connection |
| `MODEL_PATH` | `models/behavioral.joblib` | Behavioral model |
| `FAISS_PATH` | `models/catalog.faiss` | Catalog index |
| `AUDIT_PATH` | `data/audit.jsonl` | Audit log file |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | unset | Enables trace export |

---

## 6. Run tests

```bash
pytest -q
```

Minimum test coverage to aim for:

- Decision thresholds at boundaries (0.88, 0.50, 0.20 veto)
- Degraded mode never returns `APPROVE`
- Weight redistribution when one scorer is `None`
- Timeout: a deliberately slow scorer returns `None` within ~80 ms
- Breaker opens after N failures and recovers after the cooldown
- Idempotency: replay returns the same body; changed body returns `409`
- Audit chain: verifies clean, and detects a modified entry
- API validation errors are `application/problem+json`

Lint: `ruff check .`

---

## 7. Verify the audit log

```bash
python scripts/verify_audit.py data/audit.jsonl
# prints "OK: N entries verified" or the index of the first broken link
```

To prove it works, edit one line of the file by hand and run it again; it should report the break.

---

## 8. Load test

```bash
k6 run loadtest/score.js
```

Do it properly:

1. Run the API with the same setup you'll document (Docker, number of Uvicorn workers).
2. Warm up first (models loaded, Redis connected).
3. Run at increasing load and note where p99 crosses 120 ms.
4. Run again with one scorer artificially delayed (for example `await asyncio.sleep(0.2)` behind an env flag) and confirm requests still return `200` with `degraded: true`.
5. Record: machine (CPU/RAM), workers, requests/sec, p50, p99, error rate, degraded rate.
6. Put the table in the README and `docs/BUILD_LOG.md`.

Tips if latency is too high:
- Load models once at startup, never per request.
- Run CPU-bound inference via `asyncio.to_thread`.
- Use more Uvicorn workers (`--workers N`) or Gunicorn with Uvicorn workers.
- Batch or cache embeddings for repeated titles.
- Check the Jaeger trace to see which scorer dominates.

---

## 9. Dashboard

```bash
streamlit run dashboard/review_queue.py
```

Shows held orders from `GET /v1/holds` and lets a reviewer resolve them.

---

## 10. Git hygiene

`.gitignore` should include:

```
.venv/
data/
models/*.joblib
models/*.faiss
__pycache__/
.ipynb_checkpoints/
.env
```

Don't commit the Kaggle data or credentials. Commit small artifacts only, and document how to regenerate the model files (this guide).

Suggested commit style: `feat:`, `fix:`, `docs:`, `test:`, `chore:` (Conventional Commits, https://www.conventionalcommits.org/).

---

## 11. Troubleshooting

| Problem | Likely cause / fix |
|---|---|
| `/readyz` returns 503 | Model files missing (run the training steps) or Redis not reachable |
| Every response is `degraded: true` | Scorers exceed the 80 ms timeout; check Jaeger, make sure inference is off the event loop and models load at startup |
| `faiss` import error | Use `faiss-cpu` and a supported Python version |
| Slow first request | Model warm-up; call a dummy request at startup |
| Kaggle 403 | Accept the competition rules on the Kaggle site |
| Audit verify fails right after a crash | Partial last line written; truncate the incomplete line and re-verify |
