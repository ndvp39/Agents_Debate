"""DebateSDK — single public entry point for all debate system operations."""

import contextlib
import json
import logging
import os
import tempfile
from collections.abc import Callable
from pathlib import Path

from debate.agents.watchdog import Watchdog
from debate.sdk.factory import Spawners, subprocess_factory
from debate.services.orchestrator import DebateOrchestrator, DebateResult
from debate.shared.config import ConfigManager
from debate.shared.cost_aggregator import aggregate_costs
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
    """Pick the watchdog timeout, with provider-aware precedence:
      1. explicit arg (caller knows best)
      2. config/setup.json -> provider.<active>.timeout_seconds (per-provider override)
      3. config/setup.json -> debate.timeout_seconds (global fallback)
      4. hardcoded default

    Per-provider override is the right shape because Sonnet turns run ~3x
    slower than Gemini Flash Lite (live observation: 80-110 s vs 25-45 s per
    debater turn), so a single global value either false-positive-kills Sonnet
    or wastes recovery latency on Gemini.
    """
    if explicit is not None:
        return float(explicit)
    try:
        data = json.loads(_CONFIG_SETUP_PATH.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError) as exc:
        _log.warning(
            "sdk: could not read setup.json (%s) — falling back to watchdog timeout %.1fs",
            exc, _DEFAULT_WATCHDOG_TIMEOUT,
        )
        return _DEFAULT_WATCHDOG_TIMEOUT

    # Per-provider override takes precedence over the global debate setting.
    try:
        from debate.shared.llm_provider import get_active_provider
        provider = get_active_provider(data)
        provider_cfg = data.get("provider", {}).get(provider, {})
        if "timeout_seconds" in provider_cfg:
            return float(provider_cfg["timeout_seconds"])
    except Exception as exc:  # noqa: BLE001
        _log.warning("sdk: provider-specific watchdog lookup failed (%s)", exc)

    try:
        return float(data["debate"]["timeout_seconds"])
    except (KeyError, TypeError, ValueError) as exc:
        _log.warning(
            "sdk: could not read debate.timeout_seconds (%s) — falling back to %.1fs",
            exc, _DEFAULT_WATCHDOG_TIMEOUT,
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
        if getattr(self._orchestrator, "_watchdog", None) is None:
            with contextlib.suppress(AttributeError):
                self._orchestrator._watchdog = self._watchdog
        # Keep the IPC backstop comfortably above the watchdog timeout so the
        # watchdog always fires first (it's the recoverable path; IPC abort is fatal).
        # Wrapped in try/except so mock orchestrators (whose `_ipc_timeout` is a
        # MagicMock attribute, not a float) don't blow up.
        try:
            current = float(self._orchestrator._ipc_timeout)
            self._orchestrator._ipc_timeout = max(current, resolved_timeout + 60.0)
        except (AttributeError, TypeError, ValueError):
            pass
        self._gatekeeper = gatekeeper
        self._result: DebateResult | None = None
        self._active_checkpoint: Path | None = None
        self._active_cost_paths: dict[str, Path] = {}

    # ------------------------------------------------------------------
    # Primary action
    # ------------------------------------------------------------------

    def start_debate(self, topic: str, rounds: int) -> DebateResult:
        """Spawn agents, run the debate loop, and store the result.

        Guarantees no orphan processes and no stale judge checkpoint / cost
        dump files outliving the debate.
        """
        procs: list = []
        spawners: Spawners | None = None
        try:
            # Allocate a per-debate judge checkpoint file. The orchestrator
            # owns spawning via the per-agent closures inside Spawners; passing
            # the same path to spawn_judge ensures a watchdog-restarted judge
            # reloads the accumulated state.
            self._active_checkpoint = self._allocate_judge_checkpoint()
            self._active_cost_paths = self._allocate_cost_paths()
            factory_result = self._call_factory(
                topic, rounds, self._active_checkpoint, self._active_cost_paths,
            )

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

            self._populate_cost_summary()
        except Exception:
            for p in procs:
                with contextlib.suppress(Exception):
                    p.kill()
                    p.wait()
            raise
        finally:
            self._cleanup_checkpoint()
            self._cleanup_cost_paths()
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
        """Return token + USD cost breakdown for the most recent debate.

        Empty dict before the first debate, or when all three agents made zero
        gated API calls (a configuration error or an entirely-failed run).
        Populated by `_populate_cost_summary` from per-agent gatekeeper dumps.
        """
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

    def _call_factory(
        self,
        topic: str,
        rounds: int,
        checkpoint: Path,
        cost_paths: dict[str, Path],
    ):
        """Call the configured factory, passing the judge checkpoint + per-agent
        cost paths when the factory accepts them (the real subprocess_factory
        does; test mocks may use a narrower signature)."""
        kwargs = {
            "judge_checkpoint_path": checkpoint,
            "pro_cost_path": cost_paths.get("pro"),
            "con_cost_path": cost_paths.get("con"),
            "judge_cost_path": cost_paths.get("judge"),
        }
        if self._process_factory is subprocess_factory:
            return self._process_factory(topic, rounds, **kwargs)
        try:
            return self._process_factory(topic, rounds, **kwargs)
        except TypeError:
            return self._process_factory(topic, rounds)

    @staticmethod
    def _allocate_judge_checkpoint() -> Path:
        fd, name = tempfile.mkstemp(prefix="judge_checkpoint_", suffix=".json")
        # Close the fd; the judge subprocess will create+write to the file.
        # Leaving it empty means JudgeAgent._load_checkpoint sees no payload
        # (treats as fresh state) until the judge writes its first turn.
        os.close(fd)
        return Path(name)

    @staticmethod
    def _allocate_cost_paths() -> dict[str, Path]:
        paths: dict[str, Path] = {}
        for role in ("pro", "con", "judge"):
            fd, name = tempfile.mkstemp(prefix=f"cost_{role}_", suffix=".json")
            os.close(fd)
            paths[role] = Path(name)
        return paths

    def _cleanup_checkpoint(self) -> None:
        path = self._active_checkpoint
        self._active_checkpoint = None
        if path is None:
            return
        with contextlib.suppress(OSError):
            path.unlink(missing_ok=True)

    def _cleanup_cost_paths(self) -> None:
        for path in self._active_cost_paths.values():
            with contextlib.suppress(OSError):
                path.unlink(missing_ok=True)
        self._active_cost_paths = {}

    def _populate_cost_summary(self) -> None:
        """Read per-agent gatekeeper cost dumps and store the aggregate on the result."""
        if self._result is None:
            return
        try:
            setup = ConfigManager(
                config_dir=str(Path(__file__).resolve().parents[3] / "config"),
            ).get_setup()
        except Exception as exc:  # noqa: BLE001
            _log.warning("sdk: could not load setup.json for cost rates (%s)", exc)
            setup = {}
        summary = aggregate_costs(
            setup,
            pro_cost_path=self._active_cost_paths.get("pro"),
            con_cost_path=self._active_cost_paths.get("con"),
            judge_cost_path=self._active_cost_paths.get("judge"),
        )
        if summary:
            self._result.cost_summary = summary
            _log.info(
                "sdk: debate cost — calls=%d tokens=%d (%d in / %d out) est_usd=$%.6f",
                summary["total_calls"],
                summary["total_tokens"],
                summary["total_input_tokens"],
                summary["total_output_tokens"],
                summary["estimated_cost_usd"],
            )

    def _require_result(self) -> None:
        if self._result is None:
            raise InsufficientDataError("No debate has been started yet.")
