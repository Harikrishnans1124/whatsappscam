"""Tests for Phase 4: Redis Caching and Fixed-Window Rate Limiting."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.cache import (
    check_rate_limit,
    clear_test_caches,
    get_cached_rdap,
    set_cached_rdap,
)
from app.main import app, get_db
from app.registry import Base


@pytest.fixture(autouse=True)
def _clear_cache():
    clear_test_caches()
    yield
    clear_test_caches()


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


def test_rdap_cache_get_and_set():
    domain = "test-store.in"
    assert get_cached_rdap(domain) is None

    payload = {"registration_date": "2024-01-01T00:00:00+00:00"}
    set_cached_rdap(domain, payload, ttl_s=60)

    cached = get_cached_rdap(domain)
    assert cached is not None
    assert cached["registration_date"] == "2024-01-01T00:00:00+00:00"


def test_rate_limiter_under_and_over_limit():
    ip = "192.168.1.100"
    limit = 3

    # Request 1, 2, 3 should be allowed
    allowed1, count1, _rem1 = check_rate_limit(ip, limit=limit, window_s=60, force_in_memory=True)
    assert allowed1 is True
    assert count1 == 1

    allowed2, count2, _rem2 = check_rate_limit(ip, limit=limit, window_s=60, force_in_memory=True)
    assert allowed2 is True
    assert count2 == 2

    allowed3, count3, _rem3 = check_rate_limit(ip, limit=limit, window_s=60, force_in_memory=True)
    assert allowed3 is True
    assert count3 == 3

    # Request 4 should be rejected
    allowed4, count4, _rem4 = check_rate_limit(ip, limit=limit, window_s=60, force_in_memory=True)
    assert allowed4 is False
    assert count4 > limit


def test_api_rate_limit_exceeded_returns_429(client):
    test_ip = "10.99.88.77"
    headers = {"X-Forwarded-For": test_ip}
    payload = {"phone_number": "+919876543210"}

    # Prime rate limit to 30 requests
    for _ in range(30):
        check_rate_limit(test_ip, limit=30, window_s=60)

    # 31st request via API triggers HTTP 429
    res = client.post("/v1/checks", json=payload, headers=headers)
    assert res.status_code == 429
    body = res.json()
    assert body["status"] == 429
    assert "Rate limit exceeded" in body["detail"]
