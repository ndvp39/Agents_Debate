# PRD — Debater Skills
**Version:** 2.00
**Date:** 2026-05-29
**Author:** Nadav Goldin
**Skills root:** `src/debate/skills/` · **Loader:** `src/debate/skills/loader.py`

> **Implementation change (commit `ac3d46b`, finalized in `52b5134`):** skills are
> no longer Python classes living in `src/debate/agents/debaters/skills.py` and
> `src/debate/agents/judge/skills.py` — those modules have been **deleted**. They
> were replaced by **Anthropic SKILL.md files** discovered at runtime by
> `SkillLoader`. This PRD documents the new model. The original v1 PRD described
> a `register_skill()` registry that no longer exists.

---

## 1. Description & Theoretical Background

Debater skills are discrete, composable reasoning capabilities that transform a
raw LLM call into a structured, expert-level debate turn. Each skill encapsulates
one cognitive task that a world-class human debater performs implicitly.

The skill pipeline is inspired by **Chain-of-Thought (CoT) prompting** and
**debate theory**: professional debaters do not simply respond — they first
analyze, identify weaknesses, choose a strategy, gather evidence, apply rhetoric,
and then speak. The skills make this process explicit and testable.

Skills follow the **Anthropic Skill protocol**: each is a folder under
`src/debate/skills/` containing a `SKILL.md` with YAML frontmatter and a prose
body. Two `type` values are supported:

- **`llm_prompt`** — the body is a prompt template with `{{ var }}` placeholders.
  `Skill.render(**kwargs)` substitutes placeholders by string replacement and
  returns the rendered prompt.
- **`deterministic`** — the body is a prose description of rules; a sibling
  `script.py` exports a `run(...)` function that the loader binds to the Skill
  instance. `Skill.run(*args, **kwargs)` invokes that function.

`SkillLoader` is constructed with a skills-root path (`src/debate/skills/`),
discovers SKILL.md files lazily via `rglob`, parses frontmatter with `yaml`, and
caches Skill instances by name. Calling `.run()` on an `llm_prompt` skill or
`.render()` on a `deterministic` skill raises `SkillTypeMismatchError`.

---

## 2. Skill Pipeline (execution order per turn)

```
Round 1 only:           craft_opening              (llm_prompt)
                             │
                       synthesize_evidence         (deterministic)
                             │
                       apply_rhetoric              (llm_prompt)
                             │
                       Final argument message


Round 2+:               analyze_opponent           (llm_prompt)
                             │
                       detect_fallacies            (llm_prompt)
                             │
                       adapt_strategy              (deterministic)
                             │
                       build_counter_argument     (llm_prompt)
                             │
                       synthesize_evidence         (deterministic)
                             │
                       apply_rhetoric              (llm_prompt)
                             │
                       Final argument message
```

The pipeline lives in `BaseDebater._run_pipeline()`. The agent's
`_wrapped_llm()` prepends the anti-sycophancy directive before every LLM call.

---

## 3. Skill Definitions (debater pipeline)

Each entry below describes one SKILL.md folder. The `inputs` are the YAML keys
the agent passes to `render(...)` or `run(...)`; the prompt body for
`llm_prompt` skills is verbatim under `## Instructions` in the corresponding
`SKILL.md`.

### Skill 1: `craft_opening` (llm_prompt)

**When:** Round 1 only.
**Folder:** `src/debate/skills/debater/craft_opening/SKILL.md`

**Inputs:** `topic`, `stance`.

**Body (excerpt from `## Instructions`):**
> "Topic: {{ topic }}\nStance: {{ stance }}\nDeliver the strongest possible opening
> statement. State your position boldly, preview your three strongest arguments,
> and end with a memorable hook. Do NOT acknowledge the opposing side yet."

**Round-1 guard:** the agent's `_run_pipeline` only invokes this skill when
`round_number == 1` (no `SkillNotApplicableError` is raised — the guard moved
into the agent).

---

### Skill 2: `analyze_opponent` (llm_prompt)

**When:** Round 2+.
**Folder:** `src/debate/skills/debater/analyze_opponent/SKILL.md`

**Inputs:** `opponent_argument` (sourced from the routing message's
`previous_argument` field — see §3.2 of the IPC PRD).

**Output contract (consumed by the agent):** a JSON object with keys
`main_claim`, `supporting_points`, `assumptions`, `weakest_point`. If the
LLM returns prose, `BaseDebater._coerce_analysis` treats the entire text as
both `main_claim` and `weakest_point`.

---

### Skill 3: `detect_fallacies` (llm_prompt)

**When:** Round 2+.
**Folder:** `src/debate/skills/debater/detect_fallacies/SKILL.md`

**Inputs:** `opponent_argument`, `analysis` (output of `analyze_opponent`).

**Output contract:** JSON `{fallacies_found, fallacy_descriptions}`, or a single
prose blob the agent coerces.

---

### Skill 4: `adapt_strategy` (deterministic)

**When:** Round 2+.
**Folder:** `src/debate/skills/debater/adapt_strategy/{SKILL.md, script.py}`

Pure if/else: if `own_score < opp_score` → `defensive`; `>` → `offensive`;
`==` → `pivot`. The `target` is `analysis["weakest_point"]` (or the literal
string `"opponent's main claim"` when absent). Emits
`{mode, target, rationale}`.

---

### Skill 5: `build_counter_argument` (llm_prompt)

**When:** Round 2+.
**Folder:** `src/debate/skills/debater/build_counter_argument/SKILL.md`

**Inputs:** `stance`, `topic`, `target`, `judge_feedback_block` (a
pre-formatted string the agent assembles, empty when no judge feedback).

The body demands at least one specific statistic, study name, or expert
opinion. When `judge_feedback_block` is non-empty, the argument must explicitly
adapt to the judge's directive.

