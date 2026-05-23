# TODO — Task List
# AI Agent Debate Orchestration System
**Version:** 1.00  
**Date:** 2026-05-23  
**Legend:** 🔴 Not Started | 🟡 In Progress | ✅ Done

---

## Phase 0 — Documentation (must be fully approved before any code)

| # | Task | Priority | Status | Owner | Definition of Done |
|---|------|----------|--------|-------|--------------------|
| 0.1 | Write `docs/PRD.md` | Critical | ✅ Done | Dev | PRD reviewed and approved by user |
| 0.2 | Write `docs/PLAN.md` | Critical | ✅ Done | Dev | PLAN reviewed and approved by user |
| 0.3 | Write `docs/TODO.md` | Critical | ✅ Done | Dev | TODO reviewed and approved by user |
| 0.4 | Write `docs/PRD_debate_orchestrator.md` | Critical | ✅ Done | Dev | Covers orchestration loop, round management, process lifecycle |
| 0.5 | Write `docs/PRD_ipc_protocol.md` | Critical | ✅ Done | Dev | Covers all 3 JSON schemas, validation rules, error handling |
| 0.6 | Write `docs/PRD_judge_agent.md` | Critical | ✅ Done | Dev | Covers all 4 skills, scoring logic, verdict rules |
| 0.7 | Write `docs/PRD_debater_agents.md` | Critical | ✅ Done | Dev | Covers anti-sycophancy directive, web-search integration |
| 0.8 | Write `docs/PRD_api_gatekeeper.md` | Critical | ✅ Done | Dev | Covers rate limits, FIFO queue, retry, token tracking |
| 0.9 | Write `docs/PRD_watchdog.md` | Critical | ✅ Done | Dev | Covers timeout detection, kill, restart logic |
| 0.10 | Write `docs/PRD_logging.md` | Critical | ✅ Done | Dev | Covers FIFO rotation, file limits, structured format |
| 0.11 | **User approves all Phase 0 docs** | Critical | ✅ Done | User | All docs reviewed; written approval to proceed |
| 0.12 | Write `docs/PRD_debater_skills.md` | Critical | ✅ Done | Dev | Covers all 7 skills with I/O, pipeline order, test scenarios |

---

## Phase 1 — Project Skeleton & Configuration

| # | Task | Priority | Status | Owner | Definition of Done |
|---|------|----------|--------|-------|--------------------|
| 1.1 | Initialize `uv` project (`pyproject.toml`, `uv.lock`) | Critical | ✅ Done | Dev | `uv sync` runs without error |
| 1.2 | Create full directory structure | Critical | ✅ Done | Dev | All dirs exist: src/, tests/, docs/, config/, data/, results/, assets/, notebooks/, logs/ |
| 1.3 | Create `config/setup.json` (versioned) | Critical | ✅ Done | Dev | Passes schema validation; version = "1.00" |
| 1.4 | Create `config/rate_limits.json` (versioned) | Critical | ✅ Done | Dev | Passes schema validation; version = "1.00" |
| 1.5 | Create `config/logging_config.json` (versioned) | Critical | ✅ Done | Dev | Passes schema validation; version = "1.00" |
| 1.6 | Create `.env-example` with placeholder keys | Critical | ✅ Done | Dev | All required env vars documented; no real values |
| 1.7 | Create `.gitignore` | High | ✅ Done | Dev | Includes `.env`, `*.pem`, `*.key`, `__pycache__`, `.venv`, `uv.lock` exceptions |
| 1.8 | Configure `pyproject.toml` (ruff, pytest-cov, uv scripts) | Critical | ✅ Done | Dev | `uv run ruff check` and `uv run pytest` both executable |
| 1.9 | Create all `__init__.py` files | High | ✅ Done | Dev | Every package directory has `__init__.py` with `__all__` and `__version__` |

---

## Phase 2 — Shared Infrastructure (TDD: write tests first)

| # | Task | Priority | Status | Owner | Definition of Done |
|---|------|----------|--------|-------|--------------------|
| 2.1 | Write tests for `constants.py` | High | ✅ Done | Dev | Tests written (RED) |
| 2.2 | Implement `shared/constants.py` | High | ✅ Done | Dev | Tests pass (GREEN); ruff clean; ≤150 lines |
| 2.3 | Write tests for `shared/version.py` | High | ✅ Done | Dev | Tests written (RED) |
| 2.4 | Implement `shared/version.py` (VERSION = "1.00") | High | ✅ Done | Dev | Tests pass; version exported correctly |
| 2.5 | Write tests for `shared/config.py` | Critical | ✅ Done | Dev | Tests cover load, version validation, missing key errors |
| 2.6 | Implement `shared/config.py` | Critical | ✅ Done | Dev | Tests pass; loads all 3 config files; validates version |
| 2.7 | Write tests for `shared/gatekeeper.py` | Critical | ✅ Done | Dev | Tests cover rate limiting, queue overflow, retry, logging |
| 2.8 | Implement `shared/gatekeeper.py` (ApiGatekeeper) | Critical | ✅ Done | Dev | Tests pass; FIFO queue; no API call bypasses it; ≤150 lines |
| 2.9 | Write tests for `shared/logger.py` | High | ✅ Done | Dev | Tests cover file rotation, line limit, FIFO behavior |
| 2.10 | Implement `shared/logger.py` (DebateLogger) | High | ✅ Done | Dev | Tests pass; respects config limits; ≤150 lines |

