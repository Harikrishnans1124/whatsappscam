#!/usr/bin/env python3
"""Seed the TrustShop AI brand registry from a YAML file into SQLite database.
Rejects any entry that lacks a valid source URL and verification date.
"""

import argparse
import sys
from pathlib import Path

import yaml

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.registry import (
    get_engine,
    get_session_factory,
    init_db,
    upsert_brand,
    validate_brand_data,
)


def seed_registry(yaml_path: Path, db_url: str | None = None) -> int:
    if not yaml_path.exists():
        print(f"Error: YAML file not found: {yaml_path}", file=sys.stderr)
        return 1

    with open(yaml_path, "r", encoding="utf-8") as f:
        brands_data = yaml.safe_load(f)

    if not isinstance(brands_data, list):
        print(f"Error: Expected a list of brands in {yaml_path}, got {type(brands_data)}", file=sys.stderr)
        return 1

    print(f"Loaded {len(brands_data)} brand definitions from {yaml_path}. Validating...")

    # Step 1: Pre-validation of all entries (strict rule)
    all_errors = []
    for idx, brand_dict in enumerate(brands_data):
        if not isinstance(brand_dict, dict):
            all_errors.append(f"Entry #{idx+1} is not a valid map/dict")
            continue
        errors = validate_brand_data(brand_dict)
        if errors:
            all_errors.extend(errors)

    if all_errors:
        print("\n[VALIDATION FAILED] The following errors were found in brand registry data:", file=sys.stderr)
        for err in all_errors:
            print(f"  - {err}", file=sys.stderr)
        print("\nAll registry entries must have official domains, sources with non-empty URL and verified_on date.", file=sys.stderr)
        return 1

    # Step 2: Initialize DB and upsert
    engine = get_engine(db_url)
    init_db(engine)
    session_factory = get_session_factory(engine)

    seeded_count = 0
    with session_factory() as session:
        for brand_dict in brands_data:
            brand = upsert_brand(session, brand_dict)
            phones_count = len(brand.phones)
            domains_count = len(brand.domains)
            sources_count = len(brand.sources)
            print(f"  [OK] {brand.name} ({brand.slug}): {domains_count} domains, {phones_count} phones, {sources_count} sources")
            seeded_count += 1

    print(f"\nSuccessfully seeded {seeded_count} brands into SQLite registry database.")
    return 0


def main():
    parser = argparse.ArgumentParser(description="Seed brand registry into SQLite")
    parser.add_argument(
        "yaml_file",
        nargs="?",
        default=str(PROJECT_ROOT / "registry" / "brands.yaml"),
        help="Path to brands.yaml (default: registry/brands.yaml)",
    )
    parser.add_argument(
        "--db-url",
        dest="db_url",
        default=None,
        help="Custom database URL (default: from settings.yaml / DATABASE_URL env)",
    )
    args = parser.parse_args()
    exit_code = seed_registry(Path(args.yaml_file), args.db_url)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
