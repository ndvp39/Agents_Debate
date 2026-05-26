"""Shared retry logic and JSON helper for LLM provider implementations."""

import json
import re
import time

_MAX_RETRIES = 4
_RETRY_BASE_DELAY = 5.0
_DAILY_QUOTA_MARKERS = ("PerDay", "per_day", "daily")
_EMPTY_MAX_RETRIES = 3
_EMPTY_RETRY_DELAY = 2.0


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


def _retry(fn):
    """Smart retry: wait provider-suggested delay for transient limits;
    raise immediately for daily quota exhaustion;
    retry up to _EMPTY_MAX_RETRIES times on empty/None responses."""
    empty_count = 0
    for attempt in range(_MAX_RETRIES + 1):
        try:
            result = fn()
        except Exception as exc:
            if _is_rate_limit(exc):
                if _is_daily_quota(exc):
                    raise RuntimeError(
                        "Daily API quota exhausted — please try again tomorrow."
                    ) from exc
                if attempt < _MAX_RETRIES:
                    delay = _suggested_delay(exc) or _RETRY_BASE_DELAY * (2 ** attempt)
                    time.sleep(delay)
                    continue
            if attempt == _MAX_RETRIES:
                raise
            time.sleep(_RETRY_BASE_DELAY * (2 ** attempt))
        else:
            if result is None or (isinstance(result, str) and not result.strip()):
                empty_count += 1
                if empty_count <= _EMPTY_MAX_RETRIES:
                    time.sleep(_EMPTY_RETRY_DELAY)
                    continue
                raise ValueError(f"LLM returned empty response after {_EMPTY_MAX_RETRIES} retries")
            return result
