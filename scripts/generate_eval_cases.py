#!/usr/bin/env python3
"""Generate a balanced, realistic evaluation dataset for TrustShop AI."""

import json
import random
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
EVAL_DIR = PROJECT_ROOT / "eval"
EVAL_DIR.mkdir(parents=True, exist_ok=True)
CASES_FILE = EVAL_DIR / "cases.jsonl"

random.seed(42)  # Deterministic generation

cases = []
case_id = 1


def add_case(category, expected, payload):
    global case_id
    split = "tuning" if (case_id % 2 == 1) else "held_out"
    cases.append(
        {
            "id": f"c_{case_id:03d}",
            "split": split,
            "category": category,
            "expected": expected,
            "input": payload,
        }
    )
    case_id += 1


# 1. Genuine Official Contacts (Expected: MATCHES_OFFICIAL)
# Uses exact official published channels from registry/brands.yaml
official_brands_with_phone = [
    ("Flipkart", "+91 1800 202 9898", "https://flipkart.com", "Flipkart Internet Private Limited"),
    ("Myntra", "+91 80 6156 1999", "https://myntra.com", "Myntra Designs Private Limited"),
    ("Tata CLiQ", "+91 22 6807 8282", "https://tatacliq.com", "Tata UniStore Limited"),
    ("AJIO", "+91 1800 889 9991", "https://ajio.com", "Reliance Retail Limited"),
    ("Meesho", "+91 80 6179 9600", "https://meesho.com", "Fashnear Technologies Private Limited"),
    ("Nykaa", "+91 1800 267 4444", "https://nykaa.com", "FSN E-Commerce Ventures Limited"),
    ("Acme Footwear", "+91 1800 11 2233", "https://acmefootwear.com", "Acme Footwear Private Limited"),
]

for b_name, phone, url, legal in official_brands_with_phone:
    add_case("genuine_official", "MATCHES_OFFICIAL", {
        "claimed_brand": b_name,
        "phone_number": phone,
        "urls": [url],
        "message_text": f"Thank you for contacting {b_name} customer support. Order details are confirmed.",
    })
    add_case("genuine_official", "MATCHES_OFFICIAL", {
        "claimed_brand": b_name,
        "phone_number": phone,
    })
    add_case("genuine_official", "MATCHES_OFFICIAL", {
        "claimed_brand": b_name,
        "urls": [url],
        "payment": {"display_name": legal},
    })

# Brands without published phone sales channels: official contact is via verified domain & payment
official_brands_domain_only = [
    ("Amazon India", "https://amazon.in", "Amazon Seller Services Private Limited"),
    ("Zomato", "https://zomato.com", "Zomato Limited"),
    ("Swiggy", "https://swiggy.com", "Bundl Technologies Private Limited"),
]

for b_name, url, legal in official_brands_domain_only:
    add_case("genuine_official", "MATCHES_OFFICIAL", {
        "claimed_brand": b_name,
        "urls": [url],
        "payment": {"display_name": legal},
    })
    add_case("genuine_official", "MATCHES_OFFICIAL", {
        "claimed_brand": b_name,
        "urls": [url],
    })

