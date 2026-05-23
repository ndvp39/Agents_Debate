"""Subprocess entry point for the Judge agent."""

import json
import sys

import anthropic

from debate.agents.judge.judge_agent import JudgeAgent
from debate.ipc.schemas import ArgumentMessage
from debate.shared.constants import MessageType


def _make_evaluate_llm():
    client = anthropic.Anthropic()

    def evaluate_llm(argument: str, citations: list) -> dict:
        prompt = (
            "Score this debate argument on three dimensions from 0.0 to 1.0.\n"
            f"Argument: {argument}\n"
            f"Citations: {citations}\n\n"
            "Reply with ONLY a JSON object, no explanation:\n"
            '{"logical_consistency": <float>, "citation_strength": <float>, "rhetoric_quality": <float>}'
        )
        resp = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=150,
            messages=[{"role": "user", "content": prompt}],
        )
        text = resp.content[0].text.strip()
        start = text.find("{")
        end = text.rfind("}") + 1
        return json.loads(text[start:end])

    return evaluate_llm


def _make_route_llm():
    client = anthropic.Anthropic()

    def route_llm(score) -> str:
        prompt = (
            f"A debate argument scored: logical_consistency={score.logical_consistency:.2f}, "
            f"citation_strength={score.citation_strength:.2f}, "
            f"rhetoric_quality={score.rhetoric_quality:.2f} (weighted={score.weighted:.2f}). "
            "Give 1-2 sentences of constructive feedback."
        )
        resp = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=150,
            messages=[{"role": "user", "content": prompt}],
        )
        return resp.content[0].text

    return route_llm


def main() -> None:
    agent = JudgeAgent(
        evaluate_llm=_make_evaluate_llm(),
        route_llm=_make_route_llm(),
    )
    agent.start()

    while True:
        try:
            msg = agent.receive()
        except Exception as exc:
            print(f"judge_runner: receive error: {exc}", file=sys.stderr)
            break

        msg_type = msg.get("message_type")
        if msg_type == MessageType.ARGUMENT:
            try:
                arg_msg = ArgumentMessage.from_dict(msg)
                agent.process_argument(arg_msg)
            except Exception as exc:
                print(f"judge_runner: process_argument error: {exc}", file=sys.stderr)
                break
        elif msg_type == "verdict_request":
            try:
                agent.declare_verdict()
            except Exception as exc:
                print(f"judge_runner: declare_verdict error: {exc}", file=sys.stderr)
            break
        else:
            print(f"judge_runner: unknown message_type {msg_type!r}", file=sys.stderr)
            break


if __name__ == "__main__":
    main()
