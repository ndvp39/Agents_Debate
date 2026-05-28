"""DebateOrchestrator — mediates all message routing between the three agent processes.

Watchdog-driven self-repair: every blocking `receive()` is wrapped by a turn-level
timer. When an agent hangs, the watchdog kills its subprocess, spawns a fresh one
via the per-agent closure, and the orchestrator transparently re-sends the
in-flight message to the new process so the debate continues.

A second recovery path handles agent runners that EXIT CLEANLY on a fatal error
(e.g. provider quota exhausted): the watchdog never fires (no hang), but stdout
closes and `receive()` returns EOF. The orchestrator detects this via
`process.poll()` and triggers ONE manual respawn through the same spawn closure,
bounded by the per-turn restart budget. If the respawn fails the same way the
abort is prompt and surfaces the failed agent's identity + exit code.

Debater state is fully reconstructable from the next routing message (which
carries `previous_argument` and `round_number`). Judge state is checkpointed to
a small JSON file after every scoring turn; a restarted judge reloads it and
resumes with full score history.
"""

import contextlib
import logging
import subprocess
from collections.abc import Callable
from dataclasses import dataclass

from debate.agents.watchdog import Watchdog
from debate.ipc.channel import IPCChannel
from debate.sdk.factory import Spawners
from debate.shared.constants import AgentID, MessageType
from debate.shared.exceptions import IPCParseError, IPCTimeoutError

_log = logging.getLogger("debate.orchestrator")

# Window the orchestrator waits for the watchdog's restart_fn to complete after
# a receive failure. The watchdog's spawn closure is synchronous (subprocess.Popen
# returns in <1s); 3s is plenty and keeps a runner-exited-on-error abort prompt.
_RESTART_WAIT_SECONDS = 3.0

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
        # Per-agent spawn closures (mirror of the watchdog's restart_fns), kept
        # here so the orchestrator can trigger a respawn for the runner-exit
        # recovery path without going through the watchdog timer flow.
        self._restart_fns: dict[str, Callable[[], subprocess.Popen]] = {}

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

        Recovery covers two failure modes:
        1. Watchdog kill — the watchdog timer fired, killed the process, and its
           restart_fn spawned a fresh one. We pick up the new handle and re-send.
        2. Runner clean exit — the subprocess exited on its own (e.g. its
           gatekeeper raised after exhausting retries). The watchdog never
           fired; we detect via `process.poll()`, trigger one respawn through
           our own restart_fn map, and re-send.
        Both paths share the `_MAX_RESTARTS_PER_TURN` budget so a persistently-
        broken agent surfaces a prompt clear abort rather than infinite recovery.
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

                # Path 1: did the watchdog kill+restart the process?
                restarted = self._watchdog.wait_for_restart(
                    agent_id, timeout=_RESTART_WAIT_SECONDS,
                )
                if restarted and self._watchdog.last_error is None:
                    restarts += 1
                    if restarts > _MAX_RESTARTS_PER_TURN:
                        _log.error(
                            "orchestrator: exceeded %d restarts on a single turn — aborting",
                            _MAX_RESTARTS_PER_TURN,
                        )
                        raise
                    self._procs[agent_id] = self._watchdog.current_process(agent_id)
                    _log.warning(
                        "orchestrator: re-sending in-flight message agent=%s attempt=%d",
                        agent_id, restarts,
                    )
                    if resend_message is not None:
                        self._channel.send(self._procs[agent_id], resend_message)
                    continue

                # Path 2: runner exited cleanly on error. The watchdog never fired,
                # so `wait_for_restart` returned False. Detect via process.poll().
                proc = self._procs[agent_id]
                exit_code = proc.poll()
                if exit_code is not None and agent_id in self._restart_fns:
                    restarts += 1
                    if restarts > _MAX_RESTARTS_PER_TURN:
                        raise RuntimeError(
                            f"{agent_id} subprocess exited unexpectedly "
                            f"(exit_code={exit_code}) and respawn budget exhausted. "
                            f"Check the runner's stderr log for the underlying error."
                        ) from exc
                    _log.warning(
                        "orchestrator: %s subprocess exited (code=%s) — manual respawn (attempt=%d)",
                        agent_id, exit_code, restarts,
                    )
                    new_proc = self._restart_fns[agent_id]()
                    # Sync the watchdog's tracked handle so a future timer fire
                    # targets the new process, not the stale (zombie) one.
                    self._watchdog.notify_external_restart(agent_id, new_proc)
                    if resend_message is not None:
                        self._channel.send(self._procs[agent_id], resend_message)
                    continue

                # Neither path applies — surface the original error.
                if self._watchdog.last_error is not None:
                    _log.error(
                        "orchestrator: watchdog restart failed agent=%s err=%s",
                        agent_id, self._watchdog.last_error,
                    )
                else:
                    _log.error(
                        "orchestrator: receive failed agent=%s with no recovery path — aborting (%s)",
                        agent_id, exc,
                    )
                raise

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _register_watchdog(self, spawners: Spawners | None) -> None:
        """Register each agent with the watchdog using its per-agent spawn closure.

        The restart_fn closures both spawn the fresh process and update the
        orchestrator's `_procs` map. They are also stored in `self._restart_fns`
        so the runner-exit recovery path can trigger them without going through
        the watchdog timer flow.
        """
        self._restart_fns = {}
        if self._watchdog is None:
            return
        if spawners is not None:
            def make_restart(agent_id: str, spawn_fn):
                def _restart():
                    new_proc = spawn_fn()
                    self._procs[agent_id] = new_proc
                    return new_proc
                return _restart

            for agent_id, spawn_fn in (
                (AgentID.PRO, spawners.spawn_pro),
                (AgentID.CON, spawners.spawn_con),
                (AgentID.JUDGE, spawners.spawn_judge),
            ):
                fn = make_restart(agent_id, spawn_fn)
                self._restart_fns[agent_id] = fn
                self._watchdog.register(self._procs[agent_id], agent_id, fn)
        else:
            # Test path with explicit procs: no spawners → no respawn capability.
            # Register no-op restart_fns so the watchdog can still arm/reset timers
            # (the receive loop won't try to respawn because `agent_id not in self._restart_fns`).
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
