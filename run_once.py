"""Non-interactive runner — executes one full debate, writes live progress, saves results."""

import json
import sys
from datetime import datetime
from pathlib import Path

from generate_html import generate_html

sys.path.insert(0, str(Path(__file__).parent / "src"))

from debate.ipc.channel import IPCChannel
from debate.sdk.factory import subprocess_factory
from debate.sdk.sdk import DebateSDK
from debate.services.orchestrator import DebateOrchestrator

TOPIC = "Will artificial intelligence replace human jobs"
ROUNDS = 10
OUTDIR = Path(__file__).parent / "results"
OUTDIR.mkdir(exist_ok=True)

PROGRESS_FILE = OUTDIR / "debate_progress.log"


def _log(msg: str) -> None:
    """Append a timestamped line to the live progress file and stdout."""
    line = f"[{datetime.now().strftime('%H:%M:%S')}] {msg}"
    print(line, flush=True)
    with open(PROGRESS_FILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")


class _TrackedChannel(IPCChannel):
    """IPCChannel subclass that writes a progress line after every received message."""

    def receive(self, proc) -> dict:
        msg = super().receive(proc)
        mt = msg.get("message_type", "?")
        if mt == "argument":
            agent = msg.get("agent_id", "?")
            rnd = msg.get("round", "?")
            preview = msg.get("argument", "")[:80].replace("\n", " ")
            _log(f"Round {rnd:>2} | {agent:<12} argues: {preview}…")
        elif mt == "routing":
            target = msg.get("target_agent", "?")
            fb = msg.get("judge_feedback", "")[:60].replace("\n", " ")
            _log(f"         | Judge  -> {target:<12} feedback: {fb}…")
        elif mt == "reprimand":
            target = msg.get("target_agent", "?")
            _log(f"         | Judge REPRIMAND -> {target}")
        elif mt == "verdict":
            winner = msg.get("winner", "?")
            scores = msg.get("scores", {})
            _log(f"VERDICT  | Winner: {winner}  Scores: {scores}")
        return msg


class _TrackedOrchestrator(DebateOrchestrator):
    def __init__(self):
        super().__init__(channel=_TrackedChannel())


def _format_transcript(transcript: list[dict]) -> str:
    lines = ["=" * 70, "  TRANSCRIPT", "=" * 70]
    for msg in transcript:
        mt = msg.get("message_type", "unknown")
        if mt == "argument":
            agent = msg.get("agent_id", "?")
            rnd = msg.get("round", "?")
            argument = msg.get("argument", "")
            citations = msg.get("citations", [])
            lines.append(f"\n[Round {rnd}] {agent} argues:")
            lines.append(f"  {argument}")
            if citations:
                lines.append("  Citations:")
                for c in citations:
                    lines.append(f"    - {c}")
        elif mt == "routing":
            target = msg.get("target_agent", "?")
            feedback = msg.get("judge_feedback", "")
            prompt = msg.get("prompt_for_next", "")
            lines.append(f"\n[Judge -> {target}]")
            if feedback:
                lines.append(f"  Feedback : {feedback}")
            lines.append(f"  Prompt   : {prompt}")
        elif mt == "reprimand":
            target = msg.get("target_agent", "?")
            prompt = msg.get("prompt_for_next", "")
            lines.append(f"\n[Judge REPRIMAND -> {target}]")
            lines.append(f"  {prompt}")
        elif mt == "verdict":
            winner = msg.get("winner", "?")
            scores = msg.get("scores", {})
            justification = msg.get("justification", "")
            lines.append(f"\n[VERDICT]  Winner: {winner}")
            lines.append(f"  Scores: {scores}")
            lines.append(f"  Justification:\n  {justification}")
    return "\n".join(lines)


def main() -> None:
    # Clear progress file
    PROGRESS_FILE.write_text("", encoding="utf-8")

    stamp = datetime.now().strftime("%Y-%m-%d_%H%M")
    out_txt = OUTDIR / f"debate_{stamp}.txt"
    out_json = OUTDIR / f"debate_{stamp}.json"

    _log(f"Topic  : {TOPIC}")
    _log(f"Rounds : {ROUNDS}")
    _log("Starting debate… (live progress below)")
    _log("-" * 60)

    sdk = DebateSDK(
        orchestrator=_TrackedOrchestrator(),
        process_factory=subprocess_factory,
    )
    sdk.start_debate(TOPIC, ROUNDS)

    transcript = sdk.get_transcript()
    verdict = sdk.get_verdict()
    cost = sdk.get_cost_summary()

    _log("-" * 60)
    _log(f"Debate complete. Saving to {out_txt.name}")

    header = [
        "=" * 70,
        "  AI Agent Debate System",
        f"  Topic  : {TOPIC}",
        f"  Rounds : {ROUNDS}",
        f"  Date   : {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "=" * 70,
    ]
    footer = [
        "\n" + "=" * 70,
        "  DEBATE COMPLETE",
        "=" * 70,
        f"  Winner : {verdict.get('winner', '?')}",
        f"  Scores : {verdict.get('scores', {})}",
        f"\n  Justification:\n  {verdict.get('justification', '')}",
    ]
    if cost:
        footer += [
            f"\n  Tokens : {cost.get('total_tokens', 'N/A')}",
            f"  Cost   : ~${cost.get('estimated_cost_usd', 'N/A')}",
        ]
    footer.append("=" * 70)

    full_text = "\n".join(header) + "\n" + _format_transcript(transcript) + "\n" + "\n".join(footer)
    out_txt.write_text(full_text, encoding="utf-8")
    out_json.write_text(
        json.dumps(
            {"topic": TOPIC, "rounds": ROUNDS, "transcript": transcript, "verdict": verdict, "cost": cost},
            indent=2, ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    date_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    out_html = OUTDIR / f"debate_{stamp}.html"
    out_html.write_text(
        generate_html(transcript, verdict, TOPIC, date_str),
        encoding="utf-8",
    )

    print(full_text)
    _log(f"Saved: {out_txt}")
    _log(f"Saved: {out_json}")
    _log(f"Saved: {out_html}")


if __name__ == "__main__":
    main()
