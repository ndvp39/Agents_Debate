"""Subprocess entry point for the Con debater agent."""

import argparse
import logging
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

_PROJECT_ROOT = Path(__file__).parent.parent
load_dotenv(_PROJECT_ROOT / ".env")

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)-7s %(name)s | %(message)s",
    datefmt="%H:%M:%S",
    stream=sys.stderr,
)

from debate.agents.debaters.con_agent import ConAgent  # noqa: E402
from debate.shared.config import ConfigManager  # noqa: E402
from debate.shared.constants import AgentID, MessageType  # noqa: E402
from debate.shared.gatekeeper import ApiGatekeeper  # noqa: E402
from debate.shared.llm_provider import make_debater_llm  # noqa: E402
from debate.shared.web_search import make_tavily_search  # noqa: E402
from debate.skills.loader import SkillLoader  # noqa: E402


def _make_search_call(gatekeeper, label):
    api_key = os.getenv("TAVILY_API_KEY", "").strip()
    if api_key:
        return make_tavily_search(api_key, gatekeeper=gatekeeper, label=label)
    print(
        "con_runner: TAVILY_API_KEY not set — web search disabled; "
        "arguments will run without retrieved sources.",
        file=sys.stderr,
    )
    return lambda q: []


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--topic", required=True)
    parser.add_argument(
        "--cost-output",
        type=Path,
        default=None,
        help="Path to write the LLM gatekeeper's cost summary after every call.",
    )
    args = parser.parse_args()

    config = ConfigManager(config_dir=str(_PROJECT_ROOT / "config"))
    setup = config.get_setup()

    llm_gk = ApiGatekeeper(config, service="llm", cost_dump_path=args.cost_output)
    search_gk = ApiGatekeeper(config, service="web_search")

    skills = SkillLoader(Path(__file__).resolve().parent / "debate" / "skills")

    agent = ConAgent(
        topic=args.topic,
        llm_call=make_debater_llm(setup, gatekeeper=llm_gk, label=f"{AgentID.CON}.debater"),
        search_call=_make_search_call(search_gk, label=f"{AgentID.CON}.tavily"),
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
