"""DebateSDK — single public entry point for all debate system operations."""

import contextlib
import json
import logging
import tempfile
from collections.abc import Callable
from pathlib import Path

from debate.agents.watchdog import Watchdog
from debate.sdk.factory import Spawners, subprocess_factory
from debate.services.orchestrator import DebateOrchestrator, DebateResult
from debate.shared.exceptions import InsufficientDataError

_log = logging.getLogger("debate.sdk")


def _null_factory(topic: str, rounds: int, **kwargs):
    """Placeholder factory — replaced in production by a real subprocess spawner."""
    raise NotImplementedError("A process_factory must be provided to spawn agent processes.")


# Final fallback when neither the caller nor `config/setup.json` provides a value.
_DEFAULT_WATCHDOG_TIMEOUT = 90.0

# Project-root config file we consult for `debate.timeout_seconds`.
# `src/debate/sdk/sdk.py` → parents[3] is the project root.
_CONFIG_SETUP_PATH = Path(__file__).resolve().parents[3] / "config" / "setup.json"


def _resolve_watchdog_timeout(explicit: float | None) -> float:
    """Pick the watchdog timeout: explicit arg > config/setup.json > hardcoded default.

    Threading the value through `config/setup.json.debate.timeout_seconds` means
    operators can tune the timeout without code changes; the hardcoded fallback
    keeps the SDK importable in test environments where the config file isn't
    on disk.
    """
    if explicit is not None:
        return float(explicit)
    try:
        data = json.loads(_CONFIG_SETUP_PATH.read_text(encoding="utf-8"))
        return float(data["debate"]["timeout_seconds"])
    except (FileNotFoundError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        _log.warning(
            "sdk: could not read watchdog timeout from %s (%s) — falling back to %.1fs",
            _CONFIG_SETUP_PATH, exc, _DEFAULT_WATCHDOG_TIMEOUT,
        )
        return _DEFAULT_WATCHDOG_TIMEOUT


class DebateSDK:
    """Single entry point for starting debates and querying results.

    Dependencies are injected for testability:
        orchestrator    — DebateOrchestrator (or mock)
        process_factory — callable(topic, rounds, **kwargs) -> Spawners (or tuple
                          for the legacy mock path used by unit tests)
        watchdog        — Watchdog instance; constructed by default when None.
        watchdog_timeout — Per-turn timeout in seconds for the default watchdog.
        gatekeeper      — ApiGatekeeper instance (optional; used for queue queries)
    """

    def __init__(
        self,
        orchestrator: DebateOrchestrator | None = None,
        process_factory: Callable | None = None,
        watchdog: Watchdog | None = None,
        watchdog_timeout: float | None = None,
        gatekeeper=None,
    ) -> None:
        self._orchestrator = orchestrator or DebateOrchestrator()
        self._process_factory = process_factory or _null_factory
        resolved_timeout = _resolve_watchdog_timeout(watchdog_timeout)
        self._watchdog = watchdog if watchdog is not None else Watchdog(resolved_timeout)
        # Inject the watchdog into the orchestrator unless one was already
        # wired in (e.g. a test passing its own mock orchestrator).
        if self._orchestrator._watchdog is None:
            self._orchestrator._watchdog = self._watchdog
        self._gatekeeper = gatekeeper
        self._result: DebateResult | None = None
        self._active_checkpoint: Path | None = None

    # ------------------------------------------------------------------
    # Primary action
    # ------------------------------------------------------------------

    def start_debate(self, topic: str, rounds: int) -> DebateResult:
        """Spawn agents, run the debate loop, and store the result.

        Guarantees no orphan processes and no stale judge checkpoint files
        outliving the debate.
        """
        procs: list = []
        spawners: Spawners | None = None
        try:
            # Allocate a per-debate judge checkpoint file. The orchestrator
            # owns spawning via the per-agent closures inside Spawners; passing
            # the same path to spawn_judge ensures a watchdog-restarted judge
            # reloads the accumulated state.
            self._active_checkpoint = self._allocate_judge_checkpoint()
            factory_result = self._call_factory(topic, rounds, self._active_checkpoint)

            if isinstance(factory_result, Spawners):
                spawners = factory_result
                self._result = self._orchestrator.run(topic, rounds, spawners=spawners)
            else:
                # Legacy/test path: factory returned a (pro, con, judge) tuple.
                pro_proc, con_proc, judge_proc = factory_result
                procs = [pro_proc, con_proc, judge_proc]
                self._result = self._orchestrator.run(
                    topic, rounds,
                    pro_proc=pro_proc, con_proc=con_proc, judge_proc=judge_proc,
                )
        except Exception:
            for p in procs:
                with contextlib.suppress(Exception):
                    p.kill()
                    p.wait()
            raise
        finally:
            self._cleanup_checkpoint()
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

    def _call_factory(self, topic: str, rounds: int, checkpoint: Path):
        """Call the configured factory, passing the judge checkpoint kwarg when
        the factory accepts it (the real subprocess_factory does; test mocks may not)."""
        if self._process_factory is subprocess_factory:
            return self._process_factory(topic, rounds, judge_checkpoint_path=checkpoint)
        try:
            return self._process_factory(topic, rounds, judge_checkpoint_path=checkpoint)
        except TypeError:
            return self._process_factory(topic, rounds)

    @staticmethod
    def _allocate_judge_checkpoint() -> Path:
        fd, name = tempfile.mkstemp(prefix="judge_checkpoint_", suffix=".json")
        # Close the fd; the judge subprocess will create+write to the file.
        # Leaving it empty means JudgeAgent._load_checkpoint sees no payload
        # (treats as fresh state) until the judge writes its first turn.
        import os
        os.close(fd)
        return Path(name)

    def _cleanup_checkpoint(self) -> None:
        path = self._active_checkpoint
        self._active_checkpoint = None
        if path is None:
            return
        with contextlib.suppress(OSError):
            path.unlink(missing_ok=True)

    def _require_result(self) -> None:
        if self._result is None:
            raise InsufficientDataError("No debate has been started yet.")
