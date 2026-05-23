"""LLM provider factory — returns callables for Anthropic or Gemini.

Active provider is resolved in priority order:
  1. LLM_PROVIDER environment variable
  2. setup.json  provider.active field
  3. Hard-coded default ("anthropic")

All API calls include exponential-backoff retry for transient rate-limit errors.
"""

import json
import os
import re
import time

_PROVIDER_ENV_VAR = "LLM_PROVIDER"
_DEFAULT_PROVIDER = "anthropic"
_MAX_RETRIES = 4
_RETRY_BASE_DELAY = 5.0  # seconds; doubles each attempt

# Substrings that identify a *daily* quota violation inside a 429 message.
_DAILY_QUOTA_MARKERS = ("PerDay", "per_day", "daily")


# ------------------------------------------------------------------
# Public API
# ------------------------------------------------------------------

def get_active_provider(setup: dict) -> str:
    """Return the active provider name (lowercase)."""
    from_env = os.getenv(_PROVIDER_ENV_VAR, "").strip().lower()
    if from_env:
        return from_env
    return setup.get("provider", {}).get("active", _DEFAULT_PROVIDER).lower()


def make_debater_llm(setup: dict):
    """Return (prompt: str) -> str callable for the active provider."""
    provider = get_active_provider(setup)
    cfg = _provider_cfg(setup, provider)
    model = cfg.get("debater_model", _default_model(provider))
    temperature = cfg.get("temperature", 0.7)
    max_tokens = cfg.get("max_tokens", 1024)
    if provider == "gemini":
        return _gemini_text_llm(model, temperature, max_tokens)
    return _anthropic_text_llm(model, temperature, max_tokens)


def make_judge_evaluate_llm(setup: dict):
    """Return (argument: str, citations: list) -> dict callable."""
    provider = get_active_provider(setup)
    cfg = _provider_cfg(setup, provider)
    model = cfg.get("judge_model", _default_model(provider))
    if provider == "gemini":
        return _gemini_evaluate_llm(model)
    return _anthropic_evaluate_llm(model)


def make_judge_route_llm(setup: dict):
    """Return (score) -> str callable."""
    provider = get_active_provider(setup)
    cfg = _provider_cfg(setup, provider)
    model = cfg.get("judge_model", _default_model(provider))
    if provider == "gemini":
        return _gemini_route_llm(model)
    return _anthropic_route_llm(model)


# ------------------------------------------------------------------
# Internal helpers
# ------------------------------------------------------------------

def _provider_cfg(setup: dict, provider: str) -> dict:
    return setup.get("provider", {}).get(provider, {})


def _default_model(provider: str) -> str:
    return "gemini-1.5-flash" if provider == "gemini" else "claude-sonnet-4-6"


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
        return float(m.group(1)) + 2  # small buffer
    m = re.search(r'"retryDelay"\s*:\s*"(\d+(?:\.\d+)?)s"', msg)
    if m:
        return float(m.group(1)) + 2
    return None


def _retry(fn):
    """Smart retry: wait the provider-suggested delay for transient limits;
    raise immediately with a clear message for daily quota exhaustion."""
    for attempt in range(_MAX_RETRIES + 1):
        try:
            return fn()
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


# ------------------------------------------------------------------
# Anthropic implementations
# ------------------------------------------------------------------

def _anthropic_text_llm(model: str, temperature: float, max_tokens: int):
    import anthropic
    client = anthropic.Anthropic()

    def llm_call(prompt: str) -> str:
        return _retry(lambda: client.messages.create(
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            messages=[{"role": "user", "content": prompt}],
        ).content[0].text)

    return llm_call


def _anthropic_evaluate_llm(model: str):
    import anthropic
    client = anthropic.Anthropic()

    def evaluate_llm(argument: str, citations: list) -> dict:
        prompt = (
            "Score this debate argument on three dimensions from 0.0 to 1.0.\n"
            f"Argument: {argument}\nCitations: {citations}\n\n"
            "Reply with ONLY a raw JSON object, no markdown, no code fences:\n"
            '{"logical_consistency": <float>, "citation_strength": <float>, "rhetoric_quality": <float>}'
        )
        text = _retry(lambda: client.messages.create(
            model=model, max_tokens=256,
            messages=[{"role": "user", "content": prompt}],
        ).content[0].text)
        return _extract_json(text)

    return evaluate_llm


def _anthropic_route_llm(model: str):
    import anthropic
    client = anthropic.Anthropic()

    def route_llm(score) -> str:
        prompt = (
            f"A debate argument scored: logic={score.logical_consistency:.2f}, "
            f"citation={score.citation_strength:.2f}, rhetoric={score.rhetoric_quality:.2f}. "
            "Give 1-2 sentences of constructive feedback."
        )
        return _retry(lambda: client.messages.create(
            model=model, max_tokens=150,
            messages=[{"role": "user", "content": prompt}],
        ).content[0].text)

    return route_llm


# ------------------------------------------------------------------
# Gemini implementations  (google-genai SDK)
# ------------------------------------------------------------------

def _gemini_client():
    from google import genai
    return genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))


def _gemini_text_llm(model: str, temperature: float, max_tokens: int):
    from google.genai import types
    client = _gemini_client()
    cfg = types.GenerateContentConfig(temperature=temperature, max_output_tokens=max_tokens)

    def llm_call(prompt: str) -> str:
        return _retry(lambda: client.models.generate_content(
            model=model, contents=prompt, config=cfg,
        ).text)

    return llm_call


def _gemini_evaluate_llm(model: str):
    from google.genai import types
    client = _gemini_client()
    cfg = types.GenerateContentConfig(max_output_tokens=2048)

    def evaluate_llm(argument: str, citations: list) -> dict:
        prompt = (
            "Score this debate argument on three dimensions from 0.0 to 1.0.\n"
            f"Argument: {argument}\nCitations: {citations}\n\n"
            "Reply with ONLY a raw JSON object, no markdown, no code fences:\n"
            '{"logical_consistency": <float>, "citation_strength": <float>, "rhetoric_quality": <float>}'
        )
        text = _retry(lambda: client.models.generate_content(
            model=model, contents=prompt, config=cfg,
        ).text)
        return _extract_json(text)

    return evaluate_llm


def _gemini_route_llm(model: str):
    from google.genai import types
    client = _gemini_client()
    cfg = types.GenerateContentConfig(max_output_tokens=150)

    def route_llm(score) -> str:
        prompt = (
            f"A debate argument scored: logic={score.logical_consistency:.2f}, "
            f"citation={score.citation_strength:.2f}, rhetoric={score.rhetoric_quality:.2f}. "
            "Give 1-2 sentences of constructive feedback."
        )
        return _retry(lambda: client.models.generate_content(
            model=model, contents=prompt, config=cfg,
        ).text)

    return route_llm
