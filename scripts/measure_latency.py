#!/usr/bin/env python3
"""Measure latency (p50, p95) across cached, uncached, and timeout scenarios for TrustShop AI."""

from __future__ import annotations

import asyncio
import platform
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import httpx
import respx
from starlette.requests import Request

from app.cache import set_cached_rdap
from app.main import create_check
from app.registry import get_session_factory, init_db
from app.schemas import CheckRequest, PaymentInput


def get_mock_request(client_ip: str = "127.0.0.1") -> Request:
    scope = {
        "type": "http",
        "method": "POST",
        "path": "/v1/checks",
        "headers": [(b"host", b"localhost:8000")],
        "client": (client_ip, 54321),
    }
    return Request(scope)


def run_benchmark_scenario(
    name: str,
    payload_fn: Any,
    setup_fn: Any = None,
    iterations: int = 50,
) -> dict[str, Any]:
    init_db()
    session_factory = get_session_factory()
    latencies: list[float] = []

    for i in range(iterations):
        if setup_fn:
            setup_fn(i)
        payload = payload_fn(i)
        req = get_mock_request(client_ip=f"192.168.2.{(i % 250) + 1}")

        t0 = time.perf_counter()
        with session_factory() as db:
            _ = asyncio.run(create_check(payload, req, db))
        t1 = time.perf_counter()
        latencies.append((t1 - t0) * 1000)

    p50 = float(np.percentile(latencies, 50))
    p95 = float(np.percentile(latencies, 95))
    mean = float(np.mean(latencies))
    min_lat = float(np.min(latencies))
    max_lat = float(np.max(latencies))

    return {
        "scenario": name,
        "iterations": iterations,
        "p50_ms": round(p50, 2),
        "p95_ms": round(p95, 2),
        "mean_ms": round(mean, 2),
        "min_ms": round(min_lat, 2),
        "max_ms": round(max_lat, 2),
    }


def main():
    print("=" * 80)
    print("TrustShop AI - Latency Benchmarking (p50, p95)")
    print("=" * 80)

    # Machine Specs
    uname = platform.uname()
    cpu_info = uname.processor or "x86_64"
    py_ver = sys.version.split()[0]
    os_name = f"{platform.system()} {platform.release()}"
    print(f"Machine Specs:  OS: {os_name} | CPU: {cpu_info} | Python: {py_ver}")
    print("=" * 80)

    # -------------------------------------------------------------
    # Scenario 1: All Cached (Domain RDAP in memory/redis cache)
    # -------------------------------------------------------------
    print("\n[1/3] Benchmarking Scenario 1: All Cached (50 runs)...")
    # Pre-warm cache
    set_cached_rdap(
        "flipkart.com",
        {"registration_date": "2007-09-01", "raw": {}},
        ttl_s=86400,
    )

    def payload_cached(i):
        return CheckRequest(
            claimed_brand="Flipkart",
            phone_number="+91 1800 202 9898",
            urls=["https://flipkart.com"],
            payment=PaymentInput(display_name="Flipkart Internet Private Limited"),
        )

    res_cached = run_benchmark_scenario("All cached", payload_cached, iterations=50)

    # -------------------------------------------------------------
    # Scenario 2: Uncached Domain Lookup (Simulated RDAP network response)
    # -------------------------------------------------------------
    print("[2/3] Benchmarking Scenario 2: Uncached Domain Lookup (50 runs)...")

    @respx.mock
    def run_uncached():
        respx.get(url__regex=r"https://rdap\..*").mock(
            return_value=httpx.Response(
                200,
                json={"events": [{"eventAction": "registration", "eventDate": "2024-01-01T00:00:00Z"}]},
            )
        )

        def payload_uncached(i):
            return CheckRequest(
                claimed_brand="Flipkart",
                urls=[f"https://flipkart-deal-{i}.store/offer"],
            )

        return run_benchmark_scenario("Uncached domain lookup", payload_uncached, iterations=50)

    res_uncached = run_uncached()

    # -------------------------------------------------------------
    # Scenario 3: RDAP Timeout Scenario (Degraded Mode, Breaker Timeout)
    # -------------------------------------------------------------
    print("[3/3] Benchmarking Scenario 3: RDAP Timeout (Degraded Mode) (10 runs)...")

    @respx.mock
    def run_timeout():
        # Simulate timeout on RDAP lookup
        respx.get(url__regex=r"https://rdap\..*").mock(side_effect=httpx.TimeoutException("RDAP timeout"))

        def payload_timeout(i):
            return CheckRequest(
                claimed_brand="Flipkart",
                urls=[f"https://timeout-test-domain-{i}.com"],
            )

        return run_benchmark_scenario("RDAP timeout (degraded)", payload_timeout, iterations=10)

    res_timeout = run_timeout()

    # -------------------------------------------------------------
    # Results Table
    # -------------------------------------------------------------
    results = [res_cached, res_uncached, res_timeout]

    print("\n" + "=" * 80)
    print(" MEASURED LATENCY BENCHMARK RESULTS")
    print("=" * 80)
    print(f"{'Scenario':<28} {'p50 (ms)':<12} {'p95 (ms)':<12} {'Mean (ms)':<12} {'Notes'}")
    print("-" * 80)
    for r in results:
        notes = (
            "Local DB + in-memory cache"
            if "cached" in r["scenario"].lower() and "un" not in r["scenario"].lower()
            else (
                "Simulated RDAP resolution"
                if "uncached" in r["scenario"].lower()
                else "Circuit breaker / degraded mode"
            )
        )
        print(f"{r['scenario']:<28} {r['p50_ms']:>8.2f} ms   {r['p95_ms']:>8.2f} ms   {r['mean_ms']:>8.2f} ms   {notes}")
    print("=" * 80)

    # Save to JSON
    out_file = PROJECT_ROOT / "eval" / "latency_benchmark.json"
    with open(out_file, "w", encoding="utf-8") as f:
        import json

        json.dump(
            {
                "machine": {"os": os_name, "cpu": cpu_info, "python": py_ver},
                "benchmarks": results,
            },
            f,
            indent=2,
        )
    print(f"\nBenchmark metrics written to {out_file}\n")


if __name__ == "__main__":
    main()
