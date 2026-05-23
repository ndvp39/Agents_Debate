"""Watchdog — per-process threading.Timer that kills and restarts hung agents."""

import subprocess
import threading
from dataclasses import dataclass, field
from typing import Callable

from debate.shared.exceptions import WatchdogRestartError


@dataclass
class _AgentEntry:
    process: subprocess.Popen
    restart_fn: Callable
    timer: threading.Timer | None = field(default=None, repr=False)


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
            if entry.timer is not None:
                entry.timer.cancel()
            timer = threading.Timer(self._timeout, self._on_timeout, args=(name,))
            timer.daemon = True
            entry.timer = timer
        timer.start()

    def reset_timer(self, name: str) -> None:
        """Cancel the countdown — valid response received."""
        with self._lock:
            entry = self._agents[name]
            if entry.timer is not None:
                entry.timer.cancel()
                entry.timer = None

    def stop(self) -> None:
        """Cancel all active timers — call at debate end."""
        with self._lock:
            for entry in self._agents.values():
                if entry.timer is not None:
                    entry.timer.cancel()
                    entry.timer = None

    # ------------------------------------------------------------------
    # Internal timeout callback
    # ------------------------------------------------------------------

    def _on_timeout(self, name: str) -> None:
        with self._lock:
            entry = self._agents.get(name)
            if entry is None:
                return
            entry.process.kill()
            entry.timer = None
            restart_fn = entry.restart_fn

        try:
            new_process = restart_fn()
        except Exception as exc:
            with self._lock:
                self.last_error = WatchdogRestartError(
                    f"Restart failed for {name!r}: {exc}"
                )
            return

        with self._lock:
            if name in self._agents:
                self._agents[name].process = new_process
