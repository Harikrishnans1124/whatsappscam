"""Circuit Breaker and execution timeout guards for TrustShop AI."""

from __future__ import annotations

import asyncio
import time
from collections.abc import Coroutine
from enum import Enum
from typing import Any

from app.config import settings


class CircuitState(str, Enum):
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"


class CircuitBreaker:
    """Lightweight 3-state circuit breaker pattern implementation."""

    def __init__(self, name: str, fail_max: int = 5, reset_timeout_s: float = 30.0) -> None:
        self.name = name
        self.fail_max = fail_max
        self.reset_timeout_s = reset_timeout_s
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.opened_at: float | None = None
        self.last_failure_time: float | None = None

    def is_open(self) -> bool:
        """Check if breaker is in OPEN state, or transition to HALF_OPEN after cooldown."""
        if self.state == CircuitState.OPEN:
            now = time.monotonic()
            if self.opened_at is not None and (now - self.opened_at) >= self.reset_timeout_s:
                self.state = CircuitState.HALF_OPEN
                return False
            return True
        return False

    def record_success(self) -> None:
        """Record successful execution and reset state to CLOSED."""
        self.failure_count = 0
        self.state = CircuitState.CLOSED
        self.opened_at = None

    def record_failure(self) -> None:
        """Record a failure and open breaker if threshold exceeded."""
        self.failure_count += 1
        self.last_failure_time = time.monotonic()
        if self.state == CircuitState.HALF_OPEN or self.failure_count >= self.fail_max:
            self.state = CircuitState.OPEN
            self.opened_at = time.monotonic()

    def reset(self) -> None:
        """Reset breaker to default CLOSED state."""
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.opened_at = None
        self.last_failure_time = None


# Registry of circuit breakers per component
_BREAKERS: dict[str, CircuitBreaker] = {}


def get_circuit_breaker(name: str) -> CircuitBreaker:
    """Get or create circuit breaker for given name."""
    if name not in _BREAKERS:
        b_cfg = settings.get("breaker", {})
        fail_max = b_cfg.get("fail_max", 5)
        reset_timeout = float(b_cfg.get("reset_timeout_s", 30))
        _BREAKERS[name] = CircuitBreaker(name=name, fail_max=fail_max, reset_timeout_s=reset_timeout)
    return _BREAKERS[name]


def reset_all_breakers() -> None:
    """Reset all circuit breakers (primarily for test isolation)."""
    for b in _BREAKERS.values():
        b.reset()


async def guarded_scorer(
    scorer_name: str,
    coro: Coroutine[Any, Any, dict[str, Any]],
    timeout_s: float | None = None,
) -> dict[str, Any]:
    """Execute scorer coroutine guarded by circuit breaker and timeout."""
    breaker = get_circuit_breaker(scorer_name)

    # 1. Fast circuit breaker rejection
    if breaker.is_open():
        try:
            coro.close()
        except (AttributeError, RuntimeError):
            pass
        return {
            "status": "failed",
            "risk": None,
            "reasons": ["SCORER_UNAVAILABLE"],
            "flags": [],
            "evidence": {
                "breaker_open": True,
                "scorer": scorer_name,
                "state": breaker.state.value,
                "details": f"Circuit breaker '{scorer_name}' is open. Scorer skipped fast.",
            },
        }

    # 2. Determine timeout
    if timeout_s is None:
        timeouts_ms = settings.get("timeouts_ms", {})
        timeout_ms = timeouts_ms.get(scorer_name, 150)
        timeout_s = timeout_ms / 1000.0

    # 3. Guarded execution
    try:
        res = await asyncio.wait_for(coro, timeout=timeout_s)
        if res.get("status") == "failed":
            breaker.record_failure()
        else:
            breaker.record_success()
        return res
    except TimeoutError:
        breaker.record_failure()
        return {
            "status": "failed",
            "risk": None,
            "reasons": ["SCORER_TIMEOUT"],
            "flags": [],
            "evidence": {
                "timeout_s": timeout_s,
                "scorer": scorer_name,
                "details": f"Scorer '{scorer_name}' timed out after {timeout_s:.3f}s.",
            },
        }
    except Exception as exc:  # noqa: BLE001
        breaker.record_failure()
        return {
            "status": "failed",
            "risk": None,
            "reasons": ["SCORER_FAILED"],
            "flags": [],
            "evidence": {
                "error": str(exc),
                "scorer": scorer_name,
                "details": f"Scorer '{scorer_name}' raised unhandled exception.",
            },
        }
