"""Anthropic Claude LLM callables for debater, evaluate, and route roles."""

from debate.shared.llm_retry import _extract_json, _retry


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

    def evaluate_llm(prompt: str) -> dict:
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
