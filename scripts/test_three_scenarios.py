"""Verification script testing genuine, suspicious, and obvious scam scenarios."""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from fastapi.testclient import TestClient

from app.main import app

with TestClient(app) as client:
    # 1. Genuine scenario
    p1 = {
        "claimed_brand": "Flipkart",
        "phone_number": "+91 1800 202 9898",
        "urls": ["https://flipkart.com/orders"],
        "payment": {
            "upi_id": "flipkart.merchant@hdfc",
            "display_name": "Flipkart Internet Private Limited",
        },
        "message_text": "Hi, I would like to check when my package will arrive.",
    }
    r1 = client.post("/v1/checks", json=p1).json()
    print("=== 1. GENUINE SCENARIO ===")
    print("Verdict:", r1["verdict"])
    print("Risk Score:", r1["risk_score"])
    print("Reasons:", r1["reason_codes"])
    assert r1["verdict"] == "MATCHES_OFFICIAL", f"Expected MATCHES_OFFICIAL, got {r1['verdict']}"

    # 2. Suspicious scenario: Known brand claimed on an unauthorized mobile number
    p2 = {
        "claimed_brand": "Flipkart",
        "phone_number": "+91 9876543210",
        "message_text": "Hello, thank you for contacting Flipkart support. How can I assist you with your order?",
    }
    r2 = client.post("/v1/checks", json=p2).json()
    print("\n=== 2. SUSPICIOUS SCENARIO ===")
    print("Verdict:", r2["verdict"])
    print("Risk Score:", r2["risk_score"])
    print("Reasons:", r2["reason_codes"])
    assert r2["verdict"] == "SUSPICIOUS", f"Expected SUSPICIOUS, got {r2['verdict']}"

    # 3. Obvious Scam scenario
    p3 = {
        "claimed_brand": "Flipkart",
        "phone_number": "+91 9999888877",
        "urls": ["https://flipkrt-deals.shop/iphone15"],
        "payment": {
            "upi_id": "9876543210@ybl",
            "display_name": "Ramesh Kumar",
        },
        "message_text": "Congratulations! Won lucky draw iPhone. Share OTP and install AnyDesk to claim.",
    }
    r3 = client.post("/v1/checks", json=p3).json()
    print("\n=== 3. OBVIOUS SCAM SCENARIO ===")
    print("Verdict:", r3["verdict"])
    print("Risk Score:", r3["risk_score"])
    print("Reasons:", r3["reason_codes"])
    print("Flags:", [s for s in r3["scores"].values() if s.get("flags")])
    assert r3["verdict"] == "LIKELY_SCAM", f"Expected LIKELY_SCAM, got {r3['verdict']}"

    print("\nSUCCESS: All three scenarios produced exact expected verdicts!")
