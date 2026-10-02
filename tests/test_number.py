"""Tests for Phase 3d: Number Scorer."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.agents.number import number_scorer
from app.extraction import CheckContext, normalize_phone
from app.registry import Base, record_report


@pytest.fixture
def in_memory_db():
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)
    with session_factory() as session:
        yield session
    Base.metadata.drop_all(engine)


@pytest.fixture
def base_context():
    return CheckContext(
        phone=normalize_phone(None),
        extracted_phones=[],
        urls=[],
        upi_ids=[],
        payment={},
        brand=None,
    )


@pytest.mark.asyncio
async def test_number_not_applicable(base_context):
    res = await number_scorer(base_context)
    assert res["status"] == "not_applicable"
    assert res["risk"] is None
    assert len(res["reasons"]) == 0


@pytest.mark.asyncio
async def test_number_invalid_phone(base_context):
    base_context.phone = normalize_phone("12345")
    res = await number_scorer(base_context)
    assert res["status"] == "ok"
    assert "INVALID_PHONE_NUMBER" in res["reasons"]
    assert res["risk"] >= 0.80


@pytest.mark.asyncio
async def test_number_valid_clean_phone(base_context, in_memory_db):
    base_context.phone = normalize_phone("+919876543210")
    res = await number_scorer(base_context, db_session=in_memory_db)
    assert res["status"] == "ok"
    assert res["risk"] <= 0.15
    assert "REPORTED_BY_USERS" not in res["reasons"]
    assert res["evidence"]["distinct_reporters"] == 0


@pytest.mark.asyncio
async def test_number_community_reports_threshold(base_context, in_memory_db):
    target_num = "+919876543210"
    base_context.phone = normalize_phone(target_num)

    # 3 distinct reporters report this number
    record_report(in_memory_db, target_num, "phone", "192.168.1.1", "scam")
    record_report(in_memory_db, target_num, "phone", "192.168.1.2", "scam")
    record_report(in_memory_db, target_num, "phone", "192.168.1.3", "scam")

    res = await number_scorer(base_context, db_session=in_memory_db)
    assert res["status"] == "ok"
    assert "REPORTED_BY_USERS" in res["reasons"]
    assert res["evidence"]["distinct_reporters"] == 3
    assert res["risk"] >= 0.50


@pytest.mark.asyncio
async def test_number_official_brand_match(in_memory_db):
    ctx = CheckContext(
        phone=normalize_phone("+9118002029898"),
        extracted_phones=[],
        urls=[],
        upi_ids=[],
        payment={},
        brand={
            "claimed": "Flipkart",
            "slug": "flipkart",
            "name": "Flipkart",
            "in_registry": True,
            "brand_data": {
                "name": "Flipkart",
                "official_phones": ["+9118002029898"],
            },
        },
    )
    res = await number_scorer(ctx, db_session=in_memory_db)
    assert res["status"] == "ok"
    assert res["risk"] <= 0.05
    assert res["evidence"]["is_official_phone"] is True
