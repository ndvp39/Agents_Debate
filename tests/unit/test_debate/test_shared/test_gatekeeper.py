"""Tests for debate.shared.gatekeeper — capacity, queueing, cost-tracking, fail-fast propagation."""

import time
from unittest.mock import MagicMock

import pytest

from debate.shared.gatekeeper import ApiGatekeeper, BackpressureError


@pytest.fixture
def mock_config():
    config = MagicMock()
    config.get_rate_limits.return_value = {
        "version": "1.00",
        "services": {
            "default": {
                "requests_per_minute": 100,
                "requests_per_hour": 1000,
                "concurrent_max": 5,
                "retry_after_seconds": 0.01,
                "max_retries": 2,
                "queue_max_depth": 5,
            }
        },
    }
    return config


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------

def test_successful_call(mock_config):
    gk = ApiGatekeeper(mock_config)
    result = gk.execute(lambda: "ok")
    assert result == "ok"


def test_cost_tracking_call_count(mock_config):
    gk = ApiGatekeeper(mock_config)
    gk.execute(lambda: None)
    gk.execute(lambda: None)
    assert gk.get_cost_summary()["total_calls"] == 2


def test_cost_tracking_input_tokens(mock_config):
    gk = ApiGatekeeper(mock_config)
    gk.execute(lambda: None, _input_tokens=100, _output_tokens=50)
    summary = gk.get_cost_summary()
    assert summary["total_input_tokens"] == 100


def test_cost_tracking_output_tokens(mock_config):
    gk = ApiGatekeeper(mock_config)
    gk.execute(lambda: None, _input_tokens=100, _output_tokens=50)
    summary = gk.get_cost_summary()
    assert summary["total_output_tokens"] == 50


def test_queue_status_initially_zero(mock_config):
    gk = ApiGatekeeper(mock_config)
    assert gk.get_queue_status()["queue_depth"] == 0


# ---------------------------------------------------------------------------
# Fail-fast propagation — gatekeeper no longer retries api_call
# ---------------------------------------------------------------------------

def test_execute_propagates_exception_immediately(mock_config):
    """Any exception from api_call must propagate from execute() without retry."""
    attempts = {"n": 0}

    def always_fails():
        attempts["n"] += 1
        raise ValueError("boom")

    gk = ApiGatekeeper(mock_config)
    start = time.time()
    with pytest.raises(ValueError, match="boom"):
        gk.execute(always_fails)
    elapsed = time.time() - start
    # Single call, no sleep — the inner _retry owns retry policy now.
    assert attempts["n"] == 1
    assert elapsed < 0.5, f"execute() should not sleep on failure (took {elapsed:.2f}s)"


def test_execute_propagates_daily_quota_runtime_error_immediately(mock_config):
    """The exact fatal raised by _retry() on daily quota — must NOT be retried."""
    attempts = {"n": 0}

    def quota_exhausted():
        attempts["n"] += 1
        raise RuntimeError("Daily API quota exhausted — please try again tomorrow.")

    gk = ApiGatekeeper(mock_config)
    start = time.time()
    with pytest.raises(RuntimeError, match="Daily API quota exhausted"):
        gk.execute(quota_exhausted)
    elapsed = time.time() - start
    assert attempts["n"] == 1
    # If the gatekeeper retried with retry_after_seconds=0.01 × 2^n, even 3 retries
    # would only add ~0.07s. We assert much tighter to catch ANY hidden sleep loop.
    assert elapsed < 0.3, f"daily-quota error must fail fast (took {elapsed:.2f}s)"


def test_execute_does_not_increment_cost_on_failure(mock_config):
    """A failed call must not be counted as a successful call."""
    gk = ApiGatekeeper(mock_config)
    with pytest.raises(ValueError):
        gk.execute(lambda: (_ for _ in ()).throw(ValueError("nope")))
    assert gk.get_cost_summary()["total_calls"] == 0


# ---------------------------------------------------------------------------
# record_tokens / cost dump (unchanged behavior)
# ---------------------------------------------------------------------------

def test_record_tokens_adds_tokens_without_incrementing_calls(mock_config):
    gk = ApiGatekeeper(mock_config)
    gk.execute(lambda: None)  # one call, no tokens via kwargs
    gk.record_tokens(150, 75)  # post-hoc real tokens
    summary = gk.get_cost_summary()
    assert summary["total_calls"] == 1  # NOT 2 — record_tokens must not bump
    assert summary["total_input_tokens"] == 150
    assert summary["total_output_tokens"] == 75


def test_cost_dump_path_writes_json_after_each_call(mock_config, tmp_path):
    import json
    dump_path = tmp_path / "cost.json"
    gk = ApiGatekeeper(mock_config, cost_dump_path=dump_path)
    gk.execute(lambda: None)
    assert dump_path.is_file()
    payload = json.loads(dump_path.read_text(encoding="utf-8"))
    assert payload["total_calls"] == 1
    # Second call updates the same file atomically.
    gk.execute(lambda: None)
    gk.record_tokens(50, 25)
    payload = json.loads(dump_path.read_text(encoding="utf-8"))
    assert payload["total_calls"] == 2
    assert payload["total_input_tokens"] == 50
    assert payload["total_output_tokens"] == 25


# ---------------------------------------------------------------------------
# Backpressure (capacity full)
# ---------------------------------------------------------------------------

def test_backpressure_when_queue_full(mock_config):
    mock_config.get_rate_limits.return_value = {
        "version": "1.00",
        "services": {
            "default": {
                "requests_per_minute": 0,
                "requests_per_hour": 0,
                "concurrent_max": 1,
                "retry_after_seconds": 0.01,
                "max_retries": 0,
                "queue_max_depth": 0,
            }
        },
    }
    gk = ApiGatekeeper(mock_config)
    with pytest.raises(BackpressureError):
        gk.execute(lambda: None)
