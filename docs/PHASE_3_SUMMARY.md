# Phase 3 Summary: Remaining Scorers

**Date:** October 2, 2026  
**Status:** Completed & Verified  

---

## 1. Accomplishments Overview

Phase 3 replaces all stubbed scorers with fully functional, intelligent detection engines:

### 3a. Payment Scorer (`app/agents/payment.py`)
- **RapidFuzz Legal Entity Matching**: Compares user-entered payee display names to the brand's verified legal entity names using `token_set_ratio` with normalization of abbreviations (`Pvt Ltd` ↔ `Private Limited`, `Corp` ↔ `Corporation`, etc.). Fuzzy score $\ge 80$ yields `PAYEE_NAME_MATCH`.
- **`PERSONAL_PAYEE` Hard Floor Flag**: Detects when a verified brand is claimed but payment is directed to an individual's personal name (absence of corporate indicators like *Pvt, Ltd, Enterprises, LLP, Store, Retail*). Raises flag `PERSONAL_PAYEE` triggering a hard floor risk of 0.70.
- **Phone-Style UPI Handle Detection**: Flags VPAs using 10-digit mobile numbers (e.g. `9876543210@ybl`) as weak suspicion signals (`PHONE_STYLE_UPI`), without ever being decisive alone.

### 3b. Domain Scorer (`app/agents/domain.py`)
- **Exact Official Domain Verification**: Directly matches official registered domains (`OFFICIAL_DOMAIN_MATCH`) reducing domain risk to 0.0.
- **Lookalike & Typosquatting Engine**:
  - Damerau-Levenshtein edit distance $\le 2$ against official brand domain labels (`flipkrt`, `myntraa`).
  - Brand-stuffing detection: Brand token combined with commercial or phishing keywords (`nike-outlet-shop`, `amazon-deals`, `flipkart-offers`).
  - Digit / hyphen substitution tricks (`amaz0n`, `flip-kart`, `pay-tm`).
  - Punycode (`xn--`) and Unicode mixed-script homoglyph detection (e.g. Cyrillic `а` mimicking Latin `a`).
  - Triggers hard floor flag `LOOKALIKE_DOMAIN` (risk 0.85+).
- **URL Shortener List**: Identifies URL concealing services (`bit.ly`, `tinyurl.com`, `t.co`, etc.) with code `URL_SHORTENER`.
- **Asynchronous RDAP Age Resolution**: Async HTTP lookups against RDAP servers with timeout and fallback to identify newly registered domains (< 30 days) raising `NEW_DOMAIN`.

### 3c. Message Scorer (`app/agents/message.py`)
- **Rule-Based Scam Tactics Engine**:
  - `OTP_REQUEST`: Requests for OTP, one-time passwords, or PINs. Triggers hard floor flag `OTP_REQUEST` (risk $\ge 0.85$).
  - `REMOTE_ACCESS_REQUEST`: Requests to install screen-sharing / remote access tools (*AnyDesk, TeamViewer, QuickSupport, RustDesk, .apk files*). Triggers hard floor flag `REMOTE_ACCESS_REQUEST` (risk $\ge 0.85$).
  - `URGENCY_PRESSURE`: High-pressure tactics (*"today only", "last 2 pieces", "hurry up"*).
  - `ADVANCE_PAYMENT_REQUEST`: Demands for token money or upfront courier fees.
  - `OFF_PLATFORM_MOVE`: Requests to shift conversation to personal WhatsApp or Telegram.
  - `SUSPICIOUS_OFFER`: Unrealistic lotteries, 90% discounts, or prize claims.
- **Machine Learning Classifier**:
  - Trained TF-IDF + Logistic Regression model saved at `data/models/message_classifier.joblib`.
  - Non-blocking execution via `asyncio.to_thread`.
  - 100% scam recall on held-out test data.

### 3d. Number Scorer & Reports API (`app/agents/number.py`, `app/main.py`)
- **Number Validation**: Full validation and type analysis (mobile, toll-free, fixed-line) via Google's `phonenumbers` library. Invalid numbers trigger `INVALID_PHONE_NUMBER`.
- **Privacy-Preserving Community Reports**:
  - Database model `reports` stores HMAC-SHA256 hashed identifiers and hashed reporter IP addresses. Raw personal numbers and IPs are never persisted.
  - Automatic deduplication: updates timestamp if reported again by same user.
- **REST API Endpoint (`POST /v1/reports`)**:
  - Allows crowdsourcing scam reports for phone numbers, domains, and UPI IDs.
  - When distinct reporters $\ge 3$, raises `REPORTED_BY_USERS` and proportionally scales risk.

---

## 2. Verification & Test Metrics

- **Total Automated Pytest Tests**: 100/100 passed (100% green).
- **Linter Checks**: `ruff check .` passed with 0 lint or formatting errors.
- **Three Hand-Made Acceptance Scenarios Verified**:
  1. *Genuine Brand Order*: Verdict `MATCHES_OFFICIAL`, risk `0.03`.
  2. *Unauthorized Mobile Claim*: Verdict `SUSPICIOUS`, risk `0.55`.
  3. *Obvious Scam (AnyDesk + OTP + Personal Payee + Fake Domain)*: Verdict `LIKELY_SCAM`, risk `0.85`.
