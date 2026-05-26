# TODO — Task List
# AI Agent Debate Orchestration System
**Version:** 1.02  
**Date:** 2026-05-25  
**Author:** Nadav Goldin  
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
| 3.1 | Write tests for `ipc/schemas.py` | Critical | ✅ Done | Dev | Tests cover all 4 message types, invalid schema rejection |
| 3.2 | Implement `ipc/schemas.py` + `ipc/messages.py` (RoutingMessage, ReprimandMessage, VerdictMessage, ArgumentMessage) | Critical | ✅ Done | Dev | Tests pass; dataclasses with validation; `ArgumentMessage` split to `messages.py` for ≤150 line compliance; re-exported from `schemas.py` |
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
| 5.1 | Write tests for `agents/judge/skills.py` + `verdict.py` | Critical | ✅ Done | Dev | Tests cover all 4 skills; reprimand trigger; score update; verdict output |
| 5.2 | Implement `agents/judge/skills.py` + `agents/judge/verdict.py` | Critical | ✅ Done | Dev | Tests pass; skills defined locally; split: `skills.py` (EnforceDebateMechanics, EvaluatePersuasionScore, RouteTurn ≤129 lines) + `verdict.py` (PersuasionScore, DeclareVerdict ≤150 lines) |
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
| 8.1 | Write tests for `sdk/sdk.py` | Critical | ✅ Done | Dev | Tests cover start_debate, get_transcript, get_verdict, get_cost_summary |
| 8.2 | Implement `sdk/sdk.py` (DebateSDK) | Critical | ✅ Done | Dev | Tests pass; all business logic through SDK; ≤150 lines |
| 8.3 | Implement `src/main.py` (terminal menu) | High | ✅ Done | Dev | Menu works; delegates only to SDK; no business logic; ≤150 lines |

---

## Phase 9 — Quality Gates

| # | Task | Priority | Status | Owner | Definition of Done |
|---|------|----------|--------|-------|--------------------|
| 9.1 | Run `uv run pytest --cov` | Critical | ✅ Done | Dev | Coverage ≥ 85%; no test failures |
| 9.2 | Run `uv run ruff check` | Critical | ✅ Done | Dev | Zero violations |
| 9.3 | Run full integration test (mocked LLM) | Critical | ✅ Done | Dev | Complete debate runs start-to-finish; verdict produced |
| 9.4 | Verify Watchdog restarts hung agent | High | ✅ Done | Dev | Simulated hang triggers kill + restart; debate continues |
| 9.5 | Verify Gatekeeper queues on overflow | High | ✅ Done | Dev | Overflow goes to queue; no crash; drain works |
| 9.6 | Verify no hardcoded values (code review) | Critical | ✅ Done | Dev | Zero hardcoded API URLs, keys, limits in source |

---

## Phase 10 — Deliverables & Finalization

| # | Task | Priority | Status | Owner | Definition of Done |
|---|------|----------|--------|-------|--------------------|
| 10.1 | Run one complete real debate session | Critical | ✅ Done | Dev | Subprocess factory + runner scripts wired; `python src/main.py` runs a real debate end-to-end with live LLM calls |
| 10.1a | Multi-provider support (Anthropic + Gemini) | Critical | ✅ Done | Dev | `llm_provider.py` factory; `LLM_PROVIDER` env var; migrated to `google-genai` SDK; smart retry (waits suggested delay for per-minute limits, fails fast with clear message for daily quota); 246 tests at 95.11% |
| 10.2 | Create architecture diagrams (C4, UML, OOP inheritance) | High | ✅ Done | Dev | Mermaid diagrams in `assets/architecture_c4.md`, `architecture_uml_sequence.md`, `architecture_oop.md` |
| 10.3 | Write `docs/PROMPTS_BOOK.md` | High | ✅ Done | Dev | All 7 debater + 4 judge skill prompts documented with rationale; context engineering improvements documented |
| 10.4 | Create `notebooks/debate_analysis.ipynb` | Medium | ✅ Done | Dev | Round-by-round score chart, dimension breakdown, cost comparison, message distribution; saves charts to assets/ |
| 10.5 | Finalize `README.md` | Critical | ✅ Done | Dev | Quick-start for lecturer, provider setup, architecture, agent pipeline, full 10-round transcript (248 tests · 95%+ coverage) |
| 10.6 | Push to GitHub (public or shared with lecturer) | Critical | ✅ Done | Dev | Repo accessible at github.com/ndvp39/Agents_Debate; `.env` not committed; `.env-example` present |

---

## Phase 11 — Final Polish & New Features

