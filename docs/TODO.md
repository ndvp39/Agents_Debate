# TODO — Task List
# AI Agent Debate Orchestration System
**Version:** 2.00
**Date:** 2026-05-29
**Status:** ✅ **Project complete** — initial 30-phase plan executed; all integration fixes landed.

---

## Status summary

The original Phase 0-13 TODO (PRD authoring → skeleton → IPC → agents → orchestrator → integration → documentation → polish) was completed under the version-1 plan and merged before 2026-05-26. Subsequent integration fixes are tracked here in commit order. The project is complete and ready for review.

## Post-v1 integration fix log

| Commit | Title | Scope |
|---|---|---|
| `ac3d46b` | refactor(skills): replace Python prompt-builder classes with Anthropic Skill protocol | 11 SKILL.md folders + loader; agents wired through `SkillLoader` |
| `651a5a8` | fix(debate): relay opponent arguments through the judge and clean turn handoff | `RoutingMessage.previous_argument` field; `compose_next_turn_prompt` split out as deterministic skill |
| `5a21d61` | feat(search): wire real Tavily web search into debater agents | `make_tavily_search`; per-runner Tavily key; honest `[no web sources retrieved]` marker replaces fabricated `Searched: <topic>` citation |
| `ab99cdf` | improve(search): use advanced Tavily depth and exclude low-credibility domains | `search_depth="advanced"`; `exclude_domains=[facebook/quora/reddit/pinterest]` |
| `387d725` | feat(watchdog): wire live process monitoring with self-repair for all agents | SDK constructs/injects `Watchdog`; orchestrator arms timers; per-agent spawn closures; `RoutingMessage.round_number`; judge atomic checkpoint; integration test boots a hung subprocess and asserts kill+respawn+resend |
| `7ea57b3` | feat(gatekeeper): route all API calls through rate-limited gatekeepers with cost tracking | Per-subprocess `ApiGatekeeper` for LLM + web_search; `record_tokens` captures `response.usage`; SDK aggregates per-agent cost dumps into `DebateResult.cost_summary`; grep proves no provider call site outside the gate |
| `52b5134` | chore(skills): remove legacy skills.py classes superseded by the SKILL.md loader | Deleted `agents/debaters/skills.py`, `agents/judge/skills.py`, and their tests |
| `f78cc29` | fix(reliability): stop gatekeeper double-retrying fatal errors; recover from runner error-exit; add per-call timing | Gatekeeper single-shot (no retry — `_retry` owns policy); orchestrator detects runner clean-exit via `Popen.poll()` and manually respawns; per-call `[label] attempt=N took=Xs result=...` logging; judge checkpoint empty-file fix |
| `3bcda95` | fix(cost): honor active provider in cost aggregation; provider-aware watchdog timeout | `cost_aggregator` calls `get_active_provider(setup)` (honors `LLM_PROVIDER` env); per-provider `timeout_seconds`; corrected the Sonnet deliverable artifact's `cost_summary` from Gemini rates to real $1.6115 |
| `69bf62c` | docs: align README and analysis notebook with the real deliverable run | README rewritten for the implemented system (SKILL.md, watchdog, gatekeeper, real costs, verbatim transcript excerpt); notebook regenerated from real JSON; 5 PNGs refreshed |

## Quality gate (current)

- **Tests:** 276 passed (unit + integration including `test_watchdog_recovery.py`)
- **Coverage:** 92 %+
- **Ruff:** 0 violations
- **Live deliverable:** `results/debate_2026-05-28_1800.{txt,json,html}` — 10 rounds on Claude Sonnet 4.6, Agent_Con 73 vs Agent_Pro 71, 121 gated calls, 223,090 tokens, $1.6115
