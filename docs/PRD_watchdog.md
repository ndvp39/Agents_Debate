# PRD — Watchdog
**Version:** 1.00  
**Date:** 2026-05-23  
**File:** `src/debate/agents/watchdog.py`

---

## 1. Description & Theoretical Background

The Watchdog is a keep-alive and fault-recovery component that monitors every agent process. If an agent hangs — fails to produce output within the configured timeout — the Watchdog kills the process and automatically restarts it. This ensures the debate continues without manual intervention.

The design is based on the **Watchdog Timer** pattern common in embedded and distributed systems. In this context, each agent process is expected to send output within a configurable window. If it misses this window, the Watchdog assumes it has hung and takes corrective action.

The Watchdog runs in the main orchestrator process as a background monitor. It does not run as a separate OS process.

---

## 2. Responsibilities

- Accept registration of agent processes (`register(process, name, restart_fn)`).
- Start a per-process countdown timer when the orchestrator begins waiting for a response.
- Reset the timer when a valid response is received from the process.
- If the timer expires: kill the process, call the registered `restart_fn`, and notify the orchestrator.
- Log every timeout, kill, and restart event.

---

## 3. Interface

```python
class Watchdog:
    """Monitors agent processes and restarts them on timeout."""

    def __init__(self, timeout_seconds: float):
        """Load timeout from config; initialize internal state."""

    def register(self, process: subprocess.Popen, name: str, restart_fn: Callable) -> None:
        """Register an agent process for monitoring."""

    def start_timer(self, name: str) -> None:
        """Begin countdown for the named agent. Called before waiting for a response."""

    def reset_timer(self, name: str) -> None:
        """Reset the countdown. Called when a valid response is received."""

    def stop(self) -> None:
        """Stop all timers and clean up. Called at debate end."""
```

---

## 4. Timeout & Restart Flow

```
Orchestrator calls start_timer("pro")
        │
        ▼
[countdown begins — timeout_seconds from config]
        │
   ┌────┴────┐
   │         │
timeout    response received
fires      before timeout
   │         │
   ▼         ▼
[kill process]   [reset_timer("pro")]
[call restart_fn]
[log: WATCHDOG | agent=pro | event=restart]
[notify orchestrator: re-send last message]
```

---

## 5. Timer Implementation

- Each registered process has an independent `threading.Timer`.
- `start_timer()` creates and starts the timer.
- `reset_timer()` cancels the current timer (if active) — no action needed.
- On timeout callback: cancel timer, kill process via `process.kill()`, call `restart_fn()`.
- Timer timeout value is loaded from `config/setup.json` (`debate.timeout_seconds`).

---

## 6. Restart Function Contract

The `restart_fn` passed during `register()` must:
- Spawn a new process for the same agent role.
- Return the new `subprocess.Popen` object.
- Re-register the new process with the Watchdog automatically.

The Watchdog calls `restart_fn()` and updates its internal process reference.

---

## 7. Performance Requirements

| Metric | Target |
|--------|--------|
| Timer resolution | ≤ 1 second accuracy |
| Time from timeout detection to process kill | < 2 seconds |
| Time from kill to restart completion | < 10 seconds |
| Memory overhead (Watchdog itself) | < 10MB |

---

## 8. Constraints

- Timeout value MUST be loaded from `config/setup.json` — never hardcoded.
- The Watchdog MUST monitor all three agent processes independently.
- On restart, the Watchdog MUST log the event before notifying the orchestrator.
- `stop()` MUST cancel all active timers to avoid firing after debate ends.
- Thread safety: timer callbacks run in a separate thread; shared state MUST be protected with a `threading.Lock`.

---

## 9. Alternatives Considered

| Alternative | Reason Rejected |
|-------------|----------------|
| Polling loop (check every N seconds) | Slower response time; wastes CPU |
| `signal.alarm` (Unix only) | Not portable to Windows |
| asyncio timeout | Requires the entire orchestrator to be async; scope too large |
| No Watchdog at all | Violates requirement: "system must trigger timeout, kill, and restart automatically" |

---

## 10. Success Criteria

- [x] If an agent process does not respond within `timeout_seconds`, it is killed automatically.
- [x] A new process is spawned for the same agent role after a kill.
- [x] The debate resumes after a restart (orchestrator re-sends the last message).
- [x] `stop()` prevents timers from firing after the debate ends.
- [x] All timeout, kill, and restart events are logged.
- [x] Three independent timers run concurrently without interfering with each other.

---

## 11. Test Scenarios

| Scenario | Expected Outcome |
|----------|-----------------|
| Agent responds within timeout | Timer reset; no kill event |
| Agent hangs for longer than timeout | Process killed; restart_fn called; log entry written |
| `stop()` called while timer is active | Timer cancelled; no kill event fires |
| Two agents hang simultaneously | Both killed and restarted independently |
| Restart function fails | `WatchdogRestartError` raised; logged |
| `reset_timer()` called for unregistered agent | `KeyError` raised |
