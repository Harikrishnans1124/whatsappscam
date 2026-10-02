"""CLI script to verify the cryptographic integrity of the audit log."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.audit import DEFAULT_AUDIT_LOG_PATH, verify_audit_log


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify TrustShop AI hash-chained audit log.")
    parser.add_argument(
        "--file",
        type=Path,
        default=DEFAULT_AUDIT_LOG_PATH,
        help="Path to audit log jsonl file",
    )
    args = parser.parse_args()

    print(f"Verifying audit log chain at: {args.file}")
    is_valid, _count, message = verify_audit_log(args.file)

    if is_valid:
        print(f"[OK] {message}")
        return 0
    else:
        print(f"[FAILED] Integrity violation detected!\n{message}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
