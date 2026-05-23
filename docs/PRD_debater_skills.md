# PRD — Debater Skills
**Version:** 1.00  
**Date:** 2026-05-23  
**Author:** Nadav Goldin  
**File:** `src/debate/agents/debaters/skills.py`

---

## 1. Description & Theoretical Background

Debater skills are discrete, composable reasoning capabilities that transform a raw LLM call into a structured, expert-level debate turn. Each skill encapsulates one cognitive task that a world-class human debater performs implicitly.

The skill pipeline is inspired by **Chain-of-Thought (CoT) prompting** and **debate theory**: professional debaters do not simply respond — they first analyze, identify weaknesses, choose a strategy, gather evidence, apply rhetoric, and then speak. The skills make this process explicit and testable.

Skills are defined **locally** within the debaters package. They are registered in the `BaseDebater` skill registry and called in sequence each turn. Skills are independently testable — each takes a well-defined input dict and returns a well-defined output dict.

---

## 2. Skill Pipeline (execution order per turn)

```
Round 1 only:           CraftOpening
                             │
Every round:        AnalyzeOpponent
                             │
                       DetectFallacies
                             │
                       AdaptStrategy
                             │
                   BuildCounterArgument
                             │
                    SynthesizeEvidence
                             │
                       ApplyRhetoric
                             │
                   ─────────────────────
                   Final argument message
```

---

## 3. Skill Definitions

### Skill 1: `CraftOpening`

**When:** Round 1 only (before any opponent argument exists).

**Purpose:** Establish the strongest possible initial case for the assigned stance.

**Input:**
```python
{"topic": str, "stance": str}
```

**Output:**
```python
{"opening_statement": str}  # 150–300 words; bold claim + 3 supporting pillars
```

**Prompt instruction injected:**
> "You are opening this debate. Deliver the strongest possible opening statement for your stance. State your position boldly, preview your three strongest arguments, and end with a memorable hook. Do NOT acknowledge the opposing side yet."

---

### Skill 2: `AnalyzeOpponent`

**When:** Every round except round 1.

**Purpose:** Systematically deconstruct the opponent's last argument to expose its structure and vulnerabilities.

**Input:**
```python
{"opponent_argument": str}
```

**Output:**
```python
{
    "main_claim": str,         # The opponent's core assertion
    "supporting_points": list[str],  # Evidence/sub-claims they used
    "assumptions": list[str],  # Unstated premises they rely on
    "weakest_point": str       # The single most vulnerable claim
}
```

**Prompt instruction injected:**
> "Analyze the opponent's argument. Identify: (1) their main claim, (2) their supporting points, (3) hidden assumptions they rely on, (4) their single weakest point. Be precise and clinical."

---

### Skill 3: `DetectFallacies`

**When:** Every round except round 1.

**Purpose:** Explicitly name logical fallacies present in the opponent's argument to discredit their reasoning.

**Input:**
```python
{"opponent_argument": str, "analysis": dict}  # analysis from AnalyzeOpponent
```

**Output:**
```python
{
    "fallacies_found": list[str],  # Named fallacies (e.g., "Strawman", "False Dichotomy")
    "fallacy_descriptions": list[str]  # Brief explanation of each fallacy as it appears
}
```

**Fallacies to detect:** Strawman, Ad Hominem, Slippery Slope, False Dichotomy, Hasty Generalization, Appeal to Authority, Post Hoc, Circular Reasoning, Red Herring, Appeal to Emotion.

**Prompt instruction injected:**
> "Identify any logical fallacies in the opponent's argument. For each fallacy, name it and explain exactly how it appears in their argument. If none exist, state 'No fallacies detected.'"

---

### Skill 4: `AdaptStrategy`

**When:** Every round except round 1.

**Purpose:** Decide the optimal debate strategy for this turn based on the debate trajectory.

**Input:**
```python
{
    "round_number": int,
    "own_cumulative_score": float,   # from Judge's routing feedback
    "analysis": dict,                # from AnalyzeOpponent
    "fallacies": dict                # from DetectFallacies
}
```

**Output:**
```python
{
    "mode": str,           # "offensive" | "defensive" | "pivot"
    "target": str,         # Which opponent claim to focus on
    "rationale": str       # Brief explanation of strategy choice
}
```

**Modes:**
- `offensive` — attack the opponent's weakest point; use when ahead or tied.
- `defensive` — reinforce own strongest argument under attack; use when behind.
- `pivot` — introduce a new angle to shift debate territory; use when stuck.

---

### Skill 5: `BuildCounterArgument`

**When:** Every round except round 1.

**Purpose:** Construct a targeted, logically airtight rebuttal based on the analysis, fallacies, and strategy.

**Input:**
```python
{
    "stance": str,
    "topic": str,
    "analysis": dict,
    "fallacies": dict,
    "strategy": dict,
    "citations": list[str]   # from SynthesizeEvidence (may be empty at this point)
}
```

**Output:**
```python
{"counter_argument": str}  # 200–400 words; direct, aggressive, evidence-ready
```

**Prompt instruction injected:**
> "Construct a devastating counter-argument. Directly address the opponent's weakest point ('{target}'). Call out any fallacies by name. Support every claim with a placeholder for evidence. Never agree. Never soften your position."

