"""Tests for admin endpoints and authorization (X-API-Key)."""

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.main import app
from app.registry import get_brand_by_slug, get_session_factory, init_db

VALID_KEY = settings.get("admin_api_key", "dev-admin-key-change-me")


@pytest.fixture(autouse=True)
def setup_database():
    init_db()
    session_factory = get_session_factory()
    with session_factory() as session:
        b = get_brand_by_slug(session, "puma-india")
        if b:
            session.delete(b)
            session.commit()
    yield
    with session_factory() as session:
        b = get_brand_by_slug(session, "puma-india")
        if b:
            session.delete(b)
            session.commit()


@pytest.fixture
def client():
    return TestClient(app)


def test_admin_endpoints_require_api_key(client: TestClient):
    # No header
    resp = client.post("/v1/admin/brands", json={"slug": "test-brand"})
    assert resp.status_code == 403

    # Invalid header
    resp = client.post(
        "/v1/admin/brands",
        json={"slug": "test-brand"},
        headers={"X-API-Key": "wrong-secret-key"},
    )
    assert resp.status_code == 403


def test_admin_create_brand_valid(client: TestClient):
    payload = {
        "slug": "puma-india",
        "name": "Puma India",
        "aliases": ["Puma", "Puma Sports"],
        "legal_names": ["Puma Sports India Private Limited"],
        "official_domains": ["in.puma.com", "puma.com"],
        "official_phones": ["+91 1800 102 7862"],
        "payment_policy": "Official checkout only.",
        "sources": [
            {
                "url": "https://in.puma.com/in/en/help/contact-us",
                "verified_on": "2026-10-05",
            }
        ],
    }

    resp = client.post(
        "/v1/admin/brands",
        json=payload,
        headers={"X-API-Key": VALID_KEY},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["slug"] == "puma-india"
    assert data["name"] == "Puma India"
    assert "in.puma.com" in data["official_domains"]

    # Verify readable via public GET endpoint
    pub_resp = client.get("/v1/brands/puma-india")
    assert pub_resp.status_code == 200
    assert pub_resp.json()["name"] == "Puma India"


def test_admin_create_brand_invalid_sources(client: TestClient):
    # Missing source URL or invalid date format
    payload = {
        "slug": "bad-brand",
        "name": "Bad Brand",
        "official_domains": ["badbrand.com"],
        "sources": [
            {
                "url": "https://badbrand.com",
                "verified_on": "not-a-valid-date",
            }
        ],
    }
    resp = client.post(
        "/v1/admin/brands",
        json=payload,
        headers={"X-API-Key": VALID_KEY},
    )
    assert resp.status_code == 422


def test_admin_update_brand(client: TestClient):
    payload = {
        "slug": "puma-india",
        "name": "Puma India (Updated)",
        "official_domains": ["in.puma.com"],
        "official_phones": ["+91 1800 102 7862", "+91 80 4646 5500"],
        "sources": [
            {
                "url": "https://in.puma.com/in/en/help/contact-us",
                "verified_on": "2026-10-05",
            }
        ],
    }

    resp = client.put(
        "/v1/admin/brands/puma-india",
        json=payload,
        headers={"X-API-Key": VALID_KEY},
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "Puma India (Updated)"
    assert len(resp.json()["official_phones"]) == 2


def test_admin_reports_queue(client: TestClient):
    # Submit 2 test reports
    client.post(
        "/v1/reports",
        json={
            "identifier": "+91 99999 88888",
            "identifier_type": "phone",
            "category": "impersonation",
            "notes": "Fake Flipkart representative",
        },
    )

    resp = client.get("/v1/admin/reports", headers={"X-API-Key": VALID_KEY})
    assert resp.status_code == 200
    reports = resp.json()
    assert isinstance(reports, list)
    assert len(reports) >= 1
    item = next(r for r in reports if r["identifier_type"] == "phone")
    assert item["distinct_reporters"] >= 1
    assert item["category"] == "impersonation"


def test_admin_freshness_report(client: TestClient):
    resp = client.get("/v1/admin/freshness", headers={"X-API-Key": VALID_KEY})
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) >= 1
    for item in data:
        assert "slug" in item
        assert "status" in item
        assert item["status"] in ("FRESH", "STALE", "NO_VALID_DATE")
