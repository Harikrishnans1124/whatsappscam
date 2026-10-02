#!/usr/bin/env python3
"""Check freshness of the brand registry entries."""

import argparse
import datetime as dt
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.registry import get_all_brands, get_engine, get_session_factory


def check_freshness(max_age_days: int = 90, db_url: str | None = None) -> int:
    engine = get_engine(db_url)
    session_factory = get_session_factory(engine)

    today = dt.datetime.now(dt.timezone.utc).date()
    stale_count = 0

    with session_factory() as session:
        brands = get_all_brands(session)
        if not brands:
            print("No brands found in registry. Please run scripts/seed_registry.py first.")
            return 1

        print(f"Checking freshness for {len(brands)} brands (threshold: {max_age_days} days, today: {today}):\n")
        print(f"{'Brand':<25} {'Slug':<20} {'Last Verified':<15} {'Age (days)':<12} {'Status'}")
        print("-" * 80)

        for brand in brands:
            latest_date: dt.date | None = None
            for src in brand.sources:
                try:
                    d = dt.date.fromisoformat(src.verified_on)
                    if latest_date is None or d > latest_date:
                        latest_date = d
                except ValueError:
                    continue

            if latest_date is None:
                status = "NO_VALID_DATE"
                age_str = "N/A"
                stale_count += 1
            else:
                age = (today - latest_date).days
                age_str = str(age)
                if age > max_age_days:
                    status = "STALE (NEEDS RE-VERIFICATION)"
                    stale_count += 1
                else:
                    status = "FRESH"

            verif_str = latest_date.isoformat() if latest_date else "None"
            print(f"{brand.name:<25} {brand.slug:<20} {verif_str:<15} {age_str:<12} {status}")

    print("-" * 80)
    if stale_count > 0:
        print(f"WARNING: Found {stale_count} stale brand entries older than {max_age_days} days.")
    else:
        print(f"ALL CLEAR: All {len(brands)} brands are fresh and verified within {max_age_days} days.")
    return 0


def main():
    parser = argparse.ArgumentParser(description="Check brand registry freshness")
    parser.add_argument("--max-age-days", type=int, default=90, help="Maximum allowable age in days (default: 90)")
    parser.add_argument("--db-url", default=None, help="Database URL")
    args = parser.parse_args()
    sys.exit(check_freshness(args.max_age_days, args.db_url))


if __name__ == "__main__":
    main()
