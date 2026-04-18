# tests/unit/test_circuit_breaker.py
import pytest
import time
from unittest.mock import patch
from src.retrieval.hybrid import CircuitBreaker


def test_starts_closed():
    """Circuit must be CLOSED (working) on initialisation."""
    cb = CircuitBreaker(failure_threshold=3, reset_timeout=60.0)
    assert not cb.is_open()
    assert cb._state == "CLOSED"


def test_opens_after_threshold_failures():
    """
    After N consecutive failures, circuit must open.
    This is the core protection mechanism — if Cohere fails 3 times,
    stop calling it and return hybrid results instead.
    """
    cb = CircuitBreaker(failure_threshold=3, reset_timeout=60.0)
    cb.record_failure()
    cb.record_failure()
    assert not cb.is_open(), "Should still be CLOSED after 2 failures"
    cb.record_failure()
    assert cb.is_open(), "Should be OPEN after 3 failures"


def test_success_resets_failure_count():
    """A single success after failures resets to CLOSED."""
    cb = CircuitBreaker(failure_threshold=3, reset_timeout=60.0)
    cb.record_failure()
    cb.record_failure()
    cb.record_success()
    cb.record_failure()  # would only be 1 failure now, not 3
    assert not cb.is_open(), "One success should reset the failure counter"


def test_transitions_to_half_open_after_timeout():
    """
    After reset_timeout seconds, an OPEN circuit should become HALF_OPEN
    and allow one probe request through.
    
    WHY: Without this, once a circuit opens it stays open forever even
    after Cohere recovers. The half-open state lets one request through
    to test if the service is healthy again.
    """
    cb = CircuitBreaker(failure_threshold=1, reset_timeout=0.1)  # 100ms for test speed
    cb.record_failure()
    assert cb.is_open()

    time.sleep(0.15)   # wait for reset_timeout

    # After timeout, is_open() should return False (HALF_OPEN)
    assert not cb.is_open(), "Circuit should be HALF_OPEN after timeout"
    assert cb._state == "HALF_OPEN"


def test_success_in_half_open_closes_circuit():
    """A successful probe in HALF_OPEN state fully closes the circuit."""
    cb = CircuitBreaker(failure_threshold=1, reset_timeout=0.1)
    cb.record_failure()
    time.sleep(0.15)
    cb.is_open()             # transitions to HALF_OPEN
    cb.record_success()      # probe succeeded
    assert cb._state == "CLOSED"
    assert not cb.is_open()