"""LLM provider factory — returns callables for Anthropic or Gemini.

Active provider is resolved in priority order:
  1. LLM_PROVIDER environment variable
  2. setup.json  provider.active field
  3. Hard-coded default ("anthropic")
"""

import os

from debate.shared.llm_anthropic import (
    make_anthropic_evaluate_llm,
    make_anthropic_route_llm,
    make_anthropic_text_llm,
    make_anthropic_verdict_llm,
)
from debate.shared.llm_gemini import (
    _gemini_client,  # noqa: F401  (re-exported for test patching)
    make_gemini_evaluate_llm,
    make_gemini_route_llm,
    make_gemini_text_llm,
    make_gemini_verdict_llm,
)
from debate.shared.llm_retry import (  # noqa: F401  (re-exported for test imports)
    _extract_json,
    _is_daily_quota,
    _is_rate_limit,
    _retry,
    _suggested_delay,
)

_PROVIDER_ENV_VAR = "LLM_PROVIDER"
_DEFAULT_PROVIDER = "anthropic"


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
        return make_gemini_text_llm(model, temperature, max_tokens)
    return make_anthropic_text_llm(model, temperature, max_tokens)


def make_judge_evaluate_llm(setup: dict):
    """Return (prompt: str) -> dict callable. The prompt — including the scoring rubric — is rendered by evaluate_persuasion_score SKILL.md."""
    provider = get_active_provider(setup)
    cfg = _provider_cfg(setup, provider)
    model = cfg.get("judge_model", _default_model(provider))
    if provider == "gemini":
        return make_gemini_evaluate_llm(model)
    return make_anthropic_evaluate_llm(model)


def make_judge_route_llm(setup: dict):
    """Return (prompt: str) -> str callable used by RouteTurn to generate feedback."""
    provider = get_active_provider(setup)
    cfg = _provider_cfg(setup, provider)
    model = cfg.get("judge_model", _default_model(provider))
    if provider == "gemini":
        return make_gemini_route_llm(model)
    return make_anthropic_route_llm(model)


def make_judge_verdict_llm(setup: dict):
    """Return (prompt: str) -> str callable for the final LLM-generated verdict."""
    provider = get_active_provider(setup)
    cfg = _provider_cfg(setup, provider)
    model = cfg.get("judge_model", _default_model(provider))
    if provider == "gemini":
        return make_gemini_verdict_llm(model)
    return make_anthropic_verdict_llm(model)


def _provider_cfg(setup: dict, provider: str) -> dict:
    return setup.get("provider", {}).get(provider, {})


def _default_model(provider: str) -> str:
    return "gemini-1.5-flash" if provider == "gemini" else "claude-sonnet-4-6"
