#!/usr/bin/env python3
"""CLI script to test extraction and the Brand Identity Scorer."""

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.agents.brand_identity import evaluate_brand_identity
from app.extraction import extract_check_context
from app.registry import get_all_brands, get_engine, get_session_factory, init_db
from scripts.seed_registry import seed_registry


def run_check(
    brand: str | None = None,
    phone: str | None = None,
    urls: list[str] | None = None,
    message: str | None = None,
    upi: str | None = None,
    db_url: str | None = None,
) -> None:
    engine = get_engine(db_url)
    init_db(engine)
    session_factory = get_session_factory(engine)

    # Load registry brands from DB, seeding if empty
    with session_factory() as session:
        db_brands = get_all_brands(session)
        if not db_brands:
            print("[INFO] Registry database is empty. Auto-seeding from registry/brands.yaml...")
            seed_registry(PROJECT_ROOT / "registry" / "brands.yaml", db_url=db_url)
            db_brands = get_all_brands(session)

        registry_list = [b.to_dict() for b in db_brands]

    # Build extraction context
    payment_dict = {"upi_id": upi} if upi else {}
    context = extract_check_context(
        phone_number=phone,
        message_text=message,
        urls=urls,
        claimed_brand=brand,
        payment=payment_dict,
        registry_brands=registry_list,
    )

    # Evaluate brand identity
    result = evaluate_brand_identity(context)

    # Pretty print outputs
    print("\n" + "=" * 60)
    print("           TRUSTSHOP AI - EXTRACTION CONTEXT")
    print("=" * 60)
    print(f"Phone input:         {phone or 'None'}")
    print(f"Normalized phone:    {context.phone.get('e164')} (valid={context.phone.get('valid')}, type={context.phone.get('type')})")
    if context.extracted_phones:
        print(f"Chat phones found:   {[p.get('e164') for p in context.extracted_phones]}")
    print(f"Extracted URLs:      {[u.get('registrable_domain') for u in context.urls]}")
    print(f"Extracted UPI IDs:   {context.upi_ids}")
    if context.brand:
        print(f"Detected brand:      {context.brand.get('name')} (in_registry={context.brand.get('in_registry')}, method={context.brand.get('detection_method')})")
    else:
        print("Detected brand:      None")

    print("\n" + "=" * 60)
    print("         BRAND IDENTITY SCORER EVALUATION")
    print("=" * 60)
    outcome = result["evidence"].get("outcome", "UNKNOWN")
    print(f"Outcome:             {outcome}")
    print(f"Status:              {result['status']}")
    print(f"Risk score:          {result['risk']}")
    print(f"Reason codes:        {result['reasons']}")
    print(f"Flags raised:        {result['flags']}")
    print(f"Details:             {result['evidence'].get('details')}")
    print("=" * 60 + "\n")


def main():
    parser = argparse.ArgumentParser(description="Check brand identity scorer against contact inputs")
    parser.add_argument("--brand", help="Claimed brand name or alias (e.g. 'Flipkart', 'Amazon', 'Acme Footwear')")
    parser.add_argument("--phone", help="Phone / WhatsApp number (e.g. '+91 98765 43210', '09876543210')")
    parser.add_argument("--url", action="append", dest="urls", help="URL sent by seller (can specify multiple)")
    parser.add_argument("--message", help="Message text or chat snippet")
    parser.add_argument("--upi", help="UPI ID (e.g. 'seller@ybl')")
    parser.add_argument("--db-url", help="Database URL")

    args = parser.parse_args()

    if not (args.brand or args.phone or args.urls or args.message or args.upi):
        parser.print_help()
        print("\nError: Please provide at least one input (--brand, --phone, --url, --message, or --upi).")
        sys.exit(1)

    run_check(
        brand=args.brand,
        phone=args.phone,
        urls=args.urls,
        message=args.message,
        upi=args.upi,
        db_url=args.db_url,
    )


if __name__ == "__main__":
    main()
