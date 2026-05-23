# PRD — IPC Protocol
**Version:** 1.00  
**Date:** 2026-05-23  
**Author:** Nadav Goldin  
**Files:** `src/debate/ipc/schemas.py`, `src/debate/ipc/channel.py`

---

## 1. Description & Theoretical Background

Inter-Process Communication (IPC) is the mechanism by which the three agent processes exchange structured data. The system uses **JSON over stdin/stdout pipes** (via Python `subprocess`).

JSON was chosen because:
- It is human-readable for debugging and logging.
- It is natively parseable by Python without extra dependencies.
- It is token-efficient (no XML overhead).
- It allows the orchestrator to inspect and validate every message before routing.

Each message has a `message_type` field that the orchestrator uses to dispatch the correct handler. There are exactly **3 message types**: `routing`, `reprimand`, and `verdict`.

---

## 2. Message Schemas

### 2.1 Routing Message (Judge → Orchestrator → next Debater)
Sent after the Judge accepts an argument and wants to pass the turn.

```json
{
  "message_type": "routing",
  "target_agent": "Agent_B",
  "judge_feedback": "Strong point about economic displacement.",
  "prompt_for_next": "Agent_B, directly counter the claim about job loss with evidence."
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `message_type` | `str` | Yes | Always `"routing"` |
| `target_agent` | `str` | Yes | `"Agent_Pro"` or `"Agent_Con"` |
| `judge_feedback` | `str` | Yes | Judge's summary of the previous argument |
| `prompt_for_next` | `str` | Yes | Instruction for the next speaker |

---

### 2.2 Reprimand Message (Judge → Orchestrator → same Debater)
Sent when the debater failed to counter-argue, agreed with the opponent, or lacked citations.

```json
{
  "message_type": "reprimand",
  "target_agent": "Agent_A",
  "reprimand_issued": true,
  "prompt_for_next": "Rewrite and provide a counter-argument with citations."
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `message_type` | `str` | Yes | Always `"reprimand"` |
| `target_agent` | `str` | Yes | Same agent that just spoke |
| `reprimand_issued` | `bool` | Yes | Always `true` |
| `prompt_for_next` | `str` | Yes | Instruction to rewrite the argument |

---

### 2.3 Verdict Message (Judge → Orchestrator → DebateResult)
Sent at the final round after `Declare_Verdict` is executed.

```json
{
  "message_type": "verdict",
  "winner": "Agent_Con",
  "scores": {
    "Agent_Pro": 72,
    "Agent_Con": 85
  },
  "justification": "Agent_Con consistently provided peer-reviewed citations and directly rebutted every claim. Agent_Pro relied on anecdotal evidence in 6 of 10 rounds."
}
```

| Field | Type | Required | Constraints |
|-------|------|----------|-------------|
| `message_type` | `str` | Yes | Always `"verdict"` |
| `winner` | `str` | Yes | `"Agent_Pro"` or `"Agent_Con"` — ties forbidden |
| `scores` | `dict` | Yes | Both keys present; values are integers 0–100; must differ |
| `justification` | `str` | Yes | Min 50 characters |

---

### 2.4 Debater Argument Message (Debater → Orchestrator → Judge)
The debater's response to the Judge's prompt.

```json
{
  "message_type": "argument",
  "agent_id": "Agent_Pro",
  "round": 3,
  "argument": "...",
  "citations": ["Source 1: ...", "Source 2: ..."]
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `message_type` | `str` | Yes | Always `"argument"` |
| `agent_id` | `str` | Yes | `"Agent_Pro"` or `"Agent_Con"` |
| `round` | `int` | Yes | Current round number (1-based) |
| `argument` | `str` | Yes | The debater's full argument |
| `citations` | `list[str]` | Yes | At least 1 citation required |

---

## 3. IPCChannel Component

### 3.1 Responsibilities
- Serialize outgoing Python dicts to JSON strings and write to the target process's stdin.
- Read from the source process's stdout and deserialize to Python dicts.
- Validate that every received message matches one of the known schemas.
- Raise a typed exception (`IPCParseError`) on malformed JSON.
- Raise a typed exception (`IPCSchemaError`) on valid JSON that fails schema validation.

### 3.2 Interface

```python
class IPCChannel:
    def send(self, process: subprocess.Popen, message: dict) -> None:
        """Serialize message to JSON and write to process stdin."""

    def receive(self, process: subprocess.Popen, timeout: float = 120.0) -> dict:
        """Read one JSON line from process stdout; raise on timeout or parse error."""

    def validate(self, message: dict) -> None:
        """Raise IPCSchemaError if message does not match any known schema."""
```

---

## 4. Transport Rules

- Every message is a **single JSON line** terminated by `\n`.
- Agent processes MUST write ONLY valid JSON to stdout. All debug output MUST go to stderr.
- The orchestrator reads one line at a time from the agent's stdout.
- If `receive()` times out (configurable via `config/setup.json`), it raises `IPCTimeoutError`, which the Watchdog handler catches.

---

## 5. Constraints

- All four message types (`routing`, `reprimand`, `verdict`, `argument`) MUST be validated on receipt.
- Ties in the verdict scores are rejected at the schema validation layer (`IPCSchemaError`).
- `citations` in an `argument` message must be non-empty; the Judge's `Enforce_Debate_Mechanics` skill also checks this, but schema validation is the first line of defense.
- No binary data; all content is UTF-8 encoded text.

---

## 6. Alternatives Considered

| Alternative | Reason Rejected |
|-------------|----------------|
| Named pipes (FIFO files) | More complex setup; platform-specific on Windows |
| TCP sockets | Overkill for same-machine communication; adds port management |
| Python `multiprocessing.Queue` | Requires shared Python runtime; incompatible with subprocess isolation |
| XML | More verbose; higher token cost; slower parsing |

---

## 7. Success Criteria

- [x] All 4 message types serialize and deserialize without data loss.
- [x] Malformed JSON raises `IPCParseError` without crashing the orchestrator.
- [x] A verdict with equal scores raises `IPCSchemaError`.
- [x] A `receive()` call that exceeds timeout raises `IPCTimeoutError`.
- [x] Schema validation rejects an `argument` message with an empty `citations` list.

---

## 8. Test Scenarios

| Scenario | Expected Outcome |
|----------|-----------------|
| Send routing message, receive on other end | Dict matches original |
| Send malformed JSON string | `IPCParseError` raised |
| Send verdict with equal scores (75 vs 75) | `IPCSchemaError` raised |
| `receive()` with 0.1s timeout on silent process | `IPCTimeoutError` raised |
| Argument message with empty citations list | `IPCSchemaError` raised |
| Round-trip all 4 message types | All validate without error |
