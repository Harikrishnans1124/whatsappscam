"""Tests for Phase 3d: Community Reports and POST /v1/reports API."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app, get_db
from app.registry import (
    Base,
    count_distinct_reporters,
    get_report_stats,
    hmac_sha256,
    record_report,
)


@pytest.fixture
def test_db_session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    with session_factory() as session:
        yield session
    Base.metadata.drop_all(engine)


@pytest.fixture
def client(test_db_session):
    def override_get_db():
        yield test_db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def test_hmac_sha256_anonymization():
    raw_num = "+919876543210"
    h1 = hmac_sha256(raw_num, secret="test-secret")
    h2 = hmac_sha256(raw_num, secret="test-secret")
    assert h1 == h2
    assert len(h1) == 64
    assert raw_num not in h1


def test_record_report_deduplication(test_db_session):
    raw_num = "+919876543210"
    reporter = "10.0.0.1"

    # First report
    rep1, is_new1 = record_report(test_db_session, raw_num, "phone", reporter, "scam")
    assert is_new1 is True

    # Same reporter reporting again (deduplication)
    rep2, is_new2 = record_report(test_db_session, raw_num, "phone", reporter, "impersonation")
    assert is_new2 is False
    assert rep1.id == rep2.id

    # Count distinct reporters should still be 1
    count = count_distinct_reporters(test_db_session, raw_num)
    assert count == 1

    # Different reporter reports
    _, is_new3 = record_report(test_db_session, raw_num, "phone", "10.0.0.2", "scam")
    assert is_new3 is True

    # Count distinct reporters should now be 2
    stats = get_report_stats(test_db_session, raw_num)
    assert stats["distinct_reporters"] == 2
    assert stats["total_reports"] == 2


def test_api_create_report(client):
    payload = {
        "identifier": "+919876543210",
        "identifier_type": "phone",
        "category": "impersonation",
        "notes": "Claimed to be Amazon support demanding money",
    }
    response = client.post("/v1/reports", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["status"] == "received"
    assert data["distinct_reporters"] == 1
    assert data["total_reports"] == 1


def test_api_create_report_domain_and_upi(client):
    # Domain report
    dom_res = client.post(
        "/v1/reports",
        json={"identifier": "https://fake-amazon-deals.shop/order", "identifier_type": "domain"},
    )
    assert dom_res.status_code == 201
    assert dom_res.json()["identifier_type"] == "domain"

    # UPI report
    upi_res = client.post(
        "/v1/reports",
        json={"identifier": "9876543210@paytm", "identifier_type": "upi"},
    )
    assert upi_res.status_code == 201
    assert upi_res.json()["identifier_type"] == "upi"
