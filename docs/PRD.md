# PRD — AI Agent Debate Orchestration System
**Version:** 1.00  
**Date:** 2026-05-23  
**Course:** AI Agents MSC — Exercise 02

---

## 1. Project Overview & Context

This project implements a fully autonomous debate system orchestrated by three AI agents running as separate processes and communicating via IPC. Two debating agents (Pro and Con) argue opposing sides of a topic while a third agent (the Judge) manages the debate flow, enforces rules, and declares a definitive winner.

The system must run completely autonomously from the moment it is executed — no manual intervention is allowed mid-run.

---

## 2. Target Audience

- MSC students and researchers studying multi-agent AI systems.
- Developers exploring LLM orchestration patterns, anti-sycophancy techniques, and inter-process communication.
- Course lecturer (Dr. Yoram Segal) evaluating the project.

---

## 3. Problem Statement

Large Language Models (LLMs) exhibit sycophantic behavior — they tend to agree with opposing arguments rather than maintaining their assigned stance. This project addresses that challenge by designing a structured, rule-enforced debate system where:

- Agents are architecturally prevented from agreeing with each other.
- A neutral, internet-restricted Judge enforces intellectual rigor and rhetorical standards.
- All communication is structured and parseable (JSON IPC) to ensure reliability and cost control.

---

## 4. Goals & Measurable Acceptance Criteria

| Goal | Acceptance Criterion |
|------|----------------------|
| Fully autonomous execution | Running `main.py` starts and completes the entire debate without any manual input |
| Anti-sycophancy enforcement | Judge reprimands any debater that agrees with the opponent; reprimand count tracked in logs |
| Definitive winner declared | Final verdict JSON includes winner, two scores (no ties), and detailed justification |
| Structured IPC | All inter-agent messages parse as valid JSON matching defined schemas |
| Resilience | No agent hang causes a system crash; Watchdog restarts failed processes automatically |
| Cost control | Gatekeeper enforces token/rate limits; no API call bypasses it |
| Test coverage | `pytest --cov` reports ≥ 85% coverage |
| Lint compliance | `ruff check` reports zero violations |
| Debate length | 10 ping-pongs completed (or 5 if budget-constrained, stated in README) |

---

## 5. Functional Requirements

### 5.1 Agent Definitions

#### Agent 1 — Judge ("The Father")
- Persona: objective, authoritative, strictly analytical, neutral.
- Has **no internet access**; evaluates only from arguments and citations provided by debaters.
- Manages speaking turns by sending `routing` JSON messages.
- Issues `reprimand` JSON messages if a debater:
  - Agrees with the opponent.
  - Fails to provide a reasoned counter-argument.
  - Fails to directly address the opponent's previous claims.
- At the final round, executes `Declare_Verdict`:
  - Declares a definitive winner (ties are **forbidden**).
  - Assigns a score/percentage to each agent (e.g., 85% vs 72%).
  - Provides detailed justification based on persuasiveness and rhetorical skill, **not** objective factual truth.

**Judge Skills:**
| Skill | Description |
|-------|-------------|
| `Enforce_Debate_Mechanics` | Evaluates incoming message; checks direct rebuttal, citation presence, no agreement. Bounces back with reprimand if failed. |
| `Route_Turn` | Summarizes core point just made, defines the next target agent, sends routing JSON. |
| `Evaluate_Persuasion_Score` | Internal metric updated round-by-round: logical consistency + citation strength. |
| `Declare_Verdict` | Final-round output: winner, scores, justification. |

#### Agent 2 — Pro Debater
- Assigned stance: completely **FOR** the debate topic.
- Must directly address the specific claims made by the Con agent in the previous turn.
- Must never agree with the opponent.
- Has a **web-search tool** to retrieve real-world citations, quotes, and facts.

#### Agent 3 — Con Debater
- Assigned stance: completely **AGAINST** the debate topic.
- Must directly address the specific claims made by the Pro agent in the previous turn.
- Must never agree with the opponent.
- Has a **web-search tool** to retrieve real-world citations, quotes, and facts.

---

### 5.2 Communication Flow

- Debaters **never** communicate directly.
- Flow is always: `Pro → Judge → Con → Judge → Pro → ...`
- Total rounds: **10 ping-pongs** (argument + counter-argument per side). May be reduced to **5** if budget/token limits require it; this reduction must be explicitly stated in `README.md`.
- Debate language: **English only** — all internal routing, reasoning, and outputs.

---

### 5.3 IPC Protocol (JSON Schemas)

All inter-process communication is strict JSON.

**Routing Turn:**
```json
{
  "message_type": "routing",
  "target_agent": "Agent_B",
  "judge_feedback": "...",
  "prompt_for_next": "..."
}
```

**Reprimand:**
```json
{
  "message_type": "reprimand",
  "target_agent": "Agent_A",
  "reprimand_issued": true,
  "prompt_for_next": "Rewrite and provide a counter-argument."
}
```

**Final Verdict:**
```json
{
  "message_type": "verdict",
  "winner": "Agent_B",
  "scores": {"Agent_A": 75, "Agent_B": 88},
  "justification": "..."
}
```

