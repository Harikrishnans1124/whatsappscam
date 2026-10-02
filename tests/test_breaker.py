"""Tests for Phase 4: Circuit Breaker and Execution Timeouts."""

import asyncio

import pytest

from app.breaker import (
    CircuitBreaker,
    CircuitState,
    get_circuit_breaker,
    guarded_scorer,
    reset_all_breakers,
)


@pytest.fixture(autouse=True)
def _reset_breakers():
    reset_all_breakers()
    yield
    reset_all_breakers()


def test_circuit_breaker_transitions():
    cb = CircuitBreaker(name="test_cb", fail_max=3, reset_timeout_s=0.1)
    assert cb.state == CircuitState.CLOSED
    assert cb.is_open() is False

    # Record 2 failures -> still closed
    cb.record_failure()
    cb.record_failure()
    assert cb.state == CircuitState.CLOSED
    assert cb.is_open() is False

    # 3rd failure -> trip to OPEN
    cb.record_failure()
    assert cb.state == CircuitState.OPEN
    assert cb.is_open() is True

    # After cooldown period -> transitions to HALF_OPEN
    import time
    time.sleep(0.12)
    assert cb.is_open() is False
    assert cb.state == CircuitState.HALF_OPEN

    # Success in HALF_OPEN resets to CLOSED
    cb.record_success()
    assert cb.state == CircuitState.CLOSED
    assert cb.failure_count == 0


@pytest.mark.asyncio
async def test_guarded_scorer_success():
    async def fast_scorer():
        return {"status": "ok", "risk": 0.1, "reasons": [], "flags": []}

    res = await guarded_scorer("test_fast", fast_scorer(), timeout_s=0.5)
    assert res["status"] == "ok"
    assert res["risk"] == 0.1


@pytest.mark.asyncio
async def test_guarded_scorer_timeout():
    async def slow_scorer():
        await asyncio.sleep(0.3)
        return {"status": "ok", "risk": 0.1}

    res = await guarded_scorer("test_slow", slow_scorer(), timeout_s=0.05)
    assert res["status"] == "failed"
    assert res["risk"] is None
    assert "SCORER_TIMEOUT" in res["reasons"]


@pytest.mark.asyncio
async def test_guarded_scorer_open_breaker_fast_rejection():
    cb = get_circuit_breaker("test_failing")
    # Force trip breaker
    for _ in range(5):
        cb.record_failure()
    assert cb.is_open() is True

    async def dummy_scorer():
        return {"status": "ok"}

    res = await guarded_scorer("test_failing", dummy_scorer(), timeout_s=1.0)
    assert res["status"] == "failed"
    assert "SCORER_UNAVAILABLE" in res["reasons"]
    assert res["evidence"]["breaker_open"] is True


@pytest.mark.asyncio
async def test_guarded_scorer_unhandled_exception():
    async def broken_scorer():
        raise RuntimeError("Unexpected internal crash")

    res = await guarded_scorer("test_crash", broken_scorer(), timeout_s=0.5)
    assert res["status"] == "failed"
    assert "SCORER_FAILED" in res["reasons"]
