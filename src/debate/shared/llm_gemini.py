"""Google Gemini LLM callables for debater, evaluate, and route roles.

Every closure here can be wrapped through an `ApiGatekeeper` for centralized
rate-limiting, retry, and cost accounting. When a gatekeeper is provided:
* the API request goes through `gatekeeper.execute(...)` (no bypass possible).
* response.usage_metadata.{prompt_token_count, candidates_token_count} is
  reported via `gatekeeper.record_tokens` so the cost summary reflects real,
  server-returned token counts.
"""

import contextlib
import os
from typing import Any

from debate.shared.gatekeeper import ApiGatekeeper
from debate.shared.llm_retry import _extract_json, _retry


def _gemini_client():
    from google import genai
    return genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))


def _call_and_record(
    client_call,
    gatekeeper: ApiGatekeeper | None,
) -> Any:
    """Run `client_call` through the gatekeeper (when given), then record tokens."""
    if gatekeeper is None:
        return _retry(client_call)
    response = gatekeeper.execute(lambda: _retry(client_call))
    with contextlib.suppress(AttributeError, TypeError):
        usage = response.usage_metadata
        gatekeeper.record_tokens(
            int(getattr(usage, "prompt_token_count", 0) or 0),
            int(getattr(usage, "candidates_token_count", 0) or 0),
        )
    return response


def make_gemini_text_llm(
    model: str,
    temperature: float,
    max_tokens: int,
    gatekeeper: ApiGatekeeper | None = None,
):
    from google.genai import types
    client = _gemini_client()
    cfg = types.GenerateContentConfig(temperature=temperature, max_output_tokens=max_tokens)

    def llm_call(prompt: str) -> str:
        def _do():
            return client.models.generate_content(
                model=model, contents=prompt, config=cfg,
            )
        response = _call_and_record(_do, gatekeeper)
        return response.text

    return llm_call


def make_gemini_evaluate_llm(model: str, gatekeeper: ApiGatekeeper | None = None):
    from google.genai import types
    client = _gemini_client()
    cfg = types.GenerateContentConfig(max_output_tokens=2048)

    def evaluate_llm(prompt: str) -> dict:
        def _do():
            return client.models.generate_content(
                model=model, contents=prompt, config=cfg,
            )
        response = _call_and_record(_do, gatekeeper)
        return _extract_json(response.text)

    return evaluate_llm


def make_gemini_route_llm(model: str, gatekeeper: ApiGatekeeper | None = None):
    from google.genai import types
    client = _gemini_client()
    cfg = types.GenerateContentConfig(max_output_tokens=200)

    def route_llm(prompt: str) -> str:
        def _do():
            return client.models.generate_content(
                model=model, contents=prompt, config=cfg,
            )
        response = _call_and_record(_do, gatekeeper)
        return response.text

    return route_llm


def make_gemini_verdict_llm(model: str, gatekeeper: ApiGatekeeper | None = None):
    from google.genai import types
    client = _gemini_client()
    cfg = types.GenerateContentConfig(max_output_tokens=800)

    def verdict_llm(prompt: str) -> str:
        def _do():
            return client.models.generate_content(
                model=model, contents=prompt, config=cfg,
            )
        response = _call_and_record(_do, gatekeeper)
        return response.text

    return verdict_llm