| # | Task | Priority | Status | Owner | Definition of Done |
|---|------|----------|--------|-------|--------------------|
| 11.1 | **Refine Judge: Stateless & Dynamic Evaluation** — Add zero-anchoring (scores shift immediately when a devastating counter lands), refutation/novelty check (penalize argument repetition, reward new dimensions), and strict feedback enforcement (compare current arg against previous turn's exact feedback; deduct for ignore, boost for compliance). Update `EvaluatePersuasionScore` prompt and `RouteTurn` prompt in `llm_provider.py` and `skills.py`. | Critical | ✅ Done | Dev | Evaluate LLM prompt updated with ZERO-ANCHORING, NOVELTY, FEEDBACK rules; `EvaluatePersuasionScore` injects 3 context blocks (feedback enforcement, novelty check, refutation check); `RouteTurn` builds full scored prompt passed to `(prompt:str)->str` route LLM; `judge_agent.py` passes prev own arg + opponent arg; 248 tests pass |
| 11.2 | **Refine Judge: Detailed Final Verdict** — Rewrite `DeclareVerdict` justification format. Replace current 6-para structure with the required four named sections: **Key Clashes** (most pivotal argument exchanges), **Feedback Adherence** (per-agent compliance with judge instructions), **Scoring Breakdown** (Logic / Rhetoric / Citations with per-agent averages), **Final Conclusion** (decisive factor + winner declaration). | Critical | ✅ Done | Dev | `_build_verdict_justification` rewritten with KEY CLASHES (best/worst round analysis), FEEDBACK ADHERENCE (per-agent early→late trend with numeric values), SCORING BREAKDOWN (aligned table), FINAL CONCLUSION (primary dimension + weighted formula); 1600+ char output; 248 tests pass |
| 11.3 | **Fix/Verify Orphan Process Prevention** — Audit `sdk.py` and `orchestrator.py`. Ensure a `try…finally` block (or equivalent) that terminates all three subprocesses (Pro, Con, Judge) on normal exit AND on crash/exception. Verify no zombie processes are left after a `KeyboardInterrupt` or `IPCTimeoutError`. | Critical | ✅ Done | Dev | Moved `_register_watchdog` inside `try` block; replaced `_shutdown` with 3-phase cleanup (stdin.close → terminate → wait(3s)/kill fallback); added outer `except` guard in `sdk.start_debate` to handle partial factory failures; 248 tests pass |
| 11.4 | **Prompt & Skill Logging** — Create/update `logs/prompts_snapshot.md` with all system prompts, agent skills, and judge routing instructions in their final form. | High | ✅ Done | Dev | `logs/prompts_snapshot.md` exists; all 4 judge skill prompts + 7 debater skill prompts + routing instructions documented |
| 11.5 | **Debate Execution — Clean 10-Round Run** — Run a full, fresh 10-round live debate (Gemini API). Monitor for token-limit crashes (empty output seen in a previous round 9). Capture complete clean transcript; save to `results/`. | Critical | ✅ Done | Dev | Clean 10-round transcript in `results/debate_2026-05-26_2131.txt` + `.json`; topic: "Will artificial intelligence replace human jobs"; Agent_Con wins 89 vs 85; no empty-output rounds; no crashes; empty-response retry fix (11.9) confirmed working |
| 11.6 | **Static HTML Debate Viewer** — Add a feature to the Orchestrator or SDK to auto-generate `debate_viewer.html` at the end of every run. Requirements: standalone file (no server), embedded CSS, distinct chat bubbles for Pro/Con, highlighted panel for Judge feedback/verdict, visual score bars. Anyone can open it in a browser without running Python. | High | ✅ Done | Dev | `generate_html.py` at project root; auto-called from `run_once.py`; dark theme; Pro=blue right bubbles, Con=orange left bubbles; judge routing=grey cards, reprimand=red cards; animated score bars; gold verdict panel with 4-section LLM justification highlighted; `debate_2026-05-26_2131.html` generated (116 KB); opens in browser with no server |
| 11.7 | **Comprehensive Documentation & Project Update** — Update `docs/PLAN.md`, `docs/PRD.md`, `docs/PRD_judge_agent.md`, `docs/PROMPTS_BOOK.md` to reflect new judge behavior (11.1/11.2), HTML viewer (11.6), and orphan-fix (11.3). Update `README.md` with mention of `debate_viewer.html` and refresh transcript if needed. Update Jupyter notebook graphs with any new run data. | High | ✅ Done | Dev | All PRDs/PLAN/PROMPTS_BOOK updated ✅; README refreshed with 2026-05-26 run transcript (89 vs 85), `run_once.py` quick-start, HTML viewer mention, 253-test quality gate; notebook updated with new per-round scores + re-executed (new charts saved to assets/) |
| 11.8 | **Code Restructuring — ≤150 Line Compliance** — Audit all `src/` files against PRD §6 requirement. Split oversized files: `skills.py`→`verdict.py`, `llm_provider.py`→`llm_anthropic.py`+`llm_gemini.py`+`llm_retry.py`, `schemas.py`→`messages.py`. Update all imports and test patches. Re-verify 248 tests pass at ≥85% coverage. | Critical | ✅ Done | Dev | All 38 `src/` files ≤150 lines; 253 tests pass at 92.75% coverage; 0 ruff violations |
| 11.9 | **Empty Response Retry** — Extend `_retry()` in `llm_retry.py` to detect `None` or empty-string LLM responses and retry up to 3 times with a 2 s delay before raising `ValueError`. Covers both Gemini and Anthropic providers. | Critical | ✅ Done | Dev | `_EMPTY_MAX_RETRIES=3`, `_EMPTY_RETRY_DELAY=2.0` added; `try…else` branch checks falsy result; 3 new tests (`test_retry_retries_on_empty_string_then_succeeds`, `test_retry_retries_on_none_response_then_succeeds`, `test_retry_raises_after_max_empty_retries`); 253 tests pass |
| 11.10 | **LLM-Generated Final Verdict** — Replace `DeclareVerdict`'s template-filled justification with an LLM call. Add `_build_verdict_context()` (structured score data block) and `_build_verdict_prompt()` (4-section instruction: KEY CLASHES / FEEDBACK ADHERENCE / SCORING BREAKDOWN / FINAL CONCLUSION). Add `make_judge_verdict_llm()` factory (800 token limit) to all three provider files. Wire `verdict_llm` through `JudgeAgent` → `judge_runner.py`. Fallback to plain context block when no LLM supplied. | Critical | ✅ Done | Dev | `verdict.py` 125 lines ≤150; `make_judge_verdict_llm` in `llm_provider.py`, `llm_gemini.py`, `llm_anthropic.py`; `JudgeAgent` accepts `verdict_llm` param; `judge_runner.py` wired; 2 new tests; 253 tests pass at 92.75%; 0 ruff violations |

---

---

## Phase 12 — README Enrichment & Cross-Doc Consistency

| # | Task | Priority | Status | Owner | Definition of Done |
|---|------|----------|--------|-------|--------------------|
| 12.1 | **Fix round-count wording everywhere** — Replace "20 debater turns" with "10 rounds (1 Pro + 1 Con each)" in README, notebook, and any other doc that uses the "20 turns" framing. Fix model name inconsistency (Gemini 2.0 vs 3.1 Flash Lite — verify against `config/setup.json` and use that value everywhere). Fix stale "248 tests · 95%+" in TODO.md line 153 → "253 tests · 92%+". Add `TOPIC` constant value from `run_once.py` to the non-interactive quick-start step in README. | High | 🔴 Not Started | Dev | Zero occurrences of "20 debater turns"; model name consistent across README + notebook + TODO; topic shown in quick-start |
| 12.2 | **Embed charts in README** — Add all 5 analysis charts as inline images directly in README under a new "Debate Analysis" section: `score_chart.png`, `dimension_chart.png`, `final_scores.png`, `cost_comparison.png`, `message_distribution.png`. Include a short caption for each. Viewers must be able to see full results without running any code. | High | 🔴 Not Started | Dev | All 5 charts visible in README on GitHub; each has a caption; section is clearly titled |
| 12.3 | **Link / preview the HTML viewer in README** — Add a "Debate Viewer" section to README that describes the HTML output, shows the path (`results/debate_<timestamp>.html`), explains how to open it, and links to `generate_html.py`. Include the LLM verdict text (4 sections) inline in README so the debate outcome is fully readable without opening any file. | High | 🔴 Not Started | Dev | Verdict text visible in README; HTML viewer explained with path; verdict sections readable inline |
| 12.4 | **Full doc consistency audit & fix** — Verify `docs/PRD_judge_agent.md`, `docs/PROMPTS_BOOK.md`, `docs/PLAN.md`, `docs/PRD_ipc_protocol.md` all reflect: (a) 89 vs 85 final scores, (b) LLM-generated verdict with 4 sections, (c) empty-response retry in `llm_retry.py`, (d) `run_once.py` + `generate_html.py` existence, (e) 253 tests / 92%+. Update any stale lines. | Medium | 🔴 Not Started | Dev | No doc references stale scores, test counts, or missing features |

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
| 8 — SDK + CLI | 3 | 3 ✅ |
| 9 — Quality gates | 6 | 6 ✅ |
| 10 — Deliverables | 7 | 7 ✅ |
| 11 — Final Polish & New Features | 10 | 10 ✅ |
| 12 — README Enrichment & Cross-Doc Consistency | 4 | 0 🔴 |
| **Total** | **85** | **81** |
