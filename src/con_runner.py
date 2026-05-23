"""Subprocess entry point for the Con debater agent."""

import argparse
import sys
from pathlib import Path

from dotenv import load_dotenv

_PROJECT_ROOT = Path(__file__).parent.parent
load_dotenv(_PROJECT_ROOT / ".env")

from debate.agents.debaters.con_agent import ConAgent  # noqa: E402
from debate.shared.config import ConfigManager  # noqa: E402
from debate.shared.constants import MessageType  # noqa: E402
from debate.shared.llm_provider import make_debater_llm  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--topic", required=True)
    args = parser.parse_args()

    setup = ConfigManager(config_dir=str(_PROJECT_ROOT / "config")).get_setup()

    agent = ConAgent(
        topic=args.topic,
        llm_call=make_debater_llm(setup),
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
