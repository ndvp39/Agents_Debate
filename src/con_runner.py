"""Subprocess entry point for the Con debater agent."""

import argparse
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

_PROJECT_ROOT = Path(__file__).parent.parent
load_dotenv(_PROJECT_ROOT / ".env")

from debate.agents.debaters.con_agent import ConAgent  # noqa: E402
from debate.shared.config import ConfigManager  # noqa: E402
from debate.shared.constants import MessageType  # noqa: E402
from debate.shared.llm_provider import make_debater_llm  # noqa: E402
from debate.shared.web_search import make_tavily_search  # noqa: E402
from debate.skills.loader import SkillLoader  # noqa: E402


def _make_search_call():
    api_key = os.getenv("TAVILY_API_KEY", "").strip()
    if api_key:
        return make_tavily_search(api_key)
    print(
        "con_runner: TAVILY_API_KEY not set — web search disabled; "
        "arguments will run without retrieved sources.",
        file=sys.stderr,
    )
    return lambda q: []


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--topic", required=True)
    args = parser.parse_args()

    setup = ConfigManager(config_dir=str(_PROJECT_ROOT / "config")).get_setup()
    skills = SkillLoader(Path(__file__).resolve().parent / "debate" / "skills")

    agent = ConAgent(
        topic=args.topic,
        llm_call=make_debater_llm(setup),
        search_call=_make_search_call(),
        skills=skills,
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
