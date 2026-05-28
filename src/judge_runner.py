"""Subprocess entry point for the Judge agent."""

import argparse
import sys
from pathlib import Path

from dotenv import load_dotenv

_PROJECT_ROOT = Path(__file__).parent.parent
load_dotenv(_PROJECT_ROOT / ".env")

from debate.agents.judge.judge_agent import JudgeAgent  # noqa: E402
from debate.ipc.schemas import ArgumentMessage  # noqa: E402
from debate.shared.config import ConfigManager  # noqa: E402
from debate.shared.constants import MessageType  # noqa: E402
from debate.shared.gatekeeper import ApiGatekeeper  # noqa: E402
from debate.shared.llm_provider import (  # noqa: E402
    make_judge_evaluate_llm,
    make_judge_route_llm,
    make_judge_verdict_llm,
)
from debate.skills.loader import SkillLoader  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--checkpoint",
        type=Path,
        default=None,
        help="Path to a persistent state file. Loaded on startup so a "
             "watchdog-restarted judge resumes with full score history.",
    )
    parser.add_argument(
        "--cost-output",
        type=Path,
        default=None,
        help="Path to write the judge LLM gatekeeper's cost summary after every call.",
    )
    args = parser.parse_args()

    config = ConfigManager(config_dir=str(_PROJECT_ROOT / "config"))
    setup = config.get_setup()

    # Single LLM gatekeeper shared by evaluate, route, and verdict roles —
    # all three call the same Anthropic/Gemini judge model, so a single
    # rate-limit window and a single cost accumulator is the right shape.
    llm_gk = ApiGatekeeper(config, service="llm", cost_dump_path=args.cost_output)

    skills = SkillLoader(Path(__file__).resolve().parent / "debate" / "skills")

    agent = JudgeAgent(
        evaluate_llm=make_judge_evaluate_llm(setup, gatekeeper=llm_gk),
        route_llm=make_judge_route_llm(setup, gatekeeper=llm_gk),
        verdict_llm=make_judge_verdict_llm(setup, gatekeeper=llm_gk),
        skills=skills,
        checkpoint_path=args.checkpoint,
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
