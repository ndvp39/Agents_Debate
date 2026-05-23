"""Tests for debate.shared.gatekeeper — written before implementation (TDD RED)."""

from unittest.mock import MagicMock

import pytest

from debate.shared.gatekeeper import (
    ApiGatekeeper,
    BackpressureError,
    GatekeeperMaxRetriesError,
)


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


def test_successful_call(mock_config):
    gk = ApiGatekeeper(mock_config)
    result = gk.execute(lambda: "ok")
    assert result == "ok"


def test_retry_on_transient_failure(mock_config):
    attempts = {"n": 0}

    def flaky():
        attempts["n"] += 1
        if attempts["n"] < 3:
            raise ValueError("transient")
        return "success"

    gk = ApiGatekeeper(mock_config)
    result = gk.execute(flaky)
    assert result == "success"
    assert attempts["n"] == 3


def test_max_retries_exceeded_raises(mock_config):
    def always_fails():
        raise ValueError("always fails")

    gk = ApiGatekeeper(mock_config)
    with pytest.raises(GatekeeperMaxRetriesError):
        gk.execute(always_fails)


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


def test_cost_tracking_call_count(mock_config):
    gk = ApiGatekeeper(mock_config)
    gk.execute(lambda: None)
    gk.execute(lambda: None)
    assert gk.get_cost_summary()["total_calls"] == 2


def test_queue_status_initially_zero(mock_config):
    gk = ApiGatekeeper(mock_config)
    assert gk.get_queue_status()["queue_depth"] == 0


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
    with pytest.raises((BackpressureError, GatekeeperMaxRetriesError)):
        gk.execute(lambda: None)
