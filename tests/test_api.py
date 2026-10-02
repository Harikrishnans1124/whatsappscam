"""Integration tests for FastAPI endpoints in app.main."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.registry import init_db
from scripts.seed_registry import seed_registry

PROJECT_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def client():
    # Ensure DB is seeded
    init_db()
    seed_registry(PROJECT_ROOT / "registry" / "brands.yaml")
    with TestClient(app) as test_client:
        yield test_client


class TestAPIEndpoints:
    def test_healthz(self, client):
        res = client.get("/healthz")
        assert res.status_code == 200
        assert res.json() == {"status": "ok"}

    def test_readyz(self, client):
        res = client.get("/readyz")
        assert res.status_code == 200
        assert res.json() == {"status": "ready"}

    def test_list_brands(self, client):
        res = client.get("/v1/brands")
        assert res.status_code == 200
        data = res.json()
        assert isinstance(data, list)
        slugs = [b["slug"] for b in data]
        assert "flipkart" in slugs
        assert "amazon-india" in slugs
        assert "myntra" in slugs

    def test_get_single_brand(self, client):
        res = client.get("/v1/brands/flipkart")
        assert res.status_code == 200
        data = res.json()
        assert data["slug"] == "flipkart"
        assert data["name"] == "Flipkart"
        assert "flipkart.com" in data["official_domains"]
        assert len(data["sources"]) > 0

    def test_get_nonexistent_brand_rfc9457_error(self, client):
        res = client.get("/v1/brands/nonexistent-brand-slug-xyz")
        assert res.status_code == 404
        assert "application/problem+json" in res.headers.get("content-type", "")
        data = res.json()
        assert data["status"] == 404
        assert data["title"] == "Not Found"
        assert "not found in registry" in data["detail"]

    def test_check_matches_official(self, client):
        payload = {
            "claimed_brand": "Flipkart",
            "phone_number": "+91 1800 202 9898",
            "urls": ["https://flipkart.com/deal"],
        }
        res = client.post("/v1/checks", json=payload)
        assert res.status_code == 200
        data = res.json()
        assert data["verdict"] == "MATCHES_OFFICIAL"
        assert data["risk_score"] == 0.0
        assert "BRAND_CHANNEL_MATCH" in data["reason_codes"]
        assert data["brand"]["in_registry"] is True
        assert len(data["advice"]) > 0
        assert data["latency_ms"] >= 0

    def test_check_impersonation_mismatch(self, client):
        payload = {
            "claimed_brand": "Flipkart",
            "phone_number": "+91 98765 43210",  # Fake mobile
        }
        res = client.post("/v1/checks", json=payload)
        assert res.status_code == 200
        data = res.json()
        assert data["verdict"] in {"SUSPICIOUS", "LIKELY_SCAM"}
        assert data["risk_score"] >= 0.55
        assert "BRAND_CHANNEL_MISMATCH" in data["reason_codes"]

    def test_check_unknown_brand(self, client):
        payload = {
            "claimed_brand": "UnregisteredSmallShop123",
            "phone_number": "+91 98765 43210",
        }
        res = client.post("/v1/checks", json=payload)
        assert res.status_code == 200
        data = res.json()
        assert data["verdict"] == "UNVERIFIED"
        assert "BRAND_NOT_IN_REGISTRY" in data["reason_codes"]

    def test_validation_error_rfc9457(self, client):
        # Empty payload
        res = client.post("/v1/checks", json={})
        assert res.status_code == 422
        assert "application/problem+json" in res.headers.get("content-type", "")
        data = res.json()
        assert data["status"] == 422
        assert data["title"] == "Invalid request body"
        assert "Provide at least one of" in data["detail"]

    def test_frontend_page_served(self, client):
        res = client.get("/")
        assert res.status_code == 200
        assert "TrustShop" in res.text
        assert "checkForm" in res.text
