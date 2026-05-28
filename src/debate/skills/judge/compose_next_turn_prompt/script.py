"""Deterministic next-turn-prompt composer: build the literal handoff string."""


def run(next_agent: str, judge_feedback_reminder: str = "") -> str:
    base = f"It is your turn now, {next_agent}. Respond directly to the previous argument."
    if judge_feedback_reminder:
        return f"{base} {judge_feedback_reminder}"
    return base
