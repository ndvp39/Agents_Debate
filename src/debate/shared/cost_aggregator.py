"""Cost aggregation — sum per-agent gatekeeper cost JSON files into a debate total.

Each agent subprocess writes its `ApiGatekeeper.get_cost_summary()` to a per-agent
JSON file after every successful API call. The SDK calls `aggregate_costs` at
debate end to read those files, sum them, and compute the estimated USD cost
from the model rates declared in `config/setup.json.costs`.

Caveat: a watchdog-restarted subprocess starts a fresh gatekeeper at zero.
Costs from the killed process are lost. For a debate-grade deliverable this is
acceptable — restarts are rare, and the aggregator's output is documented as
best-effort. The token totals never exceed reality; they only undercount.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

_log = logging.getLogger("debate.cost")


def _read_summary(path: Path | None) -> dict:
    """Read a per-agent gatekeeper cost dump; return zeros if missing/malformed."""
    if path is None or not Path(path).is_file():
        return {"total_calls": 0, "total_input_tokens": 0, "total_output_tokens": 0}
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        _log.warning("cost: could not read %s (%s) — counting as zero", path, exc)
        return {"total_calls": 0, "total_input_tokens": 0, "total_output_tokens": 0}
    return {
        "total_calls": int(payload.get("total_calls", 0)),
        "total_input_tokens": int(payload.get("total_input_tokens", 0)),
        "total_output_tokens": int(payload.get("total_output_tokens", 0)),
    }


def _resolve_rates(setup: dict, model: str) -> dict | None:
    """Look up per-million-token rates for `model` from setup.costs; None if absent."""
    costs = setup.get("costs", {}) or {}
    entry = costs.get(model)
    if not entry:
        return None
    return {
        "input_per_million_tokens": float(entry.get("input_per_million_tokens", 0.0)),
        "output_per_million_tokens": float(entry.get("output_per_million_tokens", 0.0)),
    }


def _estimate_usd(summary: dict, rates: dict | None) -> float:
    if rates is None:
        return 0.0
    in_cost = summary["total_input_tokens"] * rates["input_per_million_tokens"] / 1_000_000
    out_cost = summary["total_output_tokens"] * rates["output_per_million_tokens"] / 1_000_000
    return round(in_cost + out_cost, 6)


def aggregate_costs(
    setup: dict,
    pro_cost_path: Path | None,
    con_cost_path: Path | None,
    judge_cost_path: Path | None,
) -> dict:
    """Aggregate per-agent gatekeeper cost dumps into a debate-level summary.

    Returns a dict shaped:
        {
          "total_calls": int,
          "total_input_tokens": int,
          "total_output_tokens": int,
          "total_tokens": int,
          "estimated_cost_usd": float,
          "per_agent": {
            "Agent_Pro":   {summary..., "model": "...", "estimated_cost_usd": float},
            "Agent_Con":   {...},
            "Agent_Judge": {...},
          },
        }
    Returns an empty dict when no cost files were produced.
    """
    provider_name = setup.get("provider", {}).get("active", "anthropic").lower()
    provider_cfg = setup.get("provider", {}).get(provider_name, {})
    debater_model = provider_cfg.get("debater_model", "")
    judge_model = provider_cfg.get("judge_model", "")

    debater_rates = _resolve_rates(setup, debater_model)
    judge_rates = _resolve_rates(setup, judge_model)

    pro = _read_summary(pro_cost_path)
    con = _read_summary(con_cost_path)
    judge = _read_summary(judge_cost_path)

    if pro["total_calls"] + con["total_calls"] + judge["total_calls"] == 0:
        return {}

    pro_usd = _estimate_usd(pro, debater_rates)
    con_usd = _estimate_usd(con, debater_rates)
    judge_usd = _estimate_usd(judge, judge_rates)

    total_in = pro["total_input_tokens"] + con["total_input_tokens"] + judge["total_input_tokens"]
    total_out = pro["total_output_tokens"] + con["total_output_tokens"] + judge["total_output_tokens"]
    total_calls = pro["total_calls"] + con["total_calls"] + judge["total_calls"]

    return {
        "total_calls": total_calls,
        "total_input_tokens": total_in,
        "total_output_tokens": total_out,
        "total_tokens": total_in + total_out,
        "estimated_cost_usd": round(pro_usd + con_usd + judge_usd, 6),
        "per_agent": {
            "Agent_Pro": {**pro, "model": debater_model, "estimated_cost_usd": pro_usd},
            "Agent_Con": {**con, "model": debater_model, "estimated_cost_usd": con_usd},
            "Agent_Judge": {**judge, "model": judge_model, "estimated_cost_usd": judge_usd},
        },
    }
