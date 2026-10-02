"""Unit tests for app.registry module."""

import datetime as dt

import pytest
from sqlalchemy import create_engine

from app.registry import (
    find_brand_by_alias_or_name,
    get_all_brands,
    get_brand_by_slug,
    get_session_factory,
    init_db,
    is_brand_stale,
    upsert_brand,
    validate_brand_data,
)


@pytest.fixture
def memory_db():
    engine = create_engine("sqlite:///:memory:")
    init_db(engine)
    session_factory = get_session_factory(engine)
    return session_factory


class TestRegistryValidation:
    def test_valid_brand(self):
        valid = {
            "slug": "test-brand",
            "name": "Test Brand",
            "official_domains": ["testbrand.com"],
            "official_phones": ["+911800123456"],
            "sources": [{"url": "https://testbrand.com/contact", "verified_on": "2026-10-01"}],
        }
        assert validate_brand_data(valid) == []

    def test_missing_slug_and_name(self):
        invalid = {
            "official_domains": ["testbrand.com"],
            "sources": [{"url": "https://testbrand.com/contact", "verified_on": "2026-10-01"}],
        }
        errors = validate_brand_data(invalid)
        assert any("slug" in e.lower() for e in errors)
        assert any("name" in e.lower() for e in errors)

    def test_missing_domains(self):
        invalid = {
            "slug": "test-brand",
            "name": "Test Brand",
            "official_domains": [],
            "sources": [{"url": "https://testbrand.com/contact", "verified_on": "2026-10-01"}],
        }
        errors = validate_brand_data(invalid)
        assert any("official_domains" in e for e in errors)

    def test_missing_sources_or_date(self):
        no_source = {
            "slug": "test-brand",
            "name": "Test Brand",
            "official_domains": ["testbrand.com"],
            "sources": [],
        }
        errors = validate_brand_data(no_source)
        assert any("source" in e.lower() for e in errors)

        no_date = {
            "slug": "test-brand",
            "name": "Test Brand",
            "official_domains": ["testbrand.com"],
            "sources": [{"url": "https://testbrand.com/contact"}],
        }
        errors = validate_brand_data(no_date)
        assert any("verified_on" in e for e in errors)

    def test_invalid_date_format(self):
        bad_date = {
            "slug": "test-brand",
            "name": "Test Brand",
            "official_domains": ["testbrand.com"],
            "sources": [{"url": "https://testbrand.com/contact", "verified_on": "01-10-2026"}],
        }
        errors = validate_brand_data(bad_date)
        assert any("ISO date" in e for e in errors)


class TestRegistryDatabaseOperations:
    def test_upsert_and_retrieve(self, memory_db):
        brand_data = {
            "slug": "acme-shoes",
            "name": "Acme Shoes",
            "aliases": ["Acme Footwear", "Acme"],
            "legal_names": ["Acme Shoes India Pvt Ltd"],
            "official_domains": ["acmeshoes.in"],
            "official_phones": ["+911800112233"],
            "payment_policy": "Pay only on website.",
            "sources": [{"url": "https://acmeshoes.in/contact", "verified_on": "2026-10-01"}],
        }

        with memory_db() as session:
            upsert_brand(session, brand_data)
            brand = get_brand_by_slug(session, "acme-shoes")
            assert brand is not None
            assert brand.name == "Acme Shoes"
            assert len(brand.domains) == 1
            assert brand.domains[0].domain == "acmeshoes.in"
            assert len(brand.phones) == 1
            assert brand.phones[0].phone_e164 == "+911800112233"

            # Query by alias
            by_alias = find_brand_by_alias_or_name(session, "Acme Footwear")
            assert by_alias is not None
            assert by_alias.slug == "acme-shoes"

            # Query all
            all_b = get_all_brands(session)
            assert len(all_b) == 1

    def test_freshness_check(self, memory_db):
        fresh_data = {
            "slug": "fresh-brand",
            "name": "Fresh Brand",
            "official_domains": ["fresh.com"],
            "sources": [{"url": "https://fresh.com", "verified_on": "2026-10-01"}],
        }
        stale_data = {
            "slug": "stale-brand",
            "name": "Stale Brand",
            "official_domains": ["stale.com"],
            "sources": [{"url": "https://stale.com", "verified_on": "2026-01-01"}],
        }

        today = dt.date(2026, 10, 2)
        with memory_db() as session:
            b_fresh = upsert_brand(session, fresh_data)
            b_stale = upsert_brand(session, stale_data)

            assert is_brand_stale(b_fresh, max_age_days=90, ref_date=today) is False
            assert is_brand_stale(b_stale, max_age_days=90, ref_date=today) is True