# 2. Genuine Small Shops NOT in Registry (Expected: UNVERIFIED)
# Legitimate small businesses that should NOT be flagged as scams or suspicious.
small_shops = [
    ("Kochi Spice Corner", "+91 98471 23456", "Fresh Wayanad black pepper and cardamom available. Price 600 per kg.", "kochispices@okhdfcbank", "Kochi Spices"),
    ("Sharma Electronics Delhi", "+91 98111 23456", "Your laptop charger is ready for pickup at our Nehru Place shop.", "sharmaelect@paytm", "Sharma Electronics"),
    ("Pooja Traditional Sarees", "+91 94441 56789", "New Kanchipuram silk sarees in stock. Delivery via speed post.", "poojasarees@sbi", "Pooja Textiles"),
    ("Baker's Haven Bakery", "+91 98801 23456", "Custom birthday cake order confirmed for Saturday 5 PM.", "bakershaven@icici", "Bakers Haven"),
    ("Royal Handicrafts Jaipur", "+91 94140 12345", "Handmade wooden jewelry box packed and dispatched. Tracking sent.", "royaljaipur@upi", "Royal Handicrafts"),
    ("Green Valley Nursery", "+91 97451 98765", "Indoor plants and ceramic pots available. Cash on delivery accepted.", "greenvalley@axl", "Green Valley Nursery"),
    ("Mubeen Tailors & Drapers", "+91 98220 54321", "Suit stitching complete. You can collect it tomorrow afternoon.", "mubeentailors@ybl", "Mubeen Tailors"),
    ("Sree Murugan Book Store", "+91 94431 87654", "CBSE Class 10 guide books arrived. We can courier to your address.", "muruganbooks@okaxis", "Sree Murugan Books"),
    ("Coastal Fresh Seafoods", "+91 98951 12345", "Fresh Kingfish and Prawns available today. Home delivery within 5 km.", "coastalfresh@okhdfcbank", "Coastal Fresh"),
    ("Gupta Hardware Store", "+91 98390 65432", "Plumbing tools and pipe fittings available. Store open till 8 PM.", "guptahardware@barodampay", "Gupta Hardware"),
    ("Malabar Halwa House", "+91 94970 33445", "Original Calicut black halwa 1kg pack ready for shipping.", "malabarhalwa@fbl", "Malabar Halwa"),
    ("Pooja Ceramic Studio", "+91 98200 44556", "Handmade coffee mugs available in 4 pastel colors. Ships in 2 days.", "poojaceramics@okicici", "Pooja Ceramics"),
]

for shop_name, phone, chat, upi, d_name in small_shops:
    add_case("genuine_small_shop", "UNVERIFIED", {
        "phone_number": phone,
        "message_text": chat,
        "payment": {"upi_id": upi, "display_name": d_name},
    })
    add_case("genuine_small_shop", "UNVERIFIED", {
        "phone_number": phone,
        "message_text": chat,
    })

# 3. Wrong-Number Brand Impersonation (Expected: LIKELY_SCAM if combined with tactics, SUSPICIOUS if phone mismatch alone)
impersonation_targets = [
    ("Flipkart", "+91 98765 11111", "seller987@ybl", "Rakesh Kumar"),
    ("Amazon India", "+91 87654 22222", "pay_amz@okaxis", "Sunil Sharma"),
    ("Myntra", "+91 76543 33333", "myntra_deals@paytm", "Ankit Verma"),
    ("Tata CLiQ", "+91 91234 44444", "tatacliq_support@upi", "Pooja Singh"),
    ("AJIO", "+91 99887 55555", "ajio_outlet@okhdfcbank", "Vikram Patel"),
    ("Nykaa", "+91 97766 66666", "nykaa_beauty@ibl", "Deepak Joshi"),
    ("Apple India", "+91 96655 77777", "apple_care_delhi@paytm", "Manoj Tiwari"),
    ("Meesho", "+91 95544 88888", "meesho_reseller@axl", "Sanjay Yadav"),
]

for brand, fake_phone, upi, d_name in impersonation_targets:
    add_case("wrong_number_impersonation", "LIKELY_SCAM", {
        "claimed_brand": brand,
        "phone_number": fake_phone,
        "message_text": f"Hello from {brand} official sales team. We have exclusive 70% discount today only.",
        "payment": {"upi_id": upi, "display_name": d_name},
    })
    add_case("wrong_number_impersonation", "SUSPICIOUS", {
        "claimed_brand": brand,
        "phone_number": fake_phone,
    })

# 4. Lookalike Domains (Expected: LIKELY_SCAM)
lookalike_examples = [
    ("Flipkart", "https://flipkart-festivesale.shop/clearance"),
    ("Flipkart", "https://filpkart-outlet.online/deals"),
    ("Amazon India", "https://amazon-india-sale.store/iphone"),
    ("Amazon India", "https://amazn-deals.site/promo"),
    ("Myntra", "https://myntra-clearancesale.shop/shoes"),
    ("Myntra", "https://myntraa-fashion.top/coupons"),
    ("Tata CLiQ", "https://tatacliq-luxuryoffer.shop/watch"),
    ("AJIO", "https://ajio-trends-sale.online/kurtas"),
    ("Nykaa", "https://nykaa-cosmetics-outlet.club/lipsticks"),
    ("Apple India", "https://apple-india-refurbished.store/iphone15"),
    ("Acme Footwear", "https://acmefootwear-outlet.shop/deal"),
    ("Meesho", "https://meesho-wholesale-direct.top/sarees"),
]

