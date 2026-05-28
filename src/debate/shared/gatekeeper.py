"""Centralized API gatekeeper — all external calls must go through here.

The gatekeeper owns **rate limiting / queueing / cost tracking** only. It does
NOT retry api_call: the inner `_retry()` in `llm_retry.py` already implements
provider-aware retry (Gemini `retry_in` hints, daily-quota fail-fast, empty-
response replays) and a gatekeeper-level retry would double-retry on every
transient failure and — worse — retry on fatal exhaustion errors that the
inner layer correctly raises (live diagnostics showed this inflating turns
by 30/60/120s).

`execute(api_call, ...)`:
1. Waits for rate-limit capacity (or `BackpressureError` if the queue is full).
2. Calls api_call **exactly once**.
3. On success, appends a timestamp to the sliding history and records cost.
4. On any exception, propagates immediately — never sleeps, never retries.
"""

import json
import os
import tempfile
import threading
import time
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from debate.shared.config import ConfigManager
from debate.shared.exceptions import BackpressureError


@dataclass
class _CostAccumulator:
    """Tracks cumulative token usage across all API calls."""

    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_calls: int = 0

    def record(self, input_tokens: int, output_tokens: int) -> None:
        self.total_input_tokens += input_tokens
        self.total_output_tokens += output_tokens
        self.total_calls += 1


class ApiGatekeeper:
    """Rate-limiting, queueing, and cost-accounting proxy for external API calls.

    Retry policy lives in the inner `_retry()`, not here — see module docstring.

    `requests_per_minute` / `requests_per_hour`: sliding-window admission limits.
    `queue_max_depth`: backpressure cap.
    `max_retries` / `retry_after_seconds`: read from config for backward
        compatibility but no longer used (kept so the existing rate_limits.json
        schema doesn't need a migration).

    `cost_dump_path` (optional): atomic write of `get_cost_summary()` after
    each successful call — lets a parent process aggregate per-subprocess cost
    without IPC plumbing.
    """

    def __init__(
        self,
        config: ConfigManager,
        service: str = "default",
        cost_dump_path: Path | None = None,
    ) -> None:
        svc = self._service_cfg(config, service)
        self._rpm: int = svc["requests_per_minute"]
        self._rph: int = svc["requests_per_hour"]
        self._queue_max: int = svc["queue_max_depth"]
        self._history: deque[float] = deque()
        self._queue: deque[bool] = deque()
        self._lock = threading.Lock()
        self._cost = _CostAccumulator()
        self._cost_dump_path: Path | None = (
            Path(cost_dump_path) if cost_dump_path else None
        )

    @staticmethod
    def _service_cfg(config: ConfigManager, service: str) -> dict:
        services = config.get_rate_limits()["services"]
        return services.get(service, services["default"])

    def _prune_history(self) -> None:
        now = time.time()
        while self._history and now - self._history[0] > 3600:
            self._history.popleft()

    def _within_limits(self) -> bool:
        self._prune_history()
        now = time.time()
        per_min = sum(1 for t in self._history if now - t <= 60)
        return per_min < self._rpm and len(self._history) < self._rph

    def _wait_for_capacity(self) -> None:
        with self._lock:
            if self._within_limits():
                return
            if len(self._queue) >= self._queue_max:
                raise BackpressureError("Gatekeeper queue is full")
            self._queue.append(True)
        while True:
            time.sleep(0.5)
            with self._lock:
                if self._within_limits():
                    if self._queue:
                        self._queue.popleft()
                    return

    def execute(self, api_call: Callable, *args: Any, **kwargs: Any) -> Any:
        """Wait for capacity, call api_call once, record cost on success.

        Any exception from api_call propagates immediately — the inner
        `_retry()` already owns retry policy.
        """
        input_tokens: int = kwargs.pop("_input_tokens", 0)
        output_tokens: int = kwargs.pop("_output_tokens", 0)
        self._wait_for_capacity()
        result = api_call(*args, **kwargs)  # may raise — propagates as-is
        with self._lock:
            self._history.append(time.time())
            self._cost.record(input_tokens, output_tokens)
        self._dump_cost()
        return result

    def record_tokens(self, input_tokens: int, output_tokens: int) -> None:
        """Add token usage to the accumulator WITHOUT bumping `total_calls`.

        Use this after `execute()` returns to record real usage extracted from
        the provider's response (e.g. response.usage on Anthropic). It complements
        the pre-call kwargs path used by callers that can estimate tokens upfront.
        """
        with self._lock:
            self._cost.total_input_tokens += input_tokens
            self._cost.total_output_tokens += output_tokens
        self._dump_cost()

    def _dump_cost(self) -> None:
        """Atomically write the running cost summary to the dump path, if set."""
        if self._cost_dump_path is None:
            return
        payload = self.get_cost_summary()
        path = self._cost_dump_path
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            fd, tmp_name = tempfile.mkstemp(
                prefix=path.name + ".", suffix=".tmp", dir=str(path.parent),
            )
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(payload, fh)
            os.replace(tmp_name, path)
        except OSError:
            # Cost reporting is best-effort; never crash the request path.
            pass

    def get_queue_status(self) -> dict:
        """Return current queue depth."""
        return {"queue_depth": len(self._queue)}

    def get_cost_summary(self) -> dict:
        """Return accumulated token usage totals."""
        return {
            "total_calls": self._cost.total_calls,
            "total_input_tokens": self._cost.total_input_tokens,
            "total_output_tokens": self._cost.total_output_tokens,
        }
