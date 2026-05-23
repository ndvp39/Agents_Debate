"""LLM provider factory — returns callables for Anthropic or Gemini.

Active provider is resolved in priority order:
  1. LLM_PROVIDER environment variable
  2. setup.json  provider.active field
  3. Hard-coded default ("anthropic")

All API calls include exponential-backoff retry for transient rate-limit errors.
"""

import json
import os
import time

_PROVIDER_ENV_VAR = "LLM_PROVIDER"
_DEFAULT_PROVIDER = "anthropic"
_MAX_RETRIES = 4
_RETRY_BASE_DELAY = 5.0  # seconds; doubles each attempt


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
    """Extract the first JSON object from a text response."""
    start = text.find("{")
    end = text.rfind("}") + 1
    return json.loads(text[start:end])


def _retry(fn):
    """Call fn(); retry up to _MAX_RETRIES times with exponential backoff."""
    for attempt in range(_MAX_RETRIES + 1):
        try:
            return fn()
        except Exception as exc:
            if attempt == _MAX_RETRIES:
                raise
            delay = _RETRY_BASE_DELAY * (2 ** attempt)
            time.sleep(delay)


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
            "Reply with ONLY a JSON object:\n"
            '{"logical_consistency": <float>, "citation_strength": <float>, "rhetoric_quality": <float>}'
        )
        text = _retry(lambda: client.messages.create(
            model=model, max_tokens=150,
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
    cfg = types.GenerateContentConfig(max_output_tokens=200)

    def evaluate_llm(argument: str, citations: list) -> dict:
        prompt = (
            "Score this debate argument on three dimensions from 0.0 to 1.0.\n"
            f"Argument: {argument}\nCitations: {citations}\n\n"
            "Reply with ONLY a JSON object:\n"
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
