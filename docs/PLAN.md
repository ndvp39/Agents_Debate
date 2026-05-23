# PLAN — Architecture & Design Document
# AI Agent Debate Orchestration System
**Version:** 1.00  
**Date:** 2026-05-23

---

## 1. C4 Model

### 1.1 Level 1 — System Context

```
┌─────────────────────────────────────────────────────────────────┐
│                        System Context                           │
│                                                                 │
│   ┌──────────┐        ┌──────────────────────────┐             │
│   │          │ runs   │                          │             │
│   │   User   │───────▶│  AI Debate Orchestrator  │             │
│   │          │  CLI   │       (this system)      │             │
│   └──────────┘        └────────────┬─────────────┘             │
│                                    │                            │
│                   ┌────────────────┼──────────────┐            │
│                   │                │              │            │
│                   ▼                ▼              ▼            │
│          ┌──────────────┐  ┌──────────────┐  ┌────────────┐   │
│          │  LLM API     │  │  Web Search  │  │ File System│   │
│          │ (Anthropic / │  │  API         │  │ (logs,     │   │
│          │  OpenAI)     │  │ (debaters    │  │  results,  │   │
│          │              │  │  only)       │  │  config)   │   │
│          └──────────────┘  └──────────────┘  └────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

### 1.2 Level 2 — Container Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        AI Debate Orchestrator                           │
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │  User Process                                                   │   │
│  │                                                                 │   │
│  │  ┌──────────────┐    delegates     ┌───────────────────────┐   │   │
│  │  │  CLI / Menu  │────────────────▶ │       SDK             │   │   │
│  │  │  (main.py)   │                  │  (single entry point) │   │   │
│  │  └──────────────┘                  └──────────┬────────────┘   │   │
│  │                                               │                │   │
│  │                                               ▼                │   │
│  │                                  ┌────────────────────────┐   │   │
│  │                                  │      Orchestrator      │   │   │
│  │                                  │  (debate loop manager) │   │   │
│  │                                  └──────────┬─────────────┘   │   │
│  └─────────────────────────────────────────────┼─────────────────┘   │
│                                                 │ spawns & manages     │
│              ┌──────────────────────────────────┼──────────────────┐  │
│              │                                  │                  │  │
│              ▼                                  ▼                  ▼  │
│  ┌───────────────────┐          ┌───────────────────┐  ┌────────────┐│
│  │   Judge Process   │  IPC     │   Pro Process     │  │Con Process ││
│  │                   │◀────────▶│                   │  │            ││
│  │  - No internet    │  JSON    │  - Web search     │  │- Web search││
│  │  - 4 skills       │          │  - Anti-sycoph.   │  │- Anti-syco.││
│  └─────────┬─────────┘          └───────────────────┘  └────────────┘│
│            │                                                           │
│            ▼                                                           │
│  ┌───────────────────┐   ┌───────────────┐   ┌──────────────────────┐│
│  │   API Gatekeeper  │   │   Watchdog    │   │  Structured Logger   ││
│  │  (rate limits,    │   │ (timeout,kill │   │  (FIFO queue,        ││
│  │   FIFO queue,     │   │  & restart)   │   │   ≤20 files,         ││
│  │   token tracking) │   └───────────────┘   │   ≤500 lines/file)   ││
│  └───────────────────┘                        └──────────────────────┘│
└─────────────────────────────────────────────────────────────────────────┘
```

### 1.3 Level 3 — Component Diagram (src package)

```
src/debate/
│
├── sdk/
│   └── sdk.py                  ← DebateSDK (single public entry point)
│
├── services/
│   └── orchestrator.py         ← DebateOrchestrator (debate loop, round mgmt)
│
├── agents/
│   ├── base_agent.py           ← BaseAgent (process lifecycle, IPC, skill registry)
│   ├── watchdog.py             ← Watchdog (timeout, kill, restart)
│   ├── judge/
│   │   ├── judge_agent.py      ← JudgeAgent(BaseAgent) (no internet, scoring)
│   │   └── skills.py           ← EnforceDebateMechanics, RouteT urn,
│   │                                EvaluatePersuasionScore, DeclareVerdict
│   └── debaters/
│       ├── base_debater.py     ← BaseDebater(BaseAgent) (anti-sycophancy, skill pipeline)
│       ├── pro_agent.py        ← ProAgent(BaseDebater)
│       ├── con_agent.py        ← ConAgent(BaseDebater)
│       ├── web_search_tool.py  ← WebSearchTool (goes through Gatekeeper)
│       └── skills.py           ← CraftOpening, AnalyzeOpponent, DetectFallacies,
│                                    AdaptStrategy, BuildCounterArgument,
│                                    SynthesizeEvidence, ApplyRhetoric
│
├── ipc/
│   ├── schemas.py              ← RoutingMessage, ReprimandMessage, VerdictMessage
│   └── channel.py              ← IPCChannel (send/receive JSON over pipes)
│
└── shared/
    ├── config.py               ← ConfigManager (loads + validates versioned JSON)
    ├── gatekeeper.py           ← ApiGatekeeper (rate limits, queue, retry, logging)
    ├── logger.py               ← DebateLogger (FIFO rotation, structured output)
    ├── version.py              ← VERSION = "1.00"
    └── constants.py            ← Immutable project constants
```