---

### Skill 6: `synthesize_evidence` (deterministic)

**When:** Every round.
**Folder:** `src/debate/skills/debater/synthesize_evidence/{SKILL.md, script.py}`

**Inputs:** `argument_draft`, `raw_search_results`. Returns `{citations,
enriched_argument}` — the first `MAX_CITATIONS = 3` entries appended as a
`"\n\nSources: " + "; ".join(citations)` block, or the draft unchanged when
the list is empty.

---

### Skill 7: `apply_rhetoric` (llm_prompt)

**When:** Every round (last skill before sending).
**Folder:** `src/debate/skills/debater/apply_rhetoric/SKILL.md`

**Inputs:** `round_number`, `stance`, `enriched_argument`,
`judge_mandate_block` (optional pre-formatted mandate from judge feedback).

The body instructs the model to refine with ethos, pathos, logos, analogy, and
a memorable closing — preserving factual content and the `Sources:` line.

---

## 4. Judge skills (cross-reference)

The judge has its own 4 SKILL.md folders under `src/debate/skills/judge/`,
documented in detail in `PRD_judge_agent.md`. Listed here for completeness:

| Skill | Type | Purpose |
|---|---|---|
| `enforce_debate_mechanics` | deterministic | Gate incoming arguments; emit `ReprimandMessage` on rule violation |
| `evaluate_persuasion_score` | llm_prompt | Score the argument on three dimensions; returns a JSON object |
| `generate_judge_feedback` | llm_prompt | 2-3 sentences of round-specific feedback for the next agent |
| `compose_next_turn_prompt` | deterministic | Build the literal `prompt_for_next` handoff string (no LLM call) |

`RouteTurn` from the original PRD was split into the last two skills in commit
`651a5a8` once it became clear the handoff-string composition is not an LLM
task.

---

## 5. SkillLoader Contract

```python
from debate.skills.loader import SkillLoader

loader = SkillLoader(Path("src/debate/skills"))
skill = loader.load("craft_opening")          # discovers via rglob

# llm_prompt — render the template
prompt = skill.render(topic="...", stance="...")

# deterministic — invoke the bound run()
out = loader.load("synthesize_evidence").run(draft, raw_results)
```

Errors: `FileNotFoundError` (missing skill or missing script.py), `ValueError`
(missing/malformed frontmatter), `SkillTypeMismatchError` (`.render` on a
deterministic skill or `.run` on an LLM-prompt skill).

---

## 6. Constraints

- Skills MUST live under `src/debate/skills/` as folders containing `SKILL.md`
  (and, for deterministic skills, a sibling `script.py`).
- Skills MUST NOT make direct API calls — the LLM call happens in
  `BaseDebater._wrapped_llm()` (debater) or in the LLM closures
  (`make_*_llm`), all routed through `ApiGatekeeper`.
- `craft_opening` MUST only run in round 1 (the agent guards this — there is no
  longer a `SkillNotApplicableError`).
- `apply_rhetoric` MUST be the last skill in the pipeline.
- The anti-sycophancy directive (`_ANTI_SYCOPHANCY` in `base_debater.py`)
  wraps every LLM call via `_wrapped_llm`.
- LLM-prompt skill bodies use `{{ var }}` placeholders. Unmatched placeholders
  are preserved literally so the agent can spot omissions.

---

## 7. Alternatives Considered (history)

| Alternative | Reason Rejected |
|---|---|
| Single monolithic "respond" method | Not testable in isolation; no visibility into reasoning steps |
| Skills as separate LLM calls each (full Chain-of-Thought) | Too many API calls per turn; expensive and slow |
| No skills — pure prompt engineering | Harder to debug, tune, and test each reasoning step |
| **Python `register_skill()` registry (original implementation)** | Lecturer required the **Anthropic Skill protocol**: SKILL.md + YAML frontmatter, loaded at runtime. Documented here for historical context. Removed in `52b5134`. |

---

## 8. Success Criteria

- [x] `SkillLoader` discovers every SKILL.md under `src/debate/skills/` and parses YAML frontmatter without error.
- [x] `analyze_opponent` correctly identifies the main claim from a sample argument.
- [x] `detect_fallacies` identifies a "Strawman" in a crafted test argument.
- [x] `adapt_strategy.run()` returns `"offensive"` when `own_score > opp_score`, `"defensive"` when `<`, `"pivot"` when equal.
- [x] `synthesize_evidence.run()` returns ≤ 3 citations from a list of N raw results.
- [x] `apply_rhetoric` rendered prompt instructs the LLM to preserve factual content.
- [x] Full pipeline produces a valid `ArgumentMessage` with `citations` populated.
- [x] `Skill.render()` on a deterministic skill raises `SkillTypeMismatchError`; `Skill.run()` on an LLM-prompt skill likewise.

---

## 9. Test Scenarios

| Scenario | Expected Outcome |
|---|---|
| `analyze_opponent` given a strawman argument | `weakest_point` identifies the misrepresentation |
| `detect_fallacies` on argument with "slippery slope" | `fallacies_found` contains "Slippery Slope" |
| `adapt_strategy` round=8, own_score=0.4, opp_score=0.7 | `mode == "defensive"` |
| `synthesize_evidence` with 0 raw results | Returns empty citations; `enriched_argument` == original draft |
| Full pipeline on round 1 | `craft_opening` runs; `analyze_opponent`/`detect_fallacies` skipped; valid output |
| Full pipeline on round 5 | round-2+ branch runs in order; valid output |
| `SkillLoader.load("does_not_exist")` | Raises `FileNotFoundError` |
| Deterministic skill missing `script.py` | Raises `FileNotFoundError` with `"script.py"` in message |
| Malformed YAML frontmatter | Raises `ValueError` |
