"""Watchdog — per-process threading.Timer that kills and restarts hung agents.

Public API
----------
* `register(process, name, restart_fn)` — track an agent.
* `start_timer(name)` / `reset_timer(name)` — arm/disarm the per-turn timer.
* `wait_for_restart(name, timeout) -> bool` — block until the watchdog's timeout
  fires AND `restart_fn()` completes. Returns True on restart, False on timeout
  waiting for it. The orchestrator uses this to safely re-send the in-flight
  message after detecting a hung process.
* `stop()` — cancel all timers (debate end).
* `last_error` — populated when `restart_fn` raised, so callers can surface it.
"""

import logging
import subprocess
import threading
from collections.abc import Callable
from dataclasses import dataclass, field

from debate.shared.exceptions import WatchdogRestartError

_log = logging.getLogger("debate.watchdog")


@dataclass
class _AgentEntry:
    process: subprocess.Popen
    restart_fn: Callable
    timer: threading.Timer | None = field(default=None, repr=False)
    # Signaled after a restart completes — orchestrator waits on this to know
    # when the new Popen handle is safe to send the re-tried message to.
    restart_event: threading.Event = field(default_factory=threading.Event, repr=False)


class Watchdog:
    """Monitors agent processes and auto-restarts them on timeout.

    Each registered agent gets an independent threading.Timer.
    start_timer() begins the countdown; reset_timer() cancels it.
    When a timer fires the process is killed, restart_fn() is called,
    and the internal process reference is updated.
    """

    def __init__(self, timeout_seconds: float) -> None:
        self._timeout = timeout_seconds
        self._agents: dict[str, _AgentEntry] = {}
        self._lock = threading.Lock()
        self.last_error: WatchdogRestartError | None = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def register(self, process: subprocess.Popen, name: str, restart_fn: Callable) -> None:
        """Register an agent process for monitoring."""
        with self._lock:
            self._agents[name] = _AgentEntry(process=process, restart_fn=restart_fn)

    def start_timer(self, name: str) -> None:
        """Begin countdown for the named agent."""
        with self._lock:
            entry = self._agents[name]
            # Each new turn starts with a fresh restart_event — a previous
            # restart's `set()` must not leak into this turn.
            entry.restart_event.clear()
            if entry.timer is not None:
                entry.timer.cancel()
            timer = threading.Timer(self._timeout, self._on_timeout, args=(name,))
            timer.daemon = True
            entry.timer = timer
        _log.info("watchdog: timer armed agent=%s timeout=%.1fs", name, self._timeout)
        timer.start()

    def reset_timer(self, name: str) -> None:
        """Cancel the countdown — valid response received."""
        with self._lock:
            entry = self._agents[name]
            if entry.timer is not None:
                entry.timer.cancel()
                entry.timer = None
        _log.debug("watchdog: timer reset agent=%s", name)

    def stop(self) -> None:
        """Cancel all active timers — call at debate end."""
        with self._lock:
            for entry in self._agents.values():
                if entry.timer is not None:
                    entry.timer.cancel()
                    entry.timer = None
        _log.info("watchdog: stopped")

    def current_process(self, name: str) -> subprocess.Popen:
        """Return the currently-tracked Popen handle (refreshed after restart)."""
        with self._lock:
            return self._agents[name].process

    def notify_external_restart(self, name: str, new_process: subprocess.Popen) -> None:
        """Update the tracked process for an externally-restarted agent.

        Use this when something other than the watchdog (e.g. the orchestrator
        detecting an unexpected subprocess exit) respawned an agent. Without
        this call, the watchdog's next `kill()` would target the stale handle.
        """
        with self._lock:
            entry = self._agents.get(name)
            if entry is not None:
                entry.process = new_process

    def wait_for_restart(self, name: str, timeout: float) -> bool:
        """Block until a restart for `name` completes; True on success, False on timeout."""
        with self._lock:
            event = self._agents[name].restart_event
        return event.wait(timeout=timeout)

    # ------------------------------------------------------------------
    # Internal timeout callback
    # ------------------------------------------------------------------

    def _on_timeout(self, name: str) -> None:
        with self._lock:
            entry = self._agents.get(name)
            if entry is None:
                return
            old_pid = getattr(entry.process, "pid", None)
            try:
                entry.process.kill()
            except Exception as exc:  # noqa: BLE001
                _log.warning("watchdog: kill raised agent=%s err=%s", name, exc)
            entry.timer = None
            restart_fn = entry.restart_fn
        _log.warning(
            "watchdog: timeout fired agent=%s killed_pid=%s — attempting restart", name, old_pid,
        )

        try:
            new_process = restart_fn()
        except Exception as exc:  # noqa: BLE001
            with self._lock:
                self.last_error = WatchdogRestartError(
                    f"Restart failed for {name!r}: {exc}"
                )
                # Signal anyway so waiters unblock and surface the error.
                self._agents[name].restart_event.set()
            _log.error("watchdog: restart FAILED agent=%s err=%s", name, exc)
            return

        new_pid = getattr(new_process, "pid", None)
        with self._lock:
            if name in self._agents:
                self._agents[name].process = new_process
                self._agents[name].restart_event.set()
        _log.warning(
            "watchdog: restart OK agent=%s new_pid=%s (was %s)", name, new_pid, old_pid,
        )