### 1.4 Level 4 — Key Class Relationships (UML)

```
BaseAgent
  ├── JudgeAgent
  │     └── uses: EnforceDebateMechanics, RouteTurn,
  │                EvaluatePersuasionScore, DeclareVerdict
  └── BaseDebater
        ├── ProAgent
        └── ConAgent
              └── uses: WebSearchTool

DebateSDK
  └── uses: DebateOrchestrator
              ├── manages: JudgeAgent, ProAgent, ConAgent
              ├── uses: IPCChannel
              └── uses: Watchdog

ApiGatekeeper  (used by ALL agents for external calls)
ConfigManager  (used by all components)
DebateLogger   (used by all components)
```

---

## 2. UML Sequence Diagram — One Debate Round

```
User      CLI       SDK       Orchestrator   Pro      Judge    Con
 │         │         │             │          │          │       │
 │─start──▶│         │             │          │          │       │
 │         │─start──▶│             │          │          │       │
 │         │         │─start_debate▶           │          │       │
 │         │         │             │─spawn────▶│          │       │
 │         │         │             │─spawn──────────────▶│       │
 │         │         │             │─spawn────────────────────────▶│
 │         │         │             │          │          │       │
 │         │         │             │◀─arg─────│          │       │
 │         │         │             │─────────────────────▶│       │
 │         │         │             │          │  enforce  │       │
 │         │         │             │          │  +route   │       │
 │         │         │             │◀────────────────────│       │
 │         │         │             │────────────────────────────▶│
 │         │         │             │          │          │  arg  │
 │         │         │             │◀────────────────────────────│
 │         │         │             │─────────────────────▶│       │
 │         │         │             │          │  enforce  │       │
 │         │         │             │          │  +route   │       │
 │         │         │  [repeat N rounds]      │          │       │
 │         │         │             │          │ declare   │       │
 │         │         │             │◀──verdict───────────│       │
 │         │◀verdict─│◀────────────│          │          │       │
 │◀verdict─│         │             │          │          │       │
```

---

## 3. Deployment Diagram

```
┌──────────────────────── Host Machine ────────────────────────────┐
│                                                                   │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │                    Python Runtime (uv)                      │ │
│  │                                                             │ │
│  │  Process 1: main.py (CLI + SDK + Orchestrator)              │ │
│  │  Process 2: judge_agent.py  (Judge)                         │ │
│  │  Process 3: pro_agent.py    (Pro Debater)                   │ │
│  │  Process 4: con_agent.py    (Con Debater)                   │ │
│  │                                                             │ │
│  │  IPC: JSON over stdin/stdout pipes (subprocess)             │ │
│  └─────────────────────────────────────────────────────────────┘ │
│                                                                   │
│  config/   — setup.json, rate_limits.json, logging_config.json   │
│  .env       — API keys (git-ignored)                             │
│  logs/      — rotating FIFO log files                            │
│  results/   — debate transcripts, verdict JSON                   │
└───────────────────────────────────────────────────────────────────┘
         │                              │
         ▼                              ▼
  LLM API (external)          Web Search API (external)
  [all calls via Gatekeeper]  [debaters only, via Gatekeeper]
```

---

## 4. Architectural Decision Records (ADRs)

### ADR-001: IPC via JSON over subprocess pipes

**Decision:** Use Python `subprocess` with stdin/stdout pipes; all messages are strict JSON.

**Rationale:** Parseable by the orchestrator, token-efficient (no extra formatting overhead), easily validated against schemas, and compatible with the Watchdog (process handle available from `subprocess.Popen`).

