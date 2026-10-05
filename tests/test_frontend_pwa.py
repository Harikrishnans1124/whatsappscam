"""Tests for frontend static files, PWA manifest/service worker, and multilingual checks."""

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client():
    return TestClient(app)


def test_frontend_index_serves_html(client: TestClient):
    resp = client.get("/")
    assert resp.status_code == 200
    assert "TrustShop" in resp.text
    assert "manifest.json" in resp.text
    assert "langSelect" in resp.text
    assert "payeeHelpBtn" in resp.text


def test_pwa_manifest(client: TestClient):
    resp = client.get("/manifest.json")
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "TrustShop AI - Scam Detector"
    assert data["display"] == "standalone"
    assert len(data["icons"]) >= 2


def test_pwa_service_worker(client: TestClient):
    resp = client.get("/sw.js")
    assert resp.status_code == 200
    assert "CACHE_NAME" in resp.text
    assert "addEventListener" in resp.text


def test_pwa_icons(client: TestClient):
    resp192 = client.get("/icons/icon-192.png")
    assert resp192.status_code == 200
    assert resp192.headers.get("content-type") == "image/png"

    resp512 = client.get("/icons/icon-512.png")
    assert resp512.status_code == 200
    assert resp512.headers.get("content-type") == "image/png"


def test_check_in_malayalam(client: TestClient):
    resp = client.post(
        "/v1/checks",
        json={
            "claimed_brand": "Flipkart",
            "phone_number": "+91 98765 43210",
            "language": "ml",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["verdict"] in ("SUSPICIOUS", "LIKELY_SCAM")
    # Verify Malayalam text in summary and reasons
    assert any("ലിസ്റ്റിൽ ഉള്ളതല്ല" in r["text"] or "പൊരുത്തപ്പെടുന്നില്ല" in r["text"] for r in data["reasons"])
    assert "Flipkart" in data["summary"]
    assert len(data["advice"]) > 0


def test_check_in_hindi(client: TestClient):
    resp = client.post(
        "/v1/checks",
        json={
            "claimed_brand": "Flipkart",
            "phone_number": "+91 98765 43210",
            "language": "hi",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["verdict"] in ("SUSPICIOUS", "LIKELY_SCAM")
    # Verify Hindi text in summary and reasons
    assert any("आधिकारिक सूची में नहीं है" in r["text"] or "मेल नहीं खाता" in r["text"] for r in data["reasons"])
    assert "Flipkart" in data["summary"]
    assert len(data["advice"]) > 0