---

### 5.4 Watchdog & Resilience
- Every agent process has a Watchdog/Keep-alive timer.
- If an agent hangs beyond the configured timeout: the Watchdog kills the process and restarts it automatically.
- No manual intervention is allowed mid-run.

---

### 5.5 API Gatekeeper (Token/Cost Protection)
- All external API calls (LLM calls, web-search calls) must pass through the Gatekeeper.
- Gatekeeper tracks token usage and enforces rate limits.
- On overflow: requests are queued (FIFO), not dropped or crashed.
- Rate limits and queue settings loaded from `config/rate_limits.json` — never hardcoded.

---

### 5.6 Logging
- Structured logging via a FIFO queue.
- Configuration-driven: up to **20 log files**, max **500 lines per file**.
- Config loaded from `config/logging_config.json`.

---

### 5.7 SDK & Terminal Menu
- An SDK layer exposes all business logic (start debate, get transcript, get verdict, etc.).
- A CLI terminal menu (keyboard inputs) delegates exclusively to the SDK — no business logic in the CLI layer.

---

## 6. Non-Functional Requirements

| Category | Requirement |
|----------|-------------|
| Language | Pure Python |
| OOP | Classes and inheritance; shared logic in base class; no code duplication (DRY) |
| Package Manager | `uv` only — no pip, venv, or `python -m` |
| Configuration | All configurable values from config files; no hardcoded values |
| Secrets | No API keys in source; use `.env` file; `.env-example` committed |
| Code quality | Ruff linter, zero violations |
| Testing | TDD (Red-Green-Refactor), ≥ 85% coverage |
| File size | Every code file ≤ 150 lines of code |
| Skills scope | Agent skills defined locally within the project, not globally |
| Version tracking | Initial version `1.00` in `version.py` and all JSON configs |

---

## 7. User Stories

1. As a **user**, I run `uv run python src/main.py` and the entire debate executes autonomously from start to finish.
2. As a **user**, I can use the terminal menu to choose a debate topic, set the number of rounds, and start the debate.
3. As a **researcher**, I can read the structured log files to trace every agent message, reprimand, and score update.
4. As a **developer**, I can import the SDK and programmatically trigger a debate and retrieve the verdict and transcript.
5. As the **Judge agent**, if a debater agrees with the opponent, I issue a reprimand and return the turn without advancing the round.
6. As a **debater agent**, I receive a routing message from the Judge, retrieve supporting citations via web-search, and reply with a direct counter-argument.

---

## 8. Assumptions

- An LLM API key is available via environment variable. Supported providers: **Google Gemini** (default, free tier at aistudio.google.com) and **Anthropic Claude**. The active provider is selected via the `LLM_PROVIDER` environment variable.
- A web-search API key is available via environment variable for debater agents.
- The system runs on a machine with Python 3.10+ and `uv` installed.
- Internet access is available for debater agents' web-search tool; the Judge agent does not use it.

---

## 9. Constraints

- The Judge has **no internet access** — enforced at the prompt/tool level.
- Ties in the final verdict are **forbidden**.
- The debate language is **English only**.
- Agent skills must be defined **locally** within the project.
- No business logic in the CLI layer.
- All API calls go through the Gatekeeper — no exceptions.

---

## 10. Out of Scope

- GUI (graphical user interface) — CLI only.
- Support for more than 3 agents in a single debate session.
- Multi-language debate support.
- Persistent debate storage beyond the current session's log files and results directory.
- Real-time streaming output to a web interface.

---

## 11. Dependencies

| Dependency | Purpose |
|------------|---------|
| `uv` | Package and environment management |
| `anthropic` SDK | LLM API calls when `LLM_PROVIDER=anthropic` |
| `google-genai` SDK | LLM API calls when `LLM_PROVIDER=gemini` (default) |
| Web-search library (TBD) | Debater agents' citation retrieval |
| `pytest` + `pytest-cov` | Testing and coverage |
| `ruff` | Linting |
| `python-dotenv` | `.env` file loading |

---

## 12. Timeline & Milestones

| Milestone | Deliverable |
|-----------|-------------|
| M0 — Docs approved | `PRD.md`, `PLAN.md`, `TODO.md`, all `PRD_*.md` files reviewed and approved |
| M1 — Project skeleton | Directory structure, `pyproject.toml`, config files, `.env-example` |
| M2 — Shared infrastructure | `config.py`, `version.py`, `gatekeeper.py`, `logger.py` with tests |
| M3 — IPC protocol | JSON schema models and channel layer with tests |
| M4 — Base agent + Watchdog | `base_agent.py`, `watchdog.py` with tests |
| M5 — Judge agent | All four Judge skills implemented with tests |
| M6 — Debater agents | Pro, Con, web-search tool with tests |
| M7 — Orchestrator | Full debate loop with tests |
| M8 — SDK + CLI | `sdk.py`, terminal menu, integration tests |
| M9 — Quality gates | Coverage ≥ 85%, ruff zero violations, full integration test |
| M10 — Deliverables | Transcript, architecture diagrams, prompts book, README finalized |
