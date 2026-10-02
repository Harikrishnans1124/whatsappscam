# Phase 1 Summary: Brand Registry, Extraction & Brand Identity Scorer

**Date:** October 2, 2026  
**Status:** Completed & Verified  

---

## 1. Accomplishments Overview

Phase 1 establishes the core foundation of **TrustShop AI**: answering the central verification question: *"Does this contact belong to the brand's verified official list?"*

### Components Implemented:
1. **Curated Brand Registry (`registry/brands.yaml`)**:
   - 11 brands (10 major impersonated brands in India + 1 benchmark test brand): Amazon India, Flipkart, Myntra, Tata CLiQ, AJIO, Meesho, Nykaa, Zomato, Swiggy, Apple India, Acme Footwear.
   - Strictly enforces source URLs and `verified_on` ISO dates for all entries.
2. **SQLite Registry Database (`app/registry.py`)**:
   - SQLAlchemy 2.0 models: `Brand`, `BrandAlias`, `BrandLegalName`, `BrandDomain`, `BrandPhone`, `BrandSource`.
   - Strict validation logic rejecting incomplete entries.
   - Fast lookup by slug, alias, or brand name.
   - Freshness detection function `is_brand_stale()`.
3. **Database Seeding & Freshness Scripts**:
   - `scripts/seed_registry.py`: Validates and seeds YAML data into SQLite (`data/trustshop.db`).
   - `scripts/check_registry_freshness.py`: Checks for entries older than 90 days.
4. **Extraction & Normalization Engine (`app/extraction.py`)**:
   - Phone normalization to E.164 and carrier type using Google's `phonenumbers` port.
   - Extraction of phones from chat text.
   - URL parsing and registrable domain extraction using `tldextract`.
   - UPI Virtual Payment Address (VPA) extraction with strict rules preventing confusion with email addresses.
   - Claimed brand detection from user input, aliases, text keywords, and domain tokens.
   - `CheckContext` data model.
5. **Brand Identity Scorer (`app/agents/brand_identity.py`)**:
   - Scorer outcomes:
     - `MATCH`: Risk `0.0`, reason `BRAND_CHANNEL_MATCH`.
     - `MISMATCH`: Risk `0.85`, flag & reason `BRAND_CHANNEL_MISMATCH`.
     - `UNKNOWN_BRAND`: Risk `0.20`, reason `BRAND_NOT_IN_REGISTRY`.
     - `NO_BRAND_CLAIM`: Status `not_applicable`, risk `None`.
   - Appends `REGISTRY_STALE` reason if the registry entry is older than 90 days.
6. **Command-Line Testing Utility (`scripts/check_brand.py`)**:
   - CLI utility allowing end-to-end testing of extraction and brand identity scoring with human-readable output.
7. **Comprehensive Unit Test Suite (`tests/`)**:
   - 37 unit tests covering messy phone formats, URL extraction, UPI vs email parsing, brand detection, registry validation, and scorer outcomes.
   - **Result:** 37 / 37 passed (`100% green`).
8. **Code Quality**:
   - `ruff check .` passes with zero lint issues.

---

## 2. Quick Command Reference

```bash
# Seed the brand registry into SQLite
python scripts/seed_registry.py

# Check freshness of registry entries
python scripts/check_registry_freshness.py --max-age-days 90

# Test a genuine brand contact (Flipkart official helpline)
python scripts/check_brand.py --brand Flipkart --phone "+91 1800 202 9898" --url "https://flipkart.com/deal"

# Test an impersonation mismatch (fake mobile claiming to be Flipkart)
python scripts/check_brand.py --brand Flipkart --phone "+91 98765 43210"

# Test an unregistered brand
python scripts/check_brand.py --brand "RandomStore" --phone "+91 98765 43210"

# Run all unit tests
pytest -v

# Run linter
ruff check .
```
