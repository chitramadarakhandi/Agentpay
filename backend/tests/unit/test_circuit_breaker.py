"""Unit tests for Circuit Breaker Pattern."""

import time
import pytest
from app.core.circuit_breaker import CircuitBreaker, CircuitBreakerOpenException, CircuitState


def test_circuit_breaker_starts_closed():
    cb = CircuitBreaker(name="test_cb", failure_threshold=3, recovery_timeout_seconds=0.5)
    assert cb.state == CircuitState.CLOSED


def test_circuit_breaker_trips_to_open_after_failures():
    cb = CircuitBreaker(name="test_cb", failure_threshold=3, recovery_timeout_seconds=0.5)

    def failing_call():
        raise RuntimeError("Gateway 500 error")

    for _ in range(3):
        with pytest.raises(RuntimeError):
            cb.call(failing_call)

    assert cb.state == CircuitState.OPEN

    # Subsequent call fails fast with CircuitBreakerOpenException without invoking func
    invoked = False
    def should_not_run():
        nonlocal invoked
        invoked = True

    with pytest.raises(CircuitBreakerOpenException):
        cb.call(should_not_run)

    assert not invoked


def test_circuit_breaker_transitions_to_half_open_and_recovers():
    cb = CircuitBreaker(name="test_cb", failure_threshold=2, recovery_timeout_seconds=0.1)

    def failing_call():
        raise ConnectionError("Timeout")

    for _ in range(2):
        with pytest.raises(ConnectionError):
            cb.call(failing_call)

    assert cb.state == CircuitState.OPEN

    # Wait for cooldown
    time.sleep(0.15)
    assert cb.state == CircuitState.HALF_OPEN

    # Successful call in HALF_OPEN recovers circuit to CLOSED
    def successful_call():
        return "ok"

    res = cb.call(successful_call)
    assert res == "ok"
    assert cb.state == CircuitState.CLOSED
