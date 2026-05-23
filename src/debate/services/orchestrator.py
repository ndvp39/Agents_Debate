"""DebateOrchestrator — mediates all message routing between the three agent processes."""

import subprocess
from dataclasses import dataclass, field
from typing import Optional

from debate.agents.watchdog import Watchdog
from debate.ipc.channel import IPCChannel
from debate.shared.constants import AgentID, MessageType


@dataclass
class DebateResult:
    """Full output of a completed debate session."""

    topic: str
    rounds_completed: int
    transcript: list[dict]
    verdict: dict
    cost_summary: dict
    reprimand_count: int


class DebateOrchestrator:
    """Implements the Mediator pattern — agents never talk to each other directly.

    Flow per round:
      current_speaker → Judge → routing/reprimand → next_speaker (or retry)
    After all rounds: verdict_request → Judge → DebateResult.
    """

    def __init__(
        self,
        channel: Optional[IPCChannel] = None,
        watchdog: Optional[Watchdog] = None,
    ) -> None:
        self._channel = channel or IPCChannel()
        self._watchdog = watchdog

    def run(
        self,
        topic: str,
        rounds: int,
        pro_proc: subprocess.Popen,
        con_proc: subprocess.Popen,
        judge_proc: subprocess.Popen,
    ) -> DebateResult:
        """Execute the full debate loop and return a DebateResult."""
        transcript: list[dict] = []
        reprimand_count = 0
        rounds_completed = 0
        verdict: dict = {}

        self._register_watchdog(pro_proc, con_proc, judge_proc)

        initial = {
            "message_type": MessageType.ROUTING,
            "target_agent": AgentID.PRO,
            "judge_feedback": "",
            "prompt_for_next": f"You are arguing completely FOR: {topic}. Open the debate.",
        }

        current_proc = pro_proc
        next_proc = con_proc

        try:
            self._channel.send(current_proc, initial)

            while rounds_completed < rounds:
                argument = self._channel.receive(current_proc)
                transcript.append(argument)

                self._channel.send(judge_proc, argument)
                judge_resp = self._channel.receive(judge_proc)

                if judge_resp.get("message_type") == MessageType.REPRIMAND:
                    reprimand_count += 1
                    self._channel.send(current_proc, judge_resp)
                else:
                    rounds_completed += 1
                    transcript.append(judge_resp)
                    current_proc, next_proc = next_proc, current_proc
                    self._channel.send(current_proc, judge_resp)

            self._channel.send(judge_proc, {"message_type": "verdict_request"})
            verdict = self._channel.receive(judge_proc)
            transcript.append(verdict)

        finally:
            self._shutdown(pro_proc, con_proc, judge_proc)

        return DebateResult(
            topic=topic,
            rounds_completed=rounds_completed,
            transcript=transcript,
            verdict=verdict,
            cost_summary={},
            reprimand_count=reprimand_count,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _register_watchdog(self, pro_proc, con_proc, judge_proc) -> None:
        if self._watchdog is None:
            return
        self._watchdog.register(pro_proc, AgentID.PRO, lambda: pro_proc)
        self._watchdog.register(con_proc, AgentID.CON, lambda: con_proc)
        self._watchdog.register(judge_proc, AgentID.JUDGE, lambda: judge_proc)

    def _shutdown(self, *procs) -> None:
        for proc in procs:
            try:
                proc.terminate()
            except Exception:
                pass
        if self._watchdog:
            self._watchdog.stop()
