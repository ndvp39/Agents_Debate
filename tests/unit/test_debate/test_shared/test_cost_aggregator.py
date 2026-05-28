"""Tests for debate.shared.cost_aggregator — sum per-agent gatekeeper dumps + USD math."""

import json
from pathlib import Path

import pytest

from debate.shared.cost_aggregator import aggregate_costs

_SETUP = {
    "provider": {
        "active": "gemini",
        "gemini": {
            "debater_model": "gemini-3.1-flash-lite",
            "judge_model": "gemini-3.1-flash-lite",
        },
    },
    "costs": {
        "gemini-3.1-flash-lite": {
            "input_per_million_tokens": 0.25,
            "output_per_million_tokens": 1.50,
        },
    },
}


def _dump(tmp_path: Path, name: str, calls: int, in_tokens: int, out_tokens: int) -> Path:
    p = tmp_path / f"{name}.json"
    p.write_text(json.dumps({
        "total_calls": calls,
        "total_input_tokens": in_tokens,
        "total_output_tokens": out_tokens,
    }), encoding="utf-8")
    return p


def test_aggregate_empty_returns_empty_dict(tmp_path):
    # All three files exist but are zero — treat as "no debate happened".
    pro = _dump(tmp_path, "pro", 0, 0, 0)
    con = _dump(tmp_path, "con", 0, 0, 0)
    judge = _dump(tmp_path, "judge", 0, 0, 0)
    assert aggregate_costs(_SETUP, pro, con, judge) == {}


def test_aggregate_sums_calls_and_tokens(tmp_path):
    pro = _dump(tmp_path, "pro", 5, 1_000_000, 500_000)   # 1M in, 0.5M out
    con = _dump(tmp_path, "con", 5, 1_000_000, 500_000)
    judge = _dump(tmp_path, "judge", 3, 200_000, 100_000)
    out = aggregate_costs(_SETUP, pro, con, judge)
    assert out["total_calls"] == 13
    assert out["total_input_tokens"] == 2_200_000
    assert out["total_output_tokens"] == 1_100_000
    assert out["total_tokens"] == 3_300_000


def test_aggregate_computes_usd_from_setup_rates(tmp_path):
    # Pro: 1M in × $0.25 + 0.5M out × $1.50 = $0.25 + $0.75 = $1.00
    # Con: identical = $1.00
    # Judge: 0.2M in × $0.25 + 0.1M out × $1.50 = $0.05 + $0.15 = $0.20
    # Total: $2.20
    pro = _dump(tmp_path, "pro", 5, 1_000_000, 500_000)
    con = _dump(tmp_path, "con", 5, 1_000_000, 500_000)
    judge = _dump(tmp_path, "judge", 3, 200_000, 100_000)
    out = aggregate_costs(_SETUP, pro, con, judge)
    assert out["estimated_cost_usd"] == pytest.approx(2.20)
    assert out["per_agent"]["Agent_Pro"]["estimated_cost_usd"] == pytest.approx(1.00)
    assert out["per_agent"]["Agent_Con"]["estimated_cost_usd"] == pytest.approx(1.00)
    assert out["per_agent"]["Agent_Judge"]["estimated_cost_usd"] == pytest.approx(0.20)


def test_aggregate_missing_file_treated_as_zero(tmp_path):
    pro = _dump(tmp_path, "pro", 4, 100, 50)
    out = aggregate_costs(_SETUP, pro, tmp_path / "missing.json", None)
    assert out["per_agent"]["Agent_Pro"]["total_calls"] == 4
    assert out["per_agent"]["Agent_Con"]["total_calls"] == 0
    assert out["per_agent"]["Agent_Judge"]["total_calls"] == 0


def test_aggregate_missing_model_rates_zeros_usd(tmp_path):
    setup_no_rates = {
        "provider": {"active": "gemini", "gemini": {
            "debater_model": "unknown-model", "judge_model": "unknown-model",
        }},
        "costs": {},
    }
    pro = _dump(tmp_path, "pro", 5, 1_000_000, 500_000)
    out = aggregate_costs(setup_no_rates, pro, None, None)
    assert out["total_calls"] == 5
    assert out["estimated_cost_usd"] == 0.0  # token totals correct, USD unknown


def test_aggregate_per_agent_carries_model_name(tmp_path):
    pro = _dump(tmp_path, "pro", 1, 100, 50)
    out = aggregate_costs(_SETUP, pro, None, None)
    assert out["per_agent"]["Agent_Pro"]["model"] == "gemini-3.1-flash-lite"
    assert out["per_agent"]["Agent_Judge"]["model"] == "gemini-3.1-flash-lite"
