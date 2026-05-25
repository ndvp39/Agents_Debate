"""DebateSDK — single public entry point for all debate system operations."""

import contextlib
from collections.abc import Callable

from debate.services.orchestrator import DebateOrchestrator, DebateResult
from debate.shared.exceptions import InsufficientDataError


def _null_factory(topic: str, rounds: int):
    """Placeholder factory — replaced in production by a real subprocess spawner."""
    raise NotImplementedError("A process_factory must be provided to spawn agent processes.")


class DebateSDK:
    """Single entry point for starting debates and querying results.

    All business logic flows through this class. The CLI delegates here and
    does no computation of its own.

    Dependencies are injected for testability:
        orchestrator    — DebateOrchestrator (or mock)
        process_factory — callable(topic, rounds) -> (pro_proc, con_proc, judge_proc)
        gatekeeper      — ApiGatekeeper instance (optional; used for queue/cost queries)
    """

    def __init__(
        self,
        orchestrator: DebateOrchestrator | None = None,
        process_factory: Callable | None = None,
        gatekeeper=None,
    ) -> None:
        self._orchestrator = orchestrator or DebateOrchestrator()
        self._process_factory = process_factory or _null_factory
        self._gatekeeper = gatekeeper
        self._result: DebateResult | None = None

    # ------------------------------------------------------------------
    # Primary action
    # ------------------------------------------------------------------

    def start_debate(self, topic: str, rounds: int) -> DebateResult:
        """Spawn agents, run the debate loop, and store the result.

        Guarantees no orphan processes: the orchestrator's try/finally handles the
        normal path; this outer guard covers the gap between factory completion and
        the orchestrator's own try block, and handles partial factory failures.
        """
        procs: list = []
        try:
            pro_proc, con_proc, judge_proc = self._process_factory(topic, rounds)
            procs = [pro_proc, con_proc, judge_proc]
            self._result = self._orchestrator.run(topic, rounds, pro_proc, con_proc, judge_proc)
        except Exception:
            for p in procs:
                with contextlib.suppress(Exception):
                    p.kill()
                    p.wait()
            raise
        return self._result

    # ------------------------------------------------------------------
    # Result accessors
    # ------------------------------------------------------------------

    def get_transcript(self) -> list[dict]:
        """Return the full ordered message transcript from the last debate."""
        self._require_result()
        return self._result.transcript

    def get_verdict(self) -> dict:
        """Return the final verdict dict from the last debate."""
        self._require_result()
        return self._result.verdict

    def get_cost_summary(self) -> dict:
        """Return token cost breakdown (empty dict before first debate)."""
        if self._result is None:
            return {}
        return self._result.cost_summary

    def get_queue_status(self) -> dict:
        """Return the current gatekeeper queue status."""
        if self._gatekeeper is None:
            return {}
        return self._gatekeeper.get_queue_status()

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _require_result(self) -> None:
        if self._result is None:
            raise InsufficientDataError("No debate has been started yet.")
