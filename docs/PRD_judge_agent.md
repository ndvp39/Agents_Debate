# PRD — Judge Agent
**Version:** 1.00  
**Date:** 2026-05-23  
**Files:** `src/debate/agents/judge/judge_agent.py`, `src/debate/agents/judge/skills.py`

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
4. If all checks pass → pass the argument to `RouteTurn`.

**Output:** Either a `reprimand` JSON message or calls `RouteTurn`.

---

### Skill 2: `RouteTurn`

**Trigger:** Called by `EnforceDebateMechanics` after a valid argument.

**Logic:**
1. Summarize the core point just made (1–2 sentences).
2. Update the `EvaluatePersuasionScore` for the current speaker.
3. Determine the next target agent (flip Pro ↔ Con).
4. Construct a `routing` JSON message with `judge_feedback` and `prompt_for_next`.
5. Send the message.

**Output:** A `routing` JSON message.

---

### Skill 3: `EvaluatePersuasionScore`

**Trigger:** Called internally by `RouteTurn` after each valid argument.

**Logic:**
Scores two sub-dimensions per round:
- `logical_consistency` (0.0–1.0): Does the argument follow logically from its premises?
- `citation_strength` (0.0–1.0): Are citations credible, specific, and relevant?

Cumulative score updated as:
```
cumulative_score = 0.6 * avg(logical_consistency) + 0.4 * avg(citation_strength)
```

Scores are stored internally and used by `DeclareVerdict`.

**Output:** Updated `PersuasionScore` dataclass for the speaking agent.

---

### Skill 4: `DeclareVerdict`

**Trigger:** Called by the orchestrator after the final round is complete.

**Logic:**
1. Compute final cumulative scores for both agents.
2. If scores are equal (tie scenario): add a 0.01 tie-breaker to the agent with more consistent citation strength across rounds.
3. Identify the winner (higher cumulative score).
4. Construct a `verdict` JSON message with winner, integer percentage scores, and detailed justification (min 50 characters referencing specific rounds).

**Output:** A `verdict` JSON message. Ties are forbidden — the tie-breaker guarantees a winner.

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

- [ ] Judge reprimands an argument that contains "I agree with your point".
- [ ] Judge reprimands an argument with an empty citations list.
- [ ] Judge advances the round for a valid argument with citations and direct rebuttal.
- [ ] `DeclareVerdict` produces a verdict with two different integer scores and a named winner.
- [ ] `DeclareVerdict` never produces equal scores (tie-breaker always fires when needed).
- [ ] Judge process raises `ToolNotAvailableError` if web search is attempted.

---

## 10. Test Scenarios

| Scenario | Expected Outcome |
|----------|-----------------|
| Argument contains "you make a good point" | `reprimand` message returned |
| Argument has empty `citations` | `reprimand` message returned |
| Argument has 2 citations and direct rebuttal | `routing` message returned |
| 10 rounds completed, Pro scored higher | Verdict names Pro as winner |
| Both agents score identically across rounds | Tie-breaker fires; one agent wins |
| `DeclareVerdict` called before any rounds | Raises `InsufficientDataError` |
