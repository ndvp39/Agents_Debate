"""Google Gemini LLM callables for debater, evaluate, and route roles."""

import os

from debate.shared.llm_retry import _extract_json, _retry

_EVALUATE_PROMPT = (
    "You are an impartial, stateless debate judge. Evaluate THIS argument on its own merits.\n"
    "ZERO-ANCHORING: Do NOT favour either side. If a devastating counter-argument is "
    "delivered, shift scores immediately — ignore all prior scoring patterns.\n\n"
    "Score on three dimensions (0.0 to 1.0):\n"
    "• logical_consistency — Causal coherence; exploits opponent's weakest point. "
    "PENALISE: circular reasoning, unsupported assertions, ignoring a direct attack, "
    "repeating prior claims without new angles.\n"
    "• citation_strength — Specific, credible, contextually relevant sourcing. "
    "PENALISE: repeating the same sources from a prior round without new evidence.\n"
    "• rhetoric_quality — Effective ethos, pathos, logos; memorability; persuasiveness.\n\n"
)


def _gemini_client():
    from google import genai
    return genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))


def make_gemini_text_llm(model: str, temperature: float, max_tokens: int):
    from google.genai import types
    client = _gemini_client()
    cfg = types.GenerateContentConfig(temperature=temperature, max_output_tokens=max_tokens)

    def llm_call(prompt: str) -> str:
        return _retry(lambda: client.models.generate_content(
            model=model, contents=prompt, config=cfg,
        ).text)

    return llm_call


def make_gemini_evaluate_llm(model: str):
    from google.genai import types
    client = _gemini_client()
    cfg = types.GenerateContentConfig(max_output_tokens=2048)

    def evaluate_llm(argument: str, citations: list) -> dict:
        prompt = (
            _EVALUATE_PROMPT
            + f"{argument}\nCitations: {citations}\n\n"
            "Reply with ONLY a raw JSON object, no markdown, no code fences:\n"
            '{"logical_consistency": <float>, "citation_strength": <float>, "rhetoric_quality": <float>}'
        )
        text = _retry(lambda: client.models.generate_content(
            model=model, contents=prompt, config=cfg,
        ).text)
        return _extract_json(text)

    return evaluate_llm


def make_gemini_route_llm(model: str):
    from google.genai import types
    client = _gemini_client()
    cfg = types.GenerateContentConfig(max_output_tokens=200)

    def route_llm(prompt: str) -> str:
        return _retry(lambda: client.models.generate_content(
            model=model, contents=prompt, config=cfg,
        ).text)

    return route_llm


def make_gemini_verdict_llm(model: str):
    from google.genai import types
    client = _gemini_client()
    cfg = types.GenerateContentConfig(max_output_tokens=800)

    def verdict_llm(prompt: str) -> str:
        return _retry(lambda: client.models.generate_content(
            model=model, contents=prompt, config=cfg,
        ).text)

    return verdict_llm
