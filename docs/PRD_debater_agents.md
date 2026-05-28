# PRD — Debater Agents (Pro & Con)
**Version:** 1.01  
**Date:** 2026-05-23  
**Author:** Nadav Goldin  
**Files:** `src/debate/agents/debaters/base_debater.py`, `pro_agent.py`, `con_agent.py`, `web_search_tool.py`, plus the SKILL.md folders under `src/debate/skills/debater/` (loaded via `SkillLoader` — see `PRD_debater_skills.md`)

---

## 1. Description & Theoretical Background

The Pro and Con agents are the two debating participants. Each is assigned a fixed, irrevocable stance on the debate topic — one completely FOR, one completely AGAINST — and must maintain that stance through all rounds regardless of the opposing arguments.

The central technical challenge is **LLM sycophancy**: the natural tendency of language models to agree with, compliment, or soften their position in response to a persuasive opposing argument. The debater architecture addresses this with an **Anti-Pleasing Directive** embedded at the prompt level and enforced at the message level by the Judge's `Enforce_Debate_Mechanics` skill.

Both agents inherit from `BaseDebater`, which itself inherits from `BaseAgent`. Each turn, `BaseDebater._run_pipeline()` invokes a **7-skill pipeline** that mirrors how a world-class human debater thinks: analyze the opponent, detect fallacies, choose a strategy, build a counter-argument, synthesize evidence, and apply rhetoric. Each skill is a SKILL.md folder under `src/debate/skills/debater/` loaded by the injected `SkillLoader` (Anthropic Skill protocol — see `PRD_debater_skills.md`). The only difference between `ProAgent` and `ConAgent` is the assigned stance constant.

Both agents are equipped with a `WebSearchTool` — the Judge is not. Web search results feed directly into the `SynthesizeEvidence` skill.

---

## 2. Anti-Sycophancy Directive

This is the most critical behavioral constraint. Every debater prompt MUST include the following directive (loaded from config, not hardcoded):

```
CRITICAL DIRECTIVE: You are arguing [STANCE] on the topic "[TOPIC]".
You MUST NEVER agree with, compliment, or validate the opposing argument.
You MUST directly contradict and rebut every specific claim made by your opponent.
Phrases like "good point", "I agree", "that's true", "you're right", "fair point"
are STRICTLY FORBIDDEN. Your only goal is to WIN this debate for your side.
```

This directive is injected by `BaseDebater._build_prompt()` before every LLM call.

---

## 3. Web Search Tool

### 3.1 Purpose
Both debaters use `WebSearchTool` to retrieve real-world citations, quotes, and facts to support their arguments. The Judge cannot verify these, so debaters are incentivized to include credible, specific sources.

### 3.2 Usage Flow
1. Debater receives `prompt_for_next` from the Judge (via orchestrator).
2. `BuildCounterArgument` skill drafts the argument structure.
3. Debater calls `WebSearchTool.search(query)` to find supporting evidence (≤ 3 queries).
4. All search calls go through `ApiGatekeeper` (rate limiting + token tracking).
5. Raw results are passed to `SynthesizeEvidence` skill, which selects the strongest citations.
6. `ApplyRhetoric` weaves citations into the final argument.
7. The final argument is packaged into the `argument` JSON message (`citations` field).

### 3.3 Interface
```python
class WebSearchTool:
    def search(self, query: str) -> list[str]:
        """Return list of citation strings via ApiGatekeeper."""
```

### 3.4 Constraints
- All calls MUST go through `ApiGatekeeper`.
- Max 3 search queries per argument (configured in `setup.json`).
- If search fails (API error), the debater MUST still respond — it cites the failed search gracefully rather than crashing.

---

## 4. BaseDebater Logic

Shared logic in `base_debater.py`:

| Method | Description |
|--------|-------------|
| `respond(routing_message)` | Entry point — runs the full skill pipeline and returns the `argument` JSON |
| `_run_pipeline(topic, stance, opponent_arg, round_num)` | Orchestrates the 7-skill sequence; returns final argument text + citations |
| `_call_llm(prompt)` | Calls the LLM via `ApiGatekeeper`; used by skills that need an LLM call |
| `_build_argument_message(text, citations, round_num)` | Packages final output into the `argument` JSON schema |
| `_inject_anti_sycophancy(prompt)` | Wraps any prompt with the anti-sycophancy directive from config |

### 4.1 Skill Pipeline Execution (per turn)

```
Round 1:   CraftOpening → SynthesizeEvidence → ApplyRhetoric
           (AnalyzeOpponent / DetectFallacies / AdaptStrategy /
            BuildCounterArgument are skipped — no opponent argument yet)

Round 2+:  AnalyzeOpponent → DetectFallacies → AdaptStrategy
               → BuildCounterArgument → SynthesizeEvidence → ApplyRhetoric
```

Each skill in the pipeline receives the output of the previous skill as part of its input context. The anti-sycophancy directive is injected into every LLM call made within any skill.

---

## 5. ProAgent

- Inherits `BaseDebater`.
- Stance constant: `STANCE = "completely FOR"`.
- No additional logic beyond stance assignment.

---

## 6. ConAgent