---

### Skill 6: `SynthesizeEvidence`

**When:** Every round (including round 1).

**Purpose:** Select, frame, and weave only the strongest citations into the argument.

**Input:**
```python
{
    "argument_draft": str,
    "raw_search_results": list[str]   # from WebSearchTool
}
```

**Output:**
```python
{
    "citations": list[str],           # 1–3 strongest, formatted citations
    "enriched_argument": str          # argument_draft with citations integrated
}
```

**Selection criteria (in order):** peer-reviewed sources > government/institutional data > reputable journalism > expert quotes > general sources.

---

### Skill 7: `ApplyRhetoric`

**When:** Every round (final skill before sending).

**Purpose:** Elevate the argument with classical rhetorical techniques to maximize persuasive impact.

**Input:**
```python
{"enriched_argument": str, "stance": str, "round_number": int}
```

**Output:**
```python
{"final_argument": str}  # Rhetorically enhanced version
```

**Techniques applied:**
- **Ethos** — establish credibility ("Experts at MIT confirm…")
- **Pathos** — targeted emotional resonance appropriate to the topic
- **Logos** — explicit logical chain ("If A, then B; B is proven by X; therefore A")
- **Anaphora** — repetition for emphasis when appropriate
- **Analogy** — clarify complex points with relatable comparisons
- **Reductio ad absurdum** — push opponent's logic to its extreme to show its absurdity

**Prompt instruction injected:**
> "Refine this argument using classical rhetorical techniques. Apply ethos, pathos, and logos. Add one analogy and one memorable closing statement. Do NOT change the factual content or citations."

---

## 4. Input / Output Summary

| Skill | Input | Output |
|-------|-------|--------|
| `CraftOpening` | topic, stance | opening_statement |
| `AnalyzeOpponent` | opponent_argument | main_claim, supporting_points, assumptions, weakest_point |
| `DetectFallacies` | opponent_argument, analysis | fallacies_found, fallacy_descriptions |
| `AdaptStrategy` | round, scores, analysis, fallacies | mode, target, rationale |
| `BuildCounterArgument` | stance, topic, analysis, fallacies, strategy, citations | counter_argument |
| `SynthesizeEvidence` | argument_draft, raw_search_results | citations, enriched_argument |
| `ApplyRhetoric` | enriched_argument, stance, round | final_argument |

---

## 5. Performance Requirements

| Metric | Target |
|--------|--------|
| Total pipeline execution time (all 7 skills) | < 90 seconds per turn |
| LLM calls per turn | ≤ 4 (skills may share a single LLM call where logical) |
| Web search calls per turn | ≤ 3 (for SynthesizeEvidence) |
| All calls via ApiGatekeeper | Mandatory — 0 exceptions |

---

## 6. Constraints

- Skills MUST be defined locally in `agents/debaters/skills.py` — not globally.
- Each skill is independently callable and testable (no hidden side effects).
- Skills MUST NOT make direct API calls — they build prompts and return structured dicts; `BaseDebater` executes LLM calls via `ApiGatekeeper`.
- `CraftOpening` MUST only run in round 1.
- `ApplyRhetoric` MUST be the last skill in the pipeline.
- The anti-sycophancy directive from `BaseDebater._build_prompt()` wraps ALL skill outputs.

---

## 7. Alternatives Considered

| Alternative | Reason Rejected |
|-------------|----------------|
| Single monolithic "respond" method | Not testable in isolation; no visibility into reasoning steps |
| Skills as separate LLM calls each | Too many API calls per turn; expensive and slow |
| No skills — pure prompt engineering | Harder to debug, tune, and test each reasoning step |
| Global skill library | Requirement: skills must be defined locally |

---

## 8. Success Criteria

- [x] `AnalyzeOpponent` correctly identifies the main claim from a sample argument.
- [x] `DetectFallacies` identifies a "Strawman" in a crafted test argument.
- [x] `AdaptStrategy` returns `"offensive"` when own score > opponent score.
- [x] `AdaptStrategy` returns `"defensive"` when own score < opponent score.
- [x] `SynthesizeEvidence` returns 1–3 citations from a list of 5 raw results.
- [x] `ApplyRhetoric` output contains the original factual content.
- [x] `CraftOpening` only fires on round 1 (raises `SkillNotApplicableError` on other rounds).
- [x] Full pipeline produces a valid `argument` JSON message with ≥ 1 citation.

---

## 9. Test Scenarios

| Scenario | Expected Outcome |
|----------|-----------------|
| `AnalyzeOpponent` given a strawman argument | `weakest_point` identifies the misrepresentation |
| `DetectFallacies` on argument with "slippery slope" | `fallacies_found` contains "Slippery Slope" |
| `AdaptStrategy` round=8, own_score=0.4, opp_score=0.7 | `mode = "defensive"` |
| `SynthesizeEvidence` with 0 raw results | Returns empty citations; `enriched_argument` = original draft |
| `CraftOpening` called on round 3 | Raises `SkillNotApplicableError` |
| Full pipeline on round 1 | `CraftOpening` runs; `AnalyzeOpponent` skipped; valid output |
| Full pipeline on round 5 | `CraftOpening` skipped; all other 6 skills run in order |
