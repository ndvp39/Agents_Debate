"""Subprocess entry point for the Con debater agent."""

import argparse
import sys

import anthropic

from debate.agents.debaters.con_agent import ConAgent
from debate.shared.constants import MessageType


def _make_llm():
    client = anthropic.Anthropic()

    def llm_call(prompt: str) -> str:
        resp = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )
        return resp.content[0].text

    return llm_call


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--topic", required=True)
    args = parser.parse_args()

    agent = ConAgent(
        topic=args.topic,
        llm_call=_make_llm(),
        search_call=lambda q: [],
    )
    agent.start()

    while True:
        try:
            msg = agent.receive()
        except Exception as exc:
            print(f"con_runner: receive error: {exc}", file=sys.stderr)
            break

        msg_type = msg.get("message_type")
        if msg_type in (MessageType.ROUTING, MessageType.REPRIMAND):
            try:
                agent.respond(msg)
            except Exception as exc:
                print(f"con_runner: respond error: {exc}", file=sys.stderr)
                break
        else:
            break


if __name__ == "__main__":
    main()
