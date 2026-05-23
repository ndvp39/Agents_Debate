"""CLI entry point — delegates entirely to DebateSDK. No business logic here."""

from debate.sdk.factory import subprocess_factory
from debate.sdk.sdk import DebateSDK
from debate.shared.constants import AgentID
from debate.shared.version import VERSION


def _banner() -> None:
    print("=" * 60)
    print(f"  AI Agent Debate System  v{VERSION}")
    print("=" * 60)


def _get_topic() -> str:
    topic = input("\nEnter debate topic: ").strip()
    if not topic:
        raise ValueError("Topic cannot be empty.")
    return topic


def _get_rounds() -> int:
    raw = input("Enter number of rounds [default 10]: ").strip()
    if not raw:
        return 10
    rounds = int(raw)
    if rounds < 1:
        raise ValueError("Rounds must be at least 1.")
    return rounds


def _display_result(sdk: DebateSDK) -> None:
    verdict = sdk.get_verdict()
    winner = verdict.get("winner", "Unknown")
    scores = verdict.get("scores", {})
    justification = verdict.get("justification", "")

    print("\n" + "=" * 60)
    print("  DEBATE COMPLETE")
    print("=" * 60)
    print(f"  Winner : {winner}")
    print(f"  Scores : {AgentID.PRO} = {scores.get(AgentID.PRO, '?')}  |  "
          f"{AgentID.CON} = {scores.get(AgentID.CON, '?')}")
    print(f"\n  Justification:\n  {justification}")

    cost = sdk.get_cost_summary()
    if cost:
        tokens = cost.get("total_tokens", "N/A")
        usd = cost.get("estimated_cost_usd", "N/A")
        print(f"\n  Cost   : {tokens} tokens  (~${usd})")

    transcript = sdk.get_transcript()
    print(f"\n  Messages in transcript : {len(transcript)}")
    print("=" * 60)


def main() -> None:
    """Launch the terminal menu for the debate system."""
    _banner()

    try:
        topic = _get_topic()
        rounds = _get_rounds()
    except (ValueError, KeyboardInterrupt) as exc:
        print(f"\nInput error: {exc}")
        return

    print(f"\nStarting debate — topic: '{topic}' | rounds: {rounds}")
    print("Please wait while agents are initialised...\n")

    sdk = DebateSDK(process_factory=subprocess_factory)

    try:
        sdk.start_debate(topic, rounds)
        _display_result(sdk)
    except KeyboardInterrupt:
        print("\nDebate interrupted by user.")
    except Exception as exc:
        print(f"\nUnexpected error: {exc}")


if __name__ == "__main__":
    main()
