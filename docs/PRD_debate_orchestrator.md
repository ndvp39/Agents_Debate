# PRD — Debate Orchestrator
**Version:** 1.00  
**Date:** 2026-05-23  
**File:** `src/debate/services/orchestrator.py`

---

## 1. Description & Theoretical Background

The Debate Orchestrator is the central coordination engine of the system. It is responsible for spawning the three agent processes (Judge, Pro, Con), managing the turn-based debate loop, routing messages between agents via the IPC channel, tracking round counts, handling reprimands, and collecting the final verdict.

The orchestrator implements the **Mediator design pattern**: agents never communicate directly with each other; all communication flows through the orchestrator, which forwards messages to the appropriate process. This enforces the required communication topology: `Pro → Judge → Con → Judge → Pro → ...`

The orchestrator also serves as the integration point for the Watchdog — it registers each spawned process with the Watchdog and reacts to restart notifications.

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

---

## 7. Alternatives Considered

| Alternative | Reason Rejected |
|-------------|----------------|
| asyncio event loop instead of subprocess | Cannot kill/restart a runaway coroutine without cooperation; Watchdog requires OS-level process control |
| Direct agent-to-agent pipes | Violates the required `Pro → Judge → Con` routing; Judge cannot intercept |
| Single process with threads | Thread isolation insufficient; hung thread cannot be killed cleanly |

---

## 8. Success Criteria

- [ ] Running `sdk.start_debate(topic, rounds=10)` completes all 10 rounds and returns a `DebateResult`.
- [ ] A reprimand from the Judge does not increment the round counter.
- [ ] A simulated agent hang (sleep > timeout) triggers Watchdog restart; debate resumes.
- [ ] All three processes are terminated after `DebateResult` is returned.
- [ ] The full transcript in `DebateResult` contains every message in correct order.

---

## 9. Test Scenarios

| Scenario | Expected Outcome |
|----------|-----------------|
| Normal 10-round debate (mocked LLM) | `DebateResult` with 10 rounds, verdict present |
| Judge issues reprimand on round 3 | Round 3 replayed; total rounds still 10 |
| Pro agent hangs on round 5 | Watchdog kills and restarts Pro; debate continues from round 5 |
| LLM API rate limit hit | Gatekeeper queues the call; debate continues after drain |
| Invalid JSON from agent | IPCChannel raises error; orchestrator logs and retries |
