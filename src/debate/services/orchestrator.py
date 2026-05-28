"""DebateOrchestrator — mediates all message routing between the three agent processes.

Watchdog-driven self-repair: every blocking `receive()` is wrapped by a turn-level
timer. When an agent hangs, the watchdog kills its subprocess, spawns a fresh one
via the per-agent closure, and the orchestrator transparently re-sends the
in-flight message to the new process so the debate continues.

Debater state is fully reconstructable from the next routing message (which
carries `previous_argument` and `round_number`). Judge state is checkpointed to
a small JSON file after every scoring turn; a restarted judge reloads it and
resumes with full score history.
"""

import contextlib
import logging
import subprocess
from dataclasses import dataclass

from debate.agents.watchdog import Watchdog
from debate.ipc.channel import IPCChannel
from debate.sdk.factory import Spawners
from debate.shared.constants import AgentID, MessageType
from debate.shared.exceptions import IPCParseError, IPCTimeoutError

_log = logging.getLogger("debate.orchestrator")

# Window the orchestrator waits for the watchdog's restart_fn to complete after
# a receive failure. Should comfortably exceed subprocess.Popen startup time
# even on a cold cache.
_RESTART_WAIT_SECONDS = 15.0

# Maximum consecutive restart attempts per turn before giving up.
_MAX_RESTARTS_PER_TURN = 2


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
        channel: IPCChannel | None = None,
        watchdog: Watchdog | None = None,
        ipc_timeout: float = 150.0,
    ) -> None:
        self._channel = channel or IPCChannel()
        self._watchdog = watchdog
        self._ipc_timeout = ipc_timeout
        # Active process handles, keyed by AgentID. Refreshed after each restart
        # via the per-agent spawn closures registered with the watchdog.
        self._procs: dict[str, subprocess.Popen] = {}

    def run(
        self,
        topic: str,
        rounds: int,
        pro_proc: subprocess.Popen | None = None,
        con_proc: subprocess.Popen | None = None,
        judge_proc: subprocess.Popen | None = None,
        *,
        spawners: Spawners | None = None,
    ) -> DebateResult:
        """Execute the full debate loop and return a DebateResult.

        Either `spawners` (production path with watchdog-driven self-repair)
        OR explicit `pro_proc/con_proc/judge_proc` (test path with mocks) must
        be provided.
        """
        if spawners is None and (pro_proc is None or con_proc is None or judge_proc is None):
            raise ValueError(
                "DebateOrchestrator.run requires either `spawners` or all of "
                "pro_proc, con_proc, judge_proc."
            )

        if spawners is not None:
            self._procs = {
                AgentID.PRO: spawners.spawn_pro(),
                AgentID.CON: spawners.spawn_con(),
                AgentID.JUDGE: spawners.spawn_judge(),
            }
        else:
            self._procs = {
                AgentID.PRO: pro_proc,
                AgentID.CON: con_proc,
                AgentID.JUDGE: judge_proc,
            }

        transcript: list[dict] = []
        reprimand_count = 0
        turns_completed = 0      # individual debater turns (Pro or Con)
        rounds_completed = 0     # complete exchanges (Pro + Con = 1 round)
        verdict: dict = {}

        initial = {
            "message_type": MessageType.ROUTING,
            "target_agent": AgentID.PRO,
            "judge_feedback": "",
            "prompt_for_next": f"You are arguing completely FOR: {topic}. Open the debate.",
            "previous_argument": "",
            "round_number": 1,
        }

        current_agent = AgentID.PRO
        next_agent = AgentID.CON
        last_message_sent: dict[str, dict] = {}

        try:
            self._register_watchdog(spawners)
            self._send(current_agent, initial)
            last_message_sent[current_agent] = initial

            while rounds_completed < rounds:
                argument = self._receive(current_agent, resend_message=last_message_sent.get(current_agent))
                transcript.append(argument)

                self._send(AgentID.JUDGE, argument)
                last_message_sent[AgentID.JUDGE] = argument
                judge_resp = self._receive(AgentID.JUDGE, resend_message=argument)

                if judge_resp.get("message_type") == MessageType.REPRIMAND:
                    reprimand_count += 1
                    self._send(current_agent, judge_resp)
                    last_message_sent[current_agent] = judge_resp
                else:
                    turns_completed += 1
                    transcript.append(judge_resp)
                    current_agent, next_agent = next_agent, current_agent
                    self._send(current_agent, judge_resp)
                    last_message_sent[current_agent] = judge_resp
                    # A complete round = one Pro turn + one Con turn (even turns_completed)
                    if turns_completed % 2 == 0:
                        rounds_completed += 1

            verdict_req = {"message_type": "verdict_request"}
            self._send(AgentID.JUDGE, verdict_req)
            last_message_sent[AgentID.JUDGE] = verdict_req
            verdict = self._receive(AgentID.JUDGE, resend_message=verdict_req)
            transcript.append(verdict)

        finally:
            self._shutdown()

        return DebateResult(
            topic=topic,
            rounds_completed=rounds_completed,
            transcript=transcript,
            verdict=verdict,
            cost_summary={},
            reprimand_count=reprimand_count,
        )

    # ------------------------------------------------------------------
    # Watchdog-aware send/receive
    # ------------------------------------------------------------------

    def _send(self, agent_id: str, message: dict) -> None:
        self._channel.send(self._procs[agent_id], message)

    def _receive(self, agent_id: str, resend_message: dict | None) -> dict:
        """Receive a message from `agent_id`, transparently surviving subprocess restarts.

        Arm the watchdog before reading; on a successful read, disarm it.
        If `_channel.receive` fails (EOF from a killed process, or backstop
        timeout) AND the watchdog has just restarted the agent, re-send the
        in-flight message to the new process and retry.
        """
        restarts = 0
        while True:
            if self._watchdog is not None:
                self._watchdog.start_timer(agent_id)
            try:
                msg = self._channel.receive(self._procs[agent_id], timeout=self._ipc_timeout)
                if self._watchdog is not None:
                    self._watchdog.reset_timer(agent_id)
                return msg
            except (IPCParseError, IPCTimeoutError) as exc:
                if self._watchdog is None:
                    raise
                _log.warning(
                    "orchestrator: receive failed agent=%s err=%s — awaiting watchdog restart",
                    agent_id, exc,
                )
                restarted = self._watchdog.wait_for_restart(
                    agent_id, timeout=_RESTART_WAIT_SECONDS,
                )
                if not restarted or self._watchdog.last_error is not None:
                    _log.error(
                        "orchestrator: no restart within %.1fs — aborting (last_error=%s)",
                        _RESTART_WAIT_SECONDS, self._watchdog.last_error,
                    )
                    raise
                restarts += 1
                if restarts > _MAX_RESTARTS_PER_TURN:
                    _log.error(
                        "orchestrator: exceeded %d restarts on a single turn — aborting",
                        _MAX_RESTARTS_PER_TURN,
                    )
                    raise
                # Pick up the fresh Popen handle and re-send the in-flight message.
                self._procs[agent_id] = self._watchdog.current_process(agent_id)
                if resend_message is not None:
                    _log.warning(
                        "orchestrator: re-sending in-flight message agent=%s attempt=%d",
                        agent_id, restarts,
                    )
                    self._channel.send(self._procs[agent_id], resend_message)
                # loop: arm a fresh timer and retry receive

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _register_watchdog(self, spawners: Spawners | None) -> None:
        """Register each agent with the watchdog using its per-agent spawn closure.

        The restart_fn closure both spawns the fresh process and updates the
        orchestrator's `_procs` map so subsequent `_send` / `_receive` calls
        target the new handle automatically.
        """
        if self._watchdog is None:
            return
        if spawners is not None:
            def make_restart(agent_id: str, spawn_fn):
                def _restart():
                    new_proc = spawn_fn()
                    self._procs[agent_id] = new_proc
                    return new_proc
                return _restart

            self._watchdog.register(
                self._procs[AgentID.PRO], AgentID.PRO,
                make_restart(AgentID.PRO, spawners.spawn_pro),
            )
            self._watchdog.register(
                self._procs[AgentID.CON], AgentID.CON,
                make_restart(AgentID.CON, spawners.spawn_con),
            )
            self._watchdog.register(
                self._procs[AgentID.JUDGE], AgentID.JUDGE,
                make_restart(AgentID.JUDGE, spawners.spawn_judge),
            )
        else:
            # Test path with explicit procs: register no-op restart_fn (the
            # tests don't exercise restart). Watchdog still arms/resets timers
            # so the wiring is exercised.
            for agent_id, proc in self._procs.items():
                self._watchdog.register(proc, agent_id, lambda p=proc: p)

    def _shutdown(self) -> None:
        """Terminate all agent subprocesses and release OS resources.

        Three-phase cleanup (all failures suppressed so every process is attempted):
          1. Close stdin — unblocks any subprocess waiting on a pipe read.
          2. terminate() — sends SIGTERM (Unix) / TerminateProcess (Windows).
          3. wait(3 s) — reaps the process; falls back to kill() + wait() if it lingers.
        """
        procs = list(self._procs.values())
        for proc in procs:
            with contextlib.suppress(Exception):
                if proc.stdin and not proc.stdin.closed:
                    proc.stdin.close()
        for proc in procs:
            with contextlib.suppress(Exception):
                proc.terminate()
        for proc in procs:
            with contextlib.suppress(Exception):
                try:
                    proc.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait()
        if self._watchdog:
            self._watchdog.stop()
