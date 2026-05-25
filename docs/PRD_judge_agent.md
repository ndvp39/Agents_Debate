# PRD — Judge Agent
**Version:** 1.02  
**Date:** 2026-05-25  
**Author:** Nadav Goldin  
**Files:** `src/debate/agents/judge/judge_agent.py`, `src/debate/agents/judge/skills.py`, `src/debate/agents/judge/verdict.py`

---

## 1. Description & Theoretical Background

The Judge Agent is the moderator and arbiter of the debate. It acts as a strict, neutral "Father" figure who enforces intellectual rigor, manages speaking turns, tracks persuasion scores round-by-round, and declares a definitive winner at the end.

The Judge's design is based on the **Rule-Based Agent** pattern: it does not improvise; it executes one of exactly four well-defined skills depending on the situation. This makes its behavior predictable, auditable, and testable.

A key design constraint is that **the Judge has no internet access**. It cannot call a web-search tool. It evaluates arguments solely based on the content, reasoning quality, and citations that the debating agents provide. This simulates a real-world judge who rules only on what is presented in court.

The Judge is also the system's **anti-sycophancy enforcer**. Because LLMs naturally drift toward agreement, the Judge's `Enforce_Debate_Mechanics` skill exists specifically to detect and block this behavior.

---

## 2. Persona & Behavioral Rules

- Objective, authoritative, strictly analytical, and neutral.
- Never takes sides.
- Always addresses debaters formally: "It is your turn now, Agent_Pro."
- Must reprimand if a debater:
  - Begins to agree with the opponent.
  - Fails to directly address the opponent's previous claims.
  - Provides no citations.
  - Provides only anecdotal evidence without sources.
  - On round 2+, completely ignores an obvious logical fallacy in the opponent's argument (the Judge expects debaters to call out fallacies given their `DetectFallacies` skill).
- The final verdict MUST name one winner. **Ties are strictly forbidden.**
- The verdict is based on **persuasiveness and rhetorical skill**, not objective factual truth.

---

## 3. Skills

All four skills are defined in `skills.py` and registered locally. The Judge Agent does not use any globally defined skills.

### Skill 1: `EnforceDebateMechanics`

**Trigger:** Received an `argument` message from a debater.

**Logic:**
1. Check if the argument directly addresses the opponent's previous claims. If not → reprimand.
2. Check if `citations` list is non-empty. If empty → reprimand.
3. Check if the argument contains agreement phrases (e.g., "you make a good point", "I agree", "that's correct"). If found → reprimand.
4. On round 2+: check if the argument identifies at least one logical fallacy in the opponent's prior argument (expected because debaters have `DetectFallacies` skill). If the opponent's argument contained an obvious fallacy and the debater completely ignored it → reprimand.
5. If all checks pass → pass the argument to `RouteTurn`.

**Output:** Either a `reprimand` JSON message or calls `RouteTurn`.

---

### Skill 2: `RouteTurn`

**Trigger:** Called after `EvaluatePersuasionScore` produces a score for the current speaker.

**Logic:**
1. Build the full route prompt internally, including scores and (if available) whether the previous instruction was followed.
2. Call the route LLM with the full prompt — returns 2–3 sentences of targeted feedback covering: (a) weakest dimension explanation, (b) repetition call-out if applicable, (c) one mandatory specific instruction for next round.
3. Determine the next target agent (flip Pro ↔ Con).
4. Construct a `routing` JSON message: `judge_feedback` = LLM output; `prompt_for_next` includes a mandatory REMINDER of previous feedback (if any) with explicit penalty warning.
5. Send the message.

**Output:** A `routing` JSON message.

---

### Skill 3: `EvaluatePersuasionScore`

**Trigger:** Called after each valid argument passes `EnforceDebateMechanics`.

**Logic:**
Before calling the evaluate LLM, prepends up to three context blocks to the argument text:

- **FEEDBACK ENFORCEMENT** (if prior feedback exists) — tells the LLM what instruction was previously given and to penalise all dimensions if ignored, or award a boost if followed well.
- **NOVELTY CHECK** (if a prior argument from the same agent exists) — provides the first 300 chars of the agent's previous argument; penalises `logical_consistency` and `citation_strength` if the current argument repeats the same core claims without new evidence or angles.
- **REFUTATION CHECK** (if an opponent argument exists) — provides the first 300 chars of the opponent's last argument; penalises `logical_consistency` if the agent failed to counter it directly.

Scores three sub-dimensions per round (ZERO-ANCHORING: scores shift immediately for strong counter-arguments; prior scoring patterns are explicitly ignored):
- `logical_consistency` (0.0–1.0): Causal coherence; exploits opponent's weakest point. PENALISE: circular reasoning, unsupported assertions, repeating prior claims without new angles.
- `citation_strength` (0.0–1.0): Specific, credible, contextually relevant sourcing. PENALISE: repeating the same sources as a prior round.
- `rhetoric_quality` (0.0–1.0): Effective ethos, pathos, logos; memorability; persuasiveness.

Cumulative score formula (used by `DeclareVerdict`):
```
cumulative_score = 0.5 × avg(logical_consistency)
                 + 0.3 × avg(citation_strength)
                 + 0.2 × avg(rhetoric_quality)
```

**Output:** `PersuasionScore` dataclass for the speaking agent.

---

### Skill 4: `DeclareVerdict`

**Trigger:** Called by the orchestrator after the final round is complete.