---

## Phase 3 — IPC Protocol (TDD)

| # | Task | Priority | Status | Owner | Definition of Done |
|---|------|----------|--------|-------|--------------------|
| 3.1 | Write tests for `ipc/schemas.py` | Critical | ✅ Done | Dev | Tests cover all 3 message types, invalid schema rejection |
| 3.2 | Implement `ipc/schemas.py` (RoutingMessage, ReprimandMessage, VerdictMessage) | Critical | ✅ Done | Dev | Tests pass; dataclasses with validation; ≤150 lines |
| 3.3 | Write tests for `ipc/channel.py` | Critical | ✅ Done | Dev | Tests cover send, receive, malformed JSON handling |
| 3.4 | Implement `ipc/channel.py` (IPCChannel) | Critical | ✅ Done | Dev | Tests pass; JSON serialization/deserialization; ≤150 lines |

---

## Phase 4 — Base Agent & Watchdog (TDD)

| # | Task | Priority | Status | Owner | Definition of Done |
|---|------|----------|--------|-------|--------------------|
| 4.1 | Write tests for `agents/base_agent.py` | Critical | ✅ Done | Dev | Tests cover start, stop, send, receive, skill registration |
| 4.2 | Implement `agents/base_agent.py` (BaseAgent) | Critical | ✅ Done | Dev | Tests pass; shared logic only; ≤150 lines |
| 4.3 | Write tests for `agents/watchdog.py` | Critical | ✅ Done | Dev | Tests cover timeout detection, kill, restart |
| 4.4 | Implement `agents/watchdog.py` (Watchdog) | Critical | ✅ Done | Dev | Tests pass; auto-restarts hung process; ≤150 lines |

---

## Phase 5 — Judge Agent (TDD)

| # | Task | Priority | Status | Owner | Definition of Done |
|---|------|----------|--------|-------|--------------------|
| 5.1 | Write tests for `agents/judge/skills.py` | Critical | ✅ Done | Dev | Tests cover all 4 skills; reprimand trigger; score update; verdict output |
| 5.2 | Implement `agents/judge/skills.py` | Critical | ✅ Done | Dev | Tests pass; skills defined locally; ≤150 lines |
| 5.3 | Write tests for `agents/judge/judge_agent.py` | Critical | ✅ Done | Dev | Tests cover no-internet enforcement, scoring rounds, verdict (no ties) |
| 5.4 | Implement `agents/judge/judge_agent.py` (JudgeAgent) | Critical | ✅ Done | Dev | Tests pass; inherits BaseAgent; ≤150 lines |

---

## Phase 6 — Debater Agents (TDD)

| # | Task | Priority | Status | Owner | Definition of Done |
|---|------|----------|--------|-------|--------------------|
| 6.1 | Write tests for `agents/debaters/web_search_tool.py` | High | ✅ Done | Dev | Tests cover search call, gatekeeper routing, result parsing |
| 6.2 | Implement `agents/debaters/web_search_tool.py` | High | ✅ Done | Dev | Tests pass; all calls via Gatekeeper; ≤150 lines |
| 6.3 | Write tests for `agents/debaters/skills.py` | Critical | ✅ Done | Dev | Tests cover all 7 skills, pipeline order, SkillNotApplicableError |
| 6.4 | Implement `agents/debaters/skills.py` | Critical | ✅ Done | Dev | Tests pass; all 7 skills locally defined; ≤150 lines per file |
| 6.5 | Write tests for `agents/debaters/base_debater.py` | Critical | ✅ Done | Dev | Tests cover skill pipeline execution, anti-sycophancy, direct rebuttal |
| 6.6 | Implement `agents/debaters/base_debater.py` (BaseDebater) | Critical | ✅ Done | Dev | Tests pass; inherits BaseAgent; runs skill pipeline; ≤150 lines |
| 6.7 | Write tests for `agents/debaters/pro_agent.py` | Critical | ✅ Done | Dev | Tests cover FOR stance enforcement |
| 6.8 | Implement `agents/debaters/pro_agent.py` (ProAgent) | Critical | ✅ Done | Dev | Tests pass; inherits BaseDebater; ≤150 lines |
| 6.9 | Write tests for `agents/debaters/con_agent.py` | Critical | ✅ Done | Dev | Tests cover AGAINST stance enforcement |
| 6.10 | Implement `agents/debaters/con_agent.py` (ConAgent) | Critical | ✅ Done | Dev | Tests pass; inherits BaseDebater; ≤150 lines |

