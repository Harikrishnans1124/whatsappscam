#!/usr/bin/env python3
"""Run quantitative evaluation on TrustShop AI benchmark cases."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import respx
from httpx import Response
from starlette.requests import Request

from app.main import create_check
from app.registry import get_session_factory, init_db
from app.schemas import CheckRequest

VERDICTS = ["MATCHES_OFFICIAL", "UNVERIFIED", "SUSPICIOUS", "LIKELY_SCAM"]
SCAM_CATEGORIES = {
    "wrong_number_impersonation",
    "lookalike_domain",
    "personal_payee",
    "message_only_scam",
}
GENUINE_CATEGORIES = {
    "genuine_official",
    "genuine_small_shop",
}


def load_cases(cases_path: Path, split_filter: str | None = None) -> list[dict[str, Any]]:
    cases = []
    with open(cases_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            item = json.loads(line)
            if split_filter and split_filter != "all" and item.get("split") != split_filter:
                continue
            cases.append(item)
    return cases


@respx.mock
def run_evaluation(cases: list[dict[str, Any]], verbose: bool = False) -> dict[str, Any]:
    # Mock RDAP external requests so tests run fast, offline, and deterministically
    respx.get(url__regex=r"https://rdap\..*").mock(
        return_value=Response(
            200,
            json={
                "events": [
                    {"eventAction": "registration", "eventDate": "2026-09-01T00:00:00Z"},
                    {"eventAction": "last changed", "eventDate": "2026-09-15T00:00:00Z"},
                ]
            },
        )
    )

    init_db()
    session_factory = get_session_factory()

    # Metrics counters
    total_cases = len(cases)
    exact_matches = 0
    unsafe_passes = 0  # Scam case classified as MATCHES_OFFICIAL (Target: 0)

    total_scam_cases = 0
    scam_detected = 0  # classified as SUSPICIOUS or LIKELY_SCAM

    total_genuine_cases = 0
    false_alarms = 0  # genuine case classified as SUSPICIOUS or LIKELY_SCAM

    # Confusion matrix: rows = expected, cols = actual
    conf_matrix: dict[str, dict[str, int]] = {
        exp: {act: 0 for act in VERDICTS} for exp in VERDICTS
    }

    category_stats: dict[str, dict[str, int]] = {}

    for i, case in enumerate(cases):
        c_id = case["id"]
        category = case.get("category", "unknown")
        expected = case["expected"]
        payload_data = case["input"]

        if category not in category_stats:
            category_stats[category] = {"total": 0, "correct": 0}
        category_stats[category]["total"] += 1

        payload = CheckRequest.model_validate(payload_data)

        # Unique mock client IP per eval item to prevent local rate limit collisions
        scope = {
            "type": "http",
            "method": "POST",
            "path": "/v1/checks",
            "headers": [(b"host", b"localhost:8000")],
            "client": (f"192.168.1.{(i % 250) + 1}", 50000 + i),
        }
        mock_request = Request(scope)

        with session_factory() as db:
            res = asyncio.run(create_check(payload, mock_request, db))

        actual = res.verdict

        if expected in conf_matrix and actual in conf_matrix[expected]:
            conf_matrix[expected][actual] += 1

        is_exact = actual == expected
        if is_exact:
            exact_matches += 1
            category_stats[category]["correct"] += 1

        # Check Unsafe Passes (CRITICAL METRIC)
        is_scam_category = category in SCAM_CATEGORIES
        if is_scam_category:
            total_scam_cases += 1
            if actual in ("SUSPICIOUS", "LIKELY_SCAM"):
                scam_detected += 1
            if actual == "MATCHES_OFFICIAL":
                unsafe_passes += 1
                if verbose:
                    print(f"  [UNSAFE PASS] {c_id}: Expected {expected}, got {actual}")

        is_genuine = category in GENUINE_CATEGORIES
        if is_genuine:
            total_genuine_cases += 1
            if actual in ("SUSPICIOUS", "LIKELY_SCAM"):
                false_alarms += 1
                if verbose:
                    print(f"  [FALSE ALARM] {c_id} ({category}): Got {actual}")

    scam_recall = (scam_detected / total_scam_cases * 100) if total_scam_cases > 0 else 100.0
    false_alarm_rate = (false_alarms / total_genuine_cases * 100) if total_genuine_cases > 0 else 0.0
    verdict_accuracy = (exact_matches / total_cases * 100) if total_cases > 0 else 0.0

    return {
        "total_cases": total_cases,
        "exact_matches": exact_matches,
        "accuracy": verdict_accuracy,
        "total_scams": total_scam_cases,
        "scam_recall": scam_recall,
        "total_genuine": total_genuine_cases,
        "false_alarm_rate": false_alarm_rate,
        "unsafe_passes": unsafe_passes,
        "conf_matrix": conf_matrix,
        "category_stats": category_stats,
    }


def print_results(results: dict[str, Any], title: str = "Evaluation Results"):
    print("\n" + "=" * 70)
    print(f" {title.upper()}")
    print("=" * 70)
    print(f"Total Cases Evaluated:       {results['total_cases']}")
    print(f"Verdict Exact Accuracy:     {results['accuracy']:.2f}% ({results['exact_matches']}/{results['total_cases']})")
    print(f"Scam Recall:                {results['scam_recall']:.2f}% ({results['total_scams']} scam cases)")
    print(f"False-Alarm Rate:           {results['false_alarm_rate']:.2f}% ({results['total_genuine']} genuine cases)")
    
    unsafe_status = "PASSED (0)" if results["unsafe_passes"] == 0 else f"FAILED ({results['unsafe_passes']})"
    print(f"Unsafe Passes (Target 0):   {results['unsafe_passes']} [{unsafe_status}]")

    print("\n" + "-" * 70)
    print(" BREAKDOWN BY CATEGORY")
    print("-" * 70)
    print(f"{'Category':<32} {'Total':<10} {'Correct':<10} {'Accuracy'}")
    print("-" * 70)
    for cat, stat in results["category_stats"].items():
        pct = (stat["correct"] / stat["total"] * 100) if stat["total"] > 0 else 0.0
        print(f"{cat:<32} {stat['total']:<10} {stat['correct']:<10} {pct:>6.1f}%")

    print("\n" + "-" * 70)
    print(" CONFUSION MATRIX")
    print("-" * 70)
    col_label = "Expected \\ Actual"
    header = f"{col_label:<20}" + "".join(f"{v:>15}" for v in VERDICTS)
    print(header)
    print("-" * 80)
    for exp in VERDICTS:
        row = f"{exp:<20}"
        for act in VERDICTS:
            row += f"{results['conf_matrix'][exp][act]:>15}"
        print(row)
    print("=" * 80 + "\n")


def main():
    parser = argparse.ArgumentParser(description="TrustShop AI Evaluation Runner")
    parser.add_argument(
        "--cases",
        type=Path,
        default=PROJECT_ROOT / "eval" / "cases.jsonl",
        help="Path to JSONL evaluation dataset",
    )
    parser.add_argument(
        "--split",
        choices=["tuning", "held_out", "all"],
        default="all",
        help="Dataset split to evaluate (tuning, held_out, or all)",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print details of unsafe passes or false alarms",
    )
    args = parser.parse_args()

    if not args.cases.exists():
        print(f"Error: Evaluation cases file not found at {args.cases}")
        print("Run scripts/generate_eval_cases.py to generate it.")
        sys.exit(1)

    if args.split == "all":
        # Run tuning and held-out separately and report both
        tuning_cases = load_cases(args.cases, split_filter="tuning")
        heldout_cases = load_cases(args.cases, split_filter="held_out")

        tuning_res = run_evaluation(tuning_cases, verbose=args.verbose)
        print_results(tuning_res, title="Tuning Subset Results (N=61)")

        heldout_res = run_evaluation(heldout_cases, verbose=args.verbose)
        print_results(heldout_res, title="Held-Out Subset Results (N=61)")

        if heldout_res["unsafe_passes"] > 0:
            print("[FAIL] Unsafe passes > 0 on held-out subset!")
            sys.exit(1)
        else:
            print("[OK] SUCCESS: 0 unsafe passes on both tuning and held-out subsets!")
            sys.exit(0)
    else:
        cases = load_cases(args.cases, split_filter=args.split)
        res = run_evaluation(cases, verbose=args.verbose)
        print_results(res, title=f"{args.split.capitalize()} Subset Results (N={len(cases)})")
        sys.exit(1 if res["unsafe_passes"] > 0 else 0)


if __name__ == "__main__":
    main()