**Alternatives considered:**
- Sockets / ZeroMQ: More complex setup, overkill for a single-machine system.
- Shared memory / multiprocessing.Queue: Harder to log and audit message content.

**Trade-off:** stdout must be reserved for IPC; debug prints must go to stderr or the logger.

---

### ADR-002: Separate processes (not threads) for agents

**Decision:** Each agent runs as a separate OS process via `subprocess.Popen`.

**Rationale:** True isolation — a hung or crashing agent does not bring down the main process. The Watchdog can kill and restart a process by PID. Aligns with the requirement for Watchdog/Keep-alive.

**Alternatives considered:**
- Threads: Shared memory makes isolation and kill/restart much harder.
- asyncio coroutines: Cannot kill a runaway coroutine without cancellation cooperation.

---

### ADR-003: Judge has no internet access (enforced at tool level)

**Decision:** The Judge agent is instantiated without the `WebSearchTool`; only debaters receive it.

**Rationale:** Requirement states "The Judge has NO internet access. It must form its evaluations solely based on the arguments and citations provided by the debating agents."

**Trade-off:** Judge cannot verify citation accuracy — this is intentional; it evaluates rhetoric, not truth.

---

### ADR-004: SDK as single entry point

**Decision:** All business logic is accessible only through `DebateSDK`. CLI and tests import only the SDK.

**Rationale:** Enforces separation of concerns; CLI remains a thin delegation layer. Enables future REST/GUI integration without changing business logic.

---

### ADR-005: Rate limits and all config from JSON files

**Decision:** `config/rate_limits.json` and `config/setup.json` hold all configurable values. `ConfigManager` validates version compatibility at startup.

**Rationale:** No hardcoded values in source code per guidelines. Config versioning allows safe upgrades.

---

## 5. API / Interface Contracts

### 5.1 DebateSDK Public Interface

```python
class DebateSDK:
    def start_debate(self, topic: str, rounds: int) -> DebateResult: ...
    def get_transcript(self) -> list[dict]: ...
    def get_verdict(self) -> dict: ...
    def get_queue_status(self) -> dict: ...
    def get_cost_summary(self) -> dict: ...
```

### 5.2 BaseAgent Interface

```python
class BaseAgent:
    def start(self) -> None: ...
    def stop(self) -> None: ...
    def send(self, message: dict) -> None: ...
    def receive(self) -> dict: ...
    def register_skill(self, skill) -> None: ...
```

### 5.3 ApiGatekeeper Interface

```python
class ApiGatekeeper:
    def execute(self, api_call, *args, **kwargs) -> Any: ...
    def get_queue_status(self) -> dict: ...
```

### 5.4 IPC Message Schemas

See `docs/PRD.md` Section 5.3 for the three JSON schemas (routing, reprimand, verdict).

---

## 6. Data Schemas

### DebateResult
```python
@dataclass
class DebateResult:
    topic: str
    rounds_completed: int
    transcript: list[dict]
    verdict: dict          # matches VerdictMessage schema
    cost_summary: dict
    reprimand_count: int
```

### PersuasionScore (internal Judge state)
```python
@dataclass
class PersuasionScore:
    agent_id: str
    round: int
    logical_consistency: float   # 0.0 – 1.0  (weight: 0.5)
    citation_strength: float     # 0.0 – 1.0  (weight: 0.3)
    rhetoric_quality: float      # 0.0 – 1.0  (weight: 0.2)
    cumulative_score: float      # 0.5*logic + 0.3*citation + 0.2*rhetoric
```

---

## 7. Configuration File Schemas

### config/setup.json
```json
{
  "version": "1.00",
  "debate": {
    "default_rounds": 10,
    "language": "en",
    "timeout_seconds": 120
  },
  "agents": {
    "judge_model": "",
    "debater_model": "",
    "temperature": 0.7
  }
}
```

### config/rate_limits.json
```json
{
  "rate_limits": {
    "version": "1.00",
    "services": {
      "default": {
        "requests_per_minute": 30,
        "requests_per_hour": 500,
        "concurrent_max": 5,
        "retry_after_seconds": 30,
        "max_retries": 3,
        "queue_max_depth": 50
      }
    }
  }
}
```

### config/logging_config.json
```json
{
  "version": "1.00",
  "logging": {
    "max_files": 20,
    "max_lines_per_file": 500,
    "log_dir": "logs/",
    "level": "INFO"
  }
}
```
