# PRD — Debate Orchestrator
**Version:** 1.01  
**Date:** 2026-05-25  
**Author:** Nadav Goldin  
**File:** `src/debate/services/orchestrator.py`

---

## 1. Description & Theoretical Background

The Debate Orchestrator is the central coordination engine of the system. It is responsible for spawning the three agent processes (Judge, Pro, Con), managing the turn-based debate loop, routing messages between agents via the IPC channel, tracking round counts, handling reprimands, and collecting the final verdict.

The orchestrator implements the **Mediator design pattern**: agents never communicate directly with each other; all communication flows through the orchestrator, which forwards messages to the appropriate process. This enforces the required communication topology: `Pro → Judge → Con → Judge → Pro → ...`

The orchestrator also serves as the integration point for the Watchdog — it registers each spawned process with the Watchdog, arms `start_timer` around every blocking `receive()`, calls `reset_timer` on success, and reacts to restart notifications. See §6 for the two restart paths.

---

## 2. Responsibilities

- Spawn and manage the lifecycle of all three agent processes.
- Register each process with the Watchdog for timeout monitoring.
- Execute the debate loop for the configured number of rounds (10 by default, 5 if budget-constrained).
- Route messages: receive output from the current speaker, pass it to the Judge, receive the Judge's routing/reprimand decision, forward to the next speaker.
- Track reprimand events (does not advance the round counter on a reprimand).
- Collect and return the `DebateResult` upon completion.
- Gracefully shut down all processes after the debate ends or on error.

---

## 3. Input / Output

### Input (via DebateSDK)
| Parameter | Type | Description |
|-----------|------|-------------|
| `topic` | `str` | The debate topic (e.g., "AI will replace human jobs") |
| `rounds` | `int` | Number of ping-pong rounds (10 or 5) |

### Output
| Field | Type | Description |
|-------|------|-------------|
| `DebateResult` | dataclass | Full result: transcript, verdict, cost summary, reprimand count |

### Internal State
| Field | Type | Description |
|-------|------|-------------|
| `current_round` | `int` | Rounds completed so far |
| `current_speaker` | `str` | "pro" or "con" |
| `reprimand_count` | `int` | Total reprimands issued |
| `transcript` | `list[dict]` | All messages in order |

---

## 4. Debate Loop Algorithm

```
1. Spawn Pro process, Con process, Judge process
2. Register all three with Watchdog
3. Send opening prompt to Pro agent (topic + stance + round count)
4. LOOP until rounds_completed == configured_rounds:
   a. Receive argument from current_speaker
   b. Forward to Judge
   c. Receive Judge response (routing OR reprimand)
   d. If reprimand:
      - Log reprimand
      - Increment reprimand_count
      - Re-send to same speaker (do NOT advance round)
      - Go to step 4a
   e. If routing:
      - Append to transcript
      - Increment round counter
      - Switch current_speaker
      - Forward Judge's prompt_for_next to next speaker
      - Go to step 4a
5. Send "final round" signal to Judge
6. Receive verdict JSON
7. Shut down all processes
8. Return DebateResult
```

---

## 5. Performance Requirements

| Metric | Target |
|--------|--------|
| Total debate completion time | < 30 minutes for 10 rounds |
| Message routing latency (orchestrator overhead) | < 100ms per hop |
| Memory footprint (orchestrator process) | < 100MB |
| Graceful shutdown time after debate ends | < 5 seconds |

---

## 6. Constraints

- The orchestrator MUST NOT contain any LLM call logic — it only routes messages.
- Round counter MUST NOT advance on a reprimand.
- All subprocess handles MUST be registered with the Watchdog before the loop starts.
- On Watchdog-triggered restart, the orchestrator MUST re-send the last message to the restarted agent.
- The orchestrator MUST shut down all processes even if an exception is raised (use `try/finally`).
- Shutdown MUST use three-phase cleanup: (1) close each process's stdin to unblock pipe reads, (2) send SIGTERM via `terminate()`, (3) wait up to 3 seconds; if the process lingers, escalate to `kill()` + `wait()`. All failures are suppressed so every process is attempted.
- The SDK `start_debate()` MUST guard against orphan processes between factory completion and orchestrator entry — if an exception occurs before the orchestrator's own try block, the SDK kills all spawned processes.

---

## 6.1 Spawners (per-agent spawn closures)

