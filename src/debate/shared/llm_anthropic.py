"""Anthropic Claude LLM callables for debater, evaluate, and route roles.

Every closure here can be wrapped through an `ApiGatekeeper` for centralized
rate-limiting, retry, and cost accounting. When a gatekeeper is provided:
* the API request goes through `gatekeeper.execute(...)` (no bypass possible).
* response.usage.{input,output}_tokens is reported via `gatekeeper.record_tokens`
  so the cost summary reflects real, server-returned token counts.
"""

import contextlib
from typing import Any

from debate.shared.gatekeeper import ApiGatekeeper
from debate.shared.llm_retry import _extract_json, _retry


def _call_and_record(
    client_call,
    gatekeeper: ApiGatekeeper | None,
) -> Any:
    """Run `client_call` through the gatekeeper (when given), then record tokens."""
    if gatekeeper is None:
        return _retry(client_call)
    response = gatekeeper.execute(lambda: _retry(client_call))
    with contextlib.suppress(AttributeError, TypeError):
        usage = response.usage
        gatekeeper.record_tokens(
            int(getattr(usage, "input_tokens", 0) or 0),
            int(getattr(usage, "output_tokens", 0) or 0),
        )
    return response


def make_anthropic_text_llm(
    model: str,
    temperature: float,
    max_tokens: int,
    gatekeeper: ApiGatekeeper | None = None,
):
    import anthropic
    client = anthropic.Anthropic()

    def llm_call(prompt: str) -> str:
        def _do():
            return client.messages.create(
                model=model, max_tokens=max_tokens, temperature=temperature,
                messages=[{"role": "user", "content": prompt}],
            )
        response = _call_and_record(_do, gatekeeper)
        return response.content[0].text

    return llm_call


def make_anthropic_evaluate_llm(model: str, gatekeeper: ApiGatekeeper | None = None):
    import anthropic
    client = anthropic.Anthropic()

    def evaluate_llm(prompt: str) -> dict:
        def _do():
            return client.messages.create(
                model=model, max_tokens=256,
                messages=[{"role": "user", "content": prompt}],
            )
        response = _call_and_record(_do, gatekeeper)
        return _extract_json(response.content[0].text)

    return evaluate_llm


def make_anthropic_route_llm(model: str, gatekeeper: ApiGatekeeper | None = None):
    import anthropic
    client = anthropic.Anthropic()

    def route_llm(prompt: str) -> str:
        def _do():
            return client.messages.create(
                model=model, max_tokens=200,
                messages=[{"role": "user", "content": prompt}],
            )
        response = _call_and_record(_do, gatekeeper)
        return response.content[0].text

    return route_llm


def make_anthropic_verdict_llm(model: str, gatekeeper: ApiGatekeeper | None = None):
    import anthropic
    client = anthropic.Anthropic()

    def verdict_llm(prompt: str) -> str:
        def _do():
            return client.messages.create(
                model=model, max_tokens=800,
                messages=[{"role": "user", "content": prompt}],
            )
        response = _call_and_record(_do, gatekeeper)
        return response.content[0].text

    return verdict_llm