**Logic:**
1. Compute final cumulative weighted scores for both agents (`0.5×logic + 0.3×citation + 0.2×rhetoric`).
2. If scores are equal (tie scenario): add a 0.01 tie-breaker to the agent with higher average citation strength across rounds.
3. Identify the winner (higher cumulative score).
4. Construct a **comprehensive, multi-paragraph verdict justification** consisting of exactly four named sections:
   - **KEY CLASHES** — identifies the most and least decisive rounds by pairwise score margin; summarises winner's overall argument quality advantage.
   - **FEEDBACK ADHERENCE** — compares early-round vs. late-round weighted averages per agent to assess how responsively each incorporated the Judge's incremental feedback.
   - **SCORING BREAKDOWN** — aligned table showing per-dimension averages (logic/citation/rhetoric) and final integer percentages for both agents.
   - **FINAL CONCLUSION** — names the winner, states the final percentage scores, identifies the primary winning dimension (largest per-dimension gap), and explains how the weighted formula made it determinative.
5. Return a `verdict` JSON message. Ties are forbidden — the tie-breaker guarantees a winner.

**Output:** A `verdict` JSON message. Justification is deterministically constructed from per-round `PersuasionScore` objects — no LLM call required. Source split: `verdict.py` (PersuasionScore, DeclareVerdict, helpers) + `skills.py` (remaining three skills).

---

## 4. Input / Output

### Input
| Source | Message Type | Description |
|--------|-------------|-------------|
| Orchestrator | `argument` | Debater's argument for evaluation |
| Orchestrator | `"final_round"` signal | Trigger `DeclareVerdict` |

### Output
| Destination | Message Type | Description |
|-------------|-------------|-------------|
| Orchestrator | `routing` | Valid argument accepted, turn advanced |
| Orchestrator | `reprimand` | Argument rejected, same speaker retries |
| Orchestrator | `verdict` | Final winner declaration |

---

## 5. Internet Restriction Enforcement

The Judge Agent is instantiated **without** the `WebSearchTool`. No web-search tool is registered in its skill registry. Any attempt to perform a web search will raise a `ToolNotAvailableError` at the skill-registry level.

---

## 6. Performance Requirements

| Metric | Target |
|--------|--------|
| Time to evaluate one argument and produce routing/reprimand | < 30 seconds (LLM call latency) |
| Time to produce final verdict | < 30 seconds |
| Memory per Judge process | < 200MB |

---

## 7. Constraints

- Skills MUST be defined locally in `skills.py` — not imported from any global/shared skill library.
- No internet access — `WebSearchTool` MUST NOT be registered.
- Ties in `DeclareVerdict` are forbidden — tie-breaker logic is mandatory.
- The Judge MUST reprimand agreement — it cannot let sycophantic behavior pass.
- All Judge output MUST be valid JSON matching the defined schemas.

---

## 8. Alternatives Considered

| Alternative | Reason Rejected |
|-------------|----------------|
| Judge with internet access | Requirement explicitly forbids it |
| Single monolithic Judge function | Makes skills untestable in isolation; violates SRP |
| Scoring only at the final round | Round-by-round scoring provides richer justification and is more fair |
| Allowing ties | Requirement explicitly forbids ties |

---

## 9. Success Criteria

- [x] Judge reprimands an argument that contains "I agree with your point".
- [x] Judge reprimands an argument with an empty citations list.
- [x] Judge reprimands a round 2+ argument that ignores an obvious logical fallacy.
- [x] Judge advances the round for a valid argument with citations, direct rebuttal, and fallacy identification.
- [x] `EvaluatePersuasionScore` produces three sub-scores (logical, citation, rhetoric) summing correctly.
- [x] `DeclareVerdict` produces a verdict with two different integer scores and a named winner.
- [x] `DeclareVerdict` never produces equal scores (tie-breaker always fires when needed).
- [x] Verdict justification is comprehensive and multi-paragraph with four sections: KEY CLASHES, FEEDBACK ADHERENCE, SCORING BREAKDOWN, FINAL CONCLUSION.
- [x] Verdict justification references per-round score averages for both agents across all three dimensions.
- [x] Judge process raises `ToolNotAvailableError` if web search is attempted.

---

## 10. Test Scenarios

| Scenario | Expected Outcome |
|----------|-----------------|
| Argument contains "you make a good point" | `reprimand` message returned |
| Argument has empty `citations` | `reprimand` message returned |
| Round 2+ argument ignores a clear strawman in opponent's prior argument | `reprimand` message returned |
| Argument has 2 citations, names a fallacy, direct rebuttal, rhetoric applied | `routing` message returned |
| `EvaluatePersuasionScore` receives argument with strong rhetoric | `rhetoric_quality` score > 0.7 |
| `EvaluatePersuasionScore` receives argument with no rhetorical techniques | `rhetoric_quality` score < 0.4 |
| 10 rounds completed, Pro scored higher on all 3 dimensions | Verdict names Pro as winner |
| Both agents score identically across rounds | Tie-breaker fires; one agent wins |
| Verdict justification references scores | Justification string contains SCORING BREAKDOWN section with per-agent averages per dimension |
| Verdict justification references "feedback" | Justification string contains FEEDBACK ADHERENCE section with early-vs-late trend analysis |
| Verdict justification references "FINAL CONCLUSION" | Justification string contains FINAL CONCLUSION section naming winner and primary winning dimension |
| `DeclareVerdict` called before any rounds | Raises `InsufficientDataError` |
