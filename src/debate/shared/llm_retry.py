"""Shared retry logic and JSON helper for LLM provider implementations.

`_retry` emits a structured INFO log line on success and WARNING on every
retry/backoff event, with a caller-supplied `label` identifying the agent role
and call purpose (e.g. "Agent_Pro.debater", "Agent_Judge.evaluate"). The lines
go to stderr via stdlib logging — inherited by the subprocess parent, so they
show up in the SDK's run log alongside the watchdog/orchestrator events.
"""

import json
import logging
import re
import time

_MAX_RETRIES = 4
_RETRY_BASE_DELAY = 5.0
_DAILY_QUOTA_MARKERS = ("PerDay", "per_day", "daily")
_EMPTY_MAX_RETRIES = 3
_EMPTY_RETRY_DELAY = 2.0

_log = logging.getLogger("debate.llm")


def _extract_json(text: str) -> dict:
    """Extract the first JSON object from a text response (handles markdown fences)."""
    if not text:
        raise ValueError("Empty LLM response")
    start = text.find("{")
    end = text.rfind("}") + 1
    if start == -1 or end == 0:
        raise ValueError(f"No JSON object found in: {text!r}")
    return json.loads(text[start:end])


def _is_rate_limit(exc: Exception) -> bool:
    msg = str(exc)
    return "429" in msg or "RESOURCE_EXHAUSTED" in msg or "RateLimitError" in type(exc).__name__


def _is_daily_quota(exc: Exception) -> bool:
    msg = str(exc)
    return any(marker in msg for marker in _DAILY_QUOTA_MARKERS)


def _suggested_delay(exc: Exception) -> float | None:
    """Extract the provider-recommended wait time (seconds) from a 429 response."""
    msg = str(exc)
    m = re.search(r"retry in (\d+(?:\.\d+)?)", msg, re.IGNORECASE)
    if m:
        return float(m.group(1)) + 2
    m = re.search(r'"retryDelay"\s*:\s*"(\d+(?:\.\d+)?)s"', msg)
    if m:
        return float(m.group(1)) + 2
    return None


def _retry(fn, label: str = "llm"):
    """Smart retry: wait provider-suggested delay for transient limits;
    raise immediately for daily quota exhaustion;
    retry up to _EMPTY_MAX_RETRIES times on empty/None responses.

    Emits per-attempt timing logs so operators can see exactly where wall-clock
    time is going (real API time vs backoff sleeps vs empty-response retries).
    """
    overall_start = time.time()
    empty_count = 0
    for attempt in range(_MAX_RETRIES + 1):
        attempt_start = time.time()
        try:
            result = fn()
        except Exception as exc:
            took = time.time() - attempt_start
            if _is_rate_limit(exc):
                if _is_daily_quota(exc):
                    _log.error("[%s] attempt=%d took=%.2fs result=DAILY_QUOTA exc=%s",
                               label, attempt + 1, took, type(exc).__name__)
                    raise RuntimeError(
                        "Daily API quota exhausted — please try again tomorrow."
                    ) from exc
                if attempt < _MAX_RETRIES:
                    delay = _suggested_delay(exc) or _RETRY_BASE_DELAY * (2 ** attempt)
                    _log.warning(
                        "[%s] attempt=%d took=%.2fs result=rate_limit backoff=%.1fs",
                        label, attempt + 1, took, delay,
                    )
                    time.sleep(delay)
                    continue
            if attempt == _MAX_RETRIES:
                _log.error(
                    "[%s] attempt=%d took=%.2fs result=FATAL exc=%s",
                    label, attempt + 1, took, type(exc).__name__,
                )
                raise
            delay = _RETRY_BASE_DELAY * (2 ** attempt)
            _log.warning(
                "[%s] attempt=%d took=%.2fs result=error backoff=%.1fs exc=%s",
                label, attempt + 1, took, delay, type(exc).__name__,
            )
            time.sleep(delay)
        else:
            took = time.time() - attempt_start
            if result is None or (isinstance(result, str) and not result.strip()):
                empty_count += 1
                if empty_count <= _EMPTY_MAX_RETRIES:
                    _log.warning(
                        "[%s] attempt=%d took=%.2fs result=empty backoff=%.1fs",
                        label, attempt + 1, took, _EMPTY_RETRY_DELAY,
                    )
                    time.sleep(_EMPTY_RETRY_DELAY)
                    continue
                _log.error(
                    "[%s] attempt=%d took=%.2fs result=empty_exhausted",
                    label, attempt + 1, took,
                )
                raise ValueError(f"LLM returned empty response after {_EMPTY_MAX_RETRIES} retries")
            total = time.time() - overall_start
            _log.info(
                "[%s] attempt=%d took=%.2fs result=ok total=%.2fs",
                label, attempt + 1, took, total,
            )
            return result