---

## Phase 7 — Orchestrator (TDD)

| # | Task | Priority | Status | Owner | Definition of Done |
|---|------|----------|--------|-------|--------------------|
| 7.1 | Write tests for `services/orchestrator.py` | Critical | ✅ Done | Dev | Tests cover full 10-round loop, reprimand handling, early termination, verdict receipt |
| 7.2 | Implement `services/orchestrator.py` (DebateOrchestrator) | Critical | ✅ Done | Dev | Tests pass; manages Pro→Judge→Con flow; ≤150 lines |

---

## Phase 8 — SDK & CLI (TDD)

| # | Task | Priority | Status | Owner | Definition of Done |
|---|------|----------|--------|-------|--------------------|
| 8.1 | Write tests for `sdk/sdk.py` | Critical | 🔴 Not Started | Dev | Tests cover start_debate, get_transcript, get_verdict, get_cost_summary |
| 8.2 | Implement `sdk/sdk.py` (DebateSDK) | Critical | 🔴 Not Started | Dev | Tests pass; all business logic through SDK; ≤150 lines |
| 8.3 | Implement `src/main.py` (terminal menu) | High | 🔴 Not Started | Dev | Menu works; delegates only to SDK; no business logic; ≤150 lines |

---

## Phase 9 — Quality Gates

| # | Task | Priority | Status | Owner | Definition of Done |
|---|------|----------|--------|-------|--------------------|
| 9.1 | Run `uv run pytest --cov` | Critical | 🔴 Not Started | Dev | Coverage ≥ 85%; no test failures |
| 9.2 | Run `uv run ruff check` | Critical | 🔴 Not Started | Dev | Zero violations |
| 9.3 | Run full integration test (mocked LLM) | Critical | 🔴 Not Started | Dev | Complete debate runs start-to-finish; verdict produced |
| 9.4 | Verify Watchdog restarts hung agent | High | 🔴 Not Started | Dev | Simulated hang triggers kill + restart; debate continues |
| 9.5 | Verify Gatekeeper queues on overflow | High | 🔴 Not Started | Dev | Overflow goes to queue; no crash; drain works |
| 9.6 | Verify no hardcoded values (code review) | Critical | 🔴 Not Started | Dev | Zero hardcoded API URLs, keys, limits in source |

---

## Phase 10 — Deliverables & Finalization

| # | Task | Priority | Status | Owner | Definition of Done |
|---|------|----------|--------|-------|--------------------|
| 10.1 | Run one complete real debate session | Critical | 🔴 Not Started | Dev | Transcript saved to `results/`; verdict JSON present |
| 10.2 | Create architecture diagrams (C4, UML, OOP inheritance) | High | 🔴 Not Started | Dev | Diagrams saved to `assets/`; referenced in README |
| 10.3 | Write `docs/PROMPTS_BOOK.md` | High | 🔴 Not Started | Dev | All agent prompts documented with rationale and refinements |
| 10.4 | Create `notebooks/debate_analysis.ipynb` | Medium | 🔴 Not Started | Dev | Token cost breakdown, round-by-round score chart |
| 10.5 | Finalize `README.md` | Critical | 🔴 Not Started | Dev | Includes: install steps, usage, screenshots, exact prompts, full transcript, ping-limit note |
| 10.6 | Push to GitHub (public or shared with lecturer) | Critical | 🔴 Not Started | Dev | Repo accessible; `.env` not committed; `.env-example` present |

---

## Summary

| Phase | Tasks | Done |
|-------|-------|------|
| 0 — Documentation | 12 | 12 ✅ |
| 1 — Project skeleton | 9 | 9 ✅ |
| 2 — Shared infrastructure | 10 | 10 ✅ |
| 3 — IPC protocol | 4 | 4 ✅ |
| 4 — Base agent + Watchdog | 4 | 4 ✅ |
| 5 — Judge agent | 4 | 4 ✅ |
| 6 — Debater agents | 10 | 10 ✅ |
| 7 — Orchestrator | 2 | 2 ✅ |
| 8 — SDK + CLI | 3 | 0 |
| 9 — Quality gates | 6 | 0 |
| 10 — Deliverables | 6 | 0 |
| **Total** | **70** | **55** |