The orchestrator does **not** spawn processes itself. The SDK constructs a
`Spawners` dataclass via `subprocess_factory(topic, rounds, judge_checkpoint_path=,
pro_cost_path=, con_cost_path=, judge_cost_path=)` containing three callables:
`spawn_pro()`, `spawn_con()`, `spawn_judge()`. Each closure spawns one
subprocess with the right argv (including `--checkpoint` for the judge and
`--cost-output` per agent) and returns the new `Popen`. The orchestrator
invokes each closure once for the initial spawn, stores the handles in
`self._procs: dict[AgentID, Popen]`, and wraps each closure with a small
`make_restart()` factory that also updates `self._procs[agent_id]` on respawn.
The same closures are registered with the watchdog as `restart_fn`.

## 6.2 Two restart paths

The orchestrator's `_receive(agent_id, resend_message)` survives both common
failure modes a subprocess can exhibit:

1. **Watchdog kill+restart (timer expiry).** Subprocess hangs longer than
   `timeout_seconds`. The watchdog kills it via `process.kill()` and invokes
   `restart_fn` (which respawns and updates `self._procs`). On the orchestrator
   side, the killed stdin/stdout closes → `receive()` raises `IPCParseError`
   ("Empty response from process"). The orchestrator calls
   `watchdog.wait_for_restart(agent_id, timeout=_RESTART_WAIT_SECONDS)`; on
   `True`, picks up the new handle via `watchdog.current_process(agent_id)`,
   re-sends the in-flight message via `_channel.send`, and loops.

2. **Runner clean exit (subprocess.exit on error).** The watchdog timer never
   fires (runner exits on its own, e.g., `_retry` raised after exhausting Gemini
   429 retries). `wait_for_restart` returns `False`. The orchestrator probes
   `self._procs[agent_id].poll()`; if non-`None`, calls
   `self._restart_fns[agent_id]()` to spawn a fresh process, calls
   `watchdog.notify_external_restart(agent_id, new_proc)` so a future timer
   fire targets the new handle, re-sends, and loops.

Both paths share a per-turn `_MAX_RESTARTS_PER_TURN = 2` budget. On budget
exhaustion `_receive` raises a `RuntimeError` naming the agent and surfacing
the exit code — no silent 15 s wait. Debater state is fully reconstructable
from the next routing message's `previous_argument` + `round_number`; the
judge persists its accumulated `_scores` / `_last_arguments` /
`_last_feedback_sent` / `_round` to an atomic JSON checkpoint after every
scoring turn so a restarted judge resumes with full history (see
`PRD_judge_agent.md §3.0`).

## 6.3 IPC backstop timeout

`DebateOrchestrator.__init__` accepts `ipc_timeout: float = 150.0` — the
`IPCChannel.receive(timeout=)` value that fires as a backstop in case the
watchdog itself fails. The SDK auto-derives this as
`max(default, watchdog_timeout + 60.0)` so the watchdog always fires first
(`PRD_watchdog.md §7.1`).

## 7. Alternatives Considered

| Alternative | Reason Rejected |
|-------------|----------------|
| asyncio event loop instead of subprocess | Cannot kill/restart a runaway coroutine without cooperation; Watchdog requires OS-level process control |
| Direct agent-to-agent pipes | Violates the required `Pro → Judge → Con` routing; Judge cannot intercept |
| Single process with threads | Thread isolation insufficient; hung thread cannot be killed cleanly |

---

## 8. Success Criteria

- [x] Running `sdk.start_debate(topic, rounds=10)` completes all 10 rounds and returns a `DebateResult`.
- [x] A reprimand from the Judge does not increment the round counter.
- [x] A simulated agent hang (sleep > timeout) triggers Watchdog restart; debate resumes.
- [x] All three processes are terminated after `DebateResult` is returned.
- [x] The full transcript in `DebateResult` contains every message in correct order.

---

## 9. Test Scenarios

| Scenario | Expected Outcome |
|----------|-----------------|
| Normal 10-round debate (mocked LLM) | `DebateResult` with 10 rounds, verdict present |
| Judge issues reprimand on round 3 | Round 3 replayed; total rounds still 10 |
| Pro agent hangs on round 5 | Watchdog kills and restarts Pro; debate continues from round 5 |
| LLM API rate limit hit | Gatekeeper queues the call; debate continues after drain |
| Invalid JSON from agent | IPCChannel raises error; orchestrator logs and retries |