- Inherits `BaseDebater`.
- Stance constant: `STANCE = "completely AGAINST"`.
- No additional logic beyond stance assignment.

---

## 7. Input / Output

### Input (per turn)
| Field | Source | Description |
|-------|--------|-------------|
| `routing_message` | Judge via Orchestrator | Contains `prompt_for_next`, `judge_feedback`, **`previous_argument`** (the opponent's actual argument text — fed into `analyze_opponent` / `detect_fallacies`), and **`round_number`** (the round the next speaker should use — lets a respawned debater resume on the correct round). |

`BaseDebater.respond` reads `previous_argument` from the routing dict into
`self._last_opponent_arg` (previously this field was sourced from
`prompt_for_next` — a turn-handoff string — which meant `analyze_opponent` was
operating on the wrong input; fixed in commit `651a5a8`). It reads
`round_number` and uses it as `current_round` when non-zero, falling back to
`self._round + 1` otherwise — so a watchdog-restarted debater whose fresh
`_round` is 0 still picks up the correct round number (fixed in `387d725`).

### Output (per turn)
| Field | Type | Description |
|-------|------|-------------|
| `argument` JSON | dict | Full `argument` message with text + citations + round number |

---

## 8. Performance Requirements

| Metric | Target |
|--------|--------|
| Total turn time (full 7-skill pipeline + web search) | < 90 seconds |
| LLM calls per turn | ≤ 4 (skills share calls where logical) |
| Web search queries per turn | ≤ 3 (configured in `setup.json`) |
| Citations per argument | ≥ 1, ≤ 3 (selected by `SynthesizeEvidence`) |
| Memory per debater process | < 200MB |

---

## 9. Constraints

- Debaters MUST NOT communicate directly with each other — only through the Judge/Orchestrator.
- Anti-sycophancy directive MUST be injected on every single LLM call — never omitted.
- All LLM calls and web-search calls MUST go through `ApiGatekeeper` (per-subprocess instances: one `service="llm"` and one `service="web_search"`).
- All 7 debater skills are SKILL.md folders under `src/debate/skills/debater/` — loaded at runtime by `SkillLoader`. (`skills.py` was deleted in `52b5134`.)
- `craft_opening` MUST only run on round 1; the round-1 guard lives in `BaseDebater._run_pipeline` (the previous `SkillNotApplicableError` mechanism was removed when the per-class guard moved into the agent in `ac3d46b`).
- `apply_rhetoric` MUST always be the final skill in the pipeline — never reordered.
- `citations` list in the output message MUST contain at least 1 entry; if web search fails, the debater must note the attempted search.
- `ProAgent` and `ConAgent` MUST NOT duplicate any logic — all shared code lives in `BaseDebater`.

---

## 10. Alternatives Considered

| Alternative | Reason Rejected |
|-------------|----------------|
| Single debater class with a `stance` parameter | Harder to test each stance in isolation; less explicit OOP design |
| Giving the Judge web search access | Requirement explicitly forbids it |
| Allowing debaters to skip citations | Violates requirement; Judge would reprimand every turn |
| Hard-coding the anti-sycophancy prompt | No hardcoded values allowed; prompt must come from config |

---

## 11. Success Criteria

- [x] `ProAgent` never produces an argument containing agreement phrases.
- [x] `ConAgent` never produces an argument containing agreement phrases.
- [x] Every argument message contains at least 1 citation.
- [x] All LLM and web-search calls pass through the Gatekeeper (verifiable via Gatekeeper logs).
- [x] If web search fails, the debater still returns a valid `argument` message.
- [x] `ProAgent` and `ConAgent` share zero duplicated logic (all in `BaseDebater`).
- [x] On round 1, only `craft_opening → synthesize_evidence → apply_rhetoric` run.
- [x] On round 2+, all 6 remaining skills run in the correct order.
- [x] `craft_opening` is only invoked on round 1 (the agent's `if round_number == 1:` branch is the guard; no exception path needed).
- [x] `apply_rhetoric` is always the last skill executed before message construction.

---

## 12. Test Scenarios

| Scenario | Expected Outcome |
|----------|-----------------|
| Pro receives routing message on round 1 | `CraftOpening` runs; `AnalyzeOpponent` skipped; valid `argument` JSON returned |
| Con receives routing message on round 3 | Full 6-skill pipeline runs; valid `argument` JSON with FOR/AGAINST stance returned |
| `_run_pipeline(round_number=2)` invoked with no opponent argument | round-2+ branch runs; `craft_opening` not invoked |
| Anti-sycophancy prompt is removed from config | `ValueError` raised at prompt build time |
| Web search API returns empty results | `SynthesizeEvidence` returns empty citations; argument still returned with note |
| Web search API raises exception | Argument returned without crash; exception logged via `DebateLogger` |
| LLM call rate limit hit | Gatekeeper queues the call; argument returned after drain |
| `DetectFallacies` finds a strawman | Output `fallacies_found` contains "Strawman"; used by `BuildCounterArgument` |
| `AdaptStrategy` called when behind on score | Returns `mode = "defensive"` |
| `ApplyRhetoric` receives enriched argument | Output contains original facts; rhetoric enhanced; no new citations invented |
