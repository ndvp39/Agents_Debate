"""Anthropic Claude LLM callables for debater, evaluate, and route roles."""

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


def make_anthropic_text_llm(model: str, temperature: float, max_tokens: int):
    import anthropic
    client = anthropic.Anthropic()

    def llm_call(prompt: str) -> str:
        return _retry(lambda: client.messages.create(
            model=model, max_tokens=max_tokens, temperature=temperature,
            messages=[{"role": "user", "content": prompt}],
        ).content[0].text)

    return llm_call


def make_anthropic_evaluate_llm(model: str):
    import anthropic
    client = anthropic.Anthropic()

    def evaluate_llm(argument: str, citations: list) -> dict:
        prompt = (
            _EVALUATE_PROMPT
            + f"{argument}\nCitations: {citations}\n\n"
            "Reply with ONLY a raw JSON object, no markdown, no code fences:\n"
            '{"logical_consistency": <float>, "citation_strength": <float>, "rhetoric_quality": <float>}'
        )
        text = _retry(lambda: client.messages.create(
            model=model, max_tokens=256,
            messages=[{"role": "user", "content": prompt}],
        ).content[0].text)
        return _extract_json(text)

    return evaluate_llm


def make_anthropic_route_llm(model: str):
    import anthropic
    client = anthropic.Anthropic()

    def route_llm(prompt: str) -> str:
        return _retry(lambda: client.messages.create(
            model=model, max_tokens=200,
            messages=[{"role": "user", "content": prompt}],
        ).content[0].text)

    return route_llm


def make_anthropic_verdict_llm(model: str):
    import anthropic
    client = anthropic.Anthropic()

    def verdict_llm(prompt: str) -> str:
        return _retry(lambda: client.messages.create(
            model=model, max_tokens=800,
            messages=[{"role": "user", "content": prompt}],
        ).content[0].text)

    return verdict_llm