for brand, fake_url in lookalike_examples:
    add_case("lookalike_domain", "LIKELY_SCAM", {
        "claimed_brand": brand,
        "urls": [fake_url],
        "message_text": f"Click this official {brand} link to claim your special discount: {fake_url}",
    })
    add_case("lookalike_domain", "LIKELY_SCAM", {
        "claimed_brand": brand,
        "urls": [fake_url],
        "phone_number": "+91 98765 00000",
    })

# 5. Personal Payee for Known Brand (Expected: LIKELY_SCAM with advance request, SUSPICIOUS for personal payee alone)
personal_payee_cases = [
    ("Flipkart", "9876543210@ybl", "Rahul Sharma"),
    ("Amazon India", "amzpay99@okhdfcbank", "Priya Kumari"),
    ("Myntra", "myntracash@paytm", "Mohit Agarwal"),
    ("Tata CLiQ", "tata_deals@okaxis", "Suresh Nair"),
    ("AJIO", "ajio_order@upi", "Dinesh Chandra"),
    ("Nykaa", "nykaastore@fbl", "Kavita Reddy"),
    ("Apple India", "apple_direct@sbi", "Arjun Pillai"),
]

for brand, upi, d_name in personal_payee_cases:
    add_case("personal_payee", "LIKELY_SCAM", {
        "claimed_brand": brand,
        "payment": {"upi_id": upi, "display_name": d_name},
        "message_text": f"Pay advance Rs. 999 to confirm {brand} dispatch.",
    })
    add_case("personal_payee", "LIKELY_SCAM", {
        "claimed_brand": brand,
        "payment": {"upi_id": upi, "display_name": d_name},
    })

# 6. Message-Only Scams: OTP & Remote Access (LIKELY_SCAM), Urgency & Advance Fee (SUSPICIOUS)
hard_message_scams = [
    "Dear customer, your order is on hold. Share the OTP sent to your phone to release shipment.",
    "Verification required for your Flipkart refund. Please tell me the OTP received on SMS.",
    "Amazon customer support: install AnyDesk app so our executive can fix your payment issue.",
    "To process your high-value cashback, download TeamViewer QuickSupport and share screen.",
    "Urgent: KYC expired! Send one time password immediately or your bank account will be blocked.",
]

for msg in hard_message_scams:
    add_case("message_only_scam", "LIKELY_SCAM", {
        "message_text": msg,
    })
    add_case("message_only_scam", "LIKELY_SCAM", {
        "message_text": msg,
        "phone_number": "+91 99999 00000",
    })

soft_message_scams = [
    "Congratulations! You won Rs 25,00,000 in Kaun Banega Crorepati lucky draw! Send processing fee.",
    "You are selected as lucky winner of free iPhone 15! Pay courier charge Rs. 499 immediately.",
    "Your package is detained at customs. Pay refundable security deposit Rs. 1500 to clear.",
    "Work from home opportunity! Earn daily Rs. 5000 by liking videos. Deposit Rs. 1000 registration fee.",
    "Flash deal! 90% off on all items! Valid for 10 minutes only! Pay Rs. 499 now to hold stock.",
]

for msg in soft_message_scams:
    add_case("message_only_scam", "SUSPICIOUS", {
        "message_text": msg,
    })
    add_case("message_only_scam", "SUSPICIOUS", {
        "message_text": msg,
        "phone_number": "+91 99999 00000",
    })

# Write to file
with open(CASES_FILE, "w", encoding="utf-8") as f:
    f.writelines(json.dumps(c, ensure_ascii=False) + "\n" for c in cases)

tuning_count = sum(1 for c in cases if c["split"] == "tuning")
heldout_count = sum(1 for c in cases if c["split"] == "held_out")

print(f"Generated {len(cases)} evaluation cases into {CASES_FILE}:")
print(f"  - Tuning subset:  {tuning_count}")
print(f"  - Held-out subset: {heldout_count}")
