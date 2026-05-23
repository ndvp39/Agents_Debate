# Prompts Book — AI Agent Debate System

**Author:** Nadav Goldin  
**Version:** 1.00  
**Date:** 2026-05-23

---

## Introduction

This document is the authoritative reference for every prompt template used in the AI Agent Debate System. It covers all three agent types — **Pro Debater**, **Con Debater**, and **Judge** — each of which operates through a structured skill pipeline rather than a monolithic prompt. The pipeline design means that context is built incrementally: each skill consumes the outputs of prior skills and passes enriched data forward, giving the final LLM call far more targeted information than a single open-ended prompt ever could.

### Agent Architecture Overview

| Agent | Role | Pipeline |
|-------|------|----------|
| Pro Debater | Argues in favour of the topic | 7-skill pipeline (CraftOpening / AnalyzeOpponent → DetectFallacies → AdaptStrategy → BuildCounterArgument → SynthesizeEvidence → ApplyRhetoric) |
| Con Debater | Argues against the topic | Same 7-skill pipeline, opposite stance |
| Judge | Enforces rules, scores arguments, routes turns, declares winner | 4-skill pipeline (EnforceDebateMechanics → EvaluatePersuasionScore → RouteTurn → DeclareVerdict) |

All debater LLM calls are intercepted by a `_wrapped_llm()` wrapper that prepends the anti-sycophancy directive documented in Section 1. Judge scoring uses a separate structured evaluate prompt documented in Section 4.

---

## Section 1 — Anti-Sycophancy System Directive

### Location

`src/debate/agents/debaters/base_debater.py` — module-level constant `_ANTI_SYCOPHANCY`, applied inside `_wrapped_llm()`.

### Template

```
CRITICAL DIRECTIVE: You are arguing {stance} on "{topic}".
You MUST NEVER agree with, compliment, or validate the opposing argument.
Phrases like 'good point', 'I agree', 'you're right' are STRICTLY FORBIDDEN.
Your only goal is to WIN this debate for your side.
```

**Runtime inputs:**

| Placeholder | Source |
|-------------|--------|
| `{stance}` | `BaseDebater.STANCE` class attribute (`"PRO"` or `"CON"`) |
| `{topic}` | Constructor argument, stored as `self._topic` |

### How It Is Applied

Every debater LLM call goes through `_wrapped_llm()` rather than the raw `_llm_call` callable directly:

```python
def _wrapped_llm(self, prompt: str) -> Any:
    directive = _ANTI_SYCOPHANCY.format(stance=self.STANCE, topic=self._topic)
    return self._llm_call(f"{directive}\n\n{prompt}")
```

The directive is physically prepended to the prompt string before it is sent to the API. This means every single skill prompt — CraftOpening, AnalyzeOpponent, DetectFallacies, BuildCounterArgument, and ApplyRhetoric — automatically inherits the anti-sycophancy constraint without each skill author having to remember to include it.

### Behaviour It Prevents

Large language models exhibit a well-documented tendency towards **sycophantic capitulation**: when presented with an opposing argument, they frequently soften their position, acknowledge merit in the other side, and drift toward consensus. In a debate system this is catastrophic — a debater that concedes ground mid-round undermines the adversarial structure that makes the debate meaningful. The directive addresses this at three levels:

1. **Identity anchoring** — "You are arguing {stance}" re-establishes role before any other instruction.
2. **Explicit prohibition** — Lists the exact surface forms that signal capitulation (`good point`, `I agree`, `you're right`).
3. **Goal framing** — "Your only goal is to WIN" overrides any cooperative instinct baked into the base model's RLHF.

The Judge's `EnforceDebateMechanics` skill provides a complementary runtime check: it scans the submitted argument text for the same sycophantic phrases and issues a `ReprimandMessage` if any are detected, forcing a rewrite.

---

## Section 2 — Debater Skills (7-Skill Pipeline)

The pipeline runs in two modes depending on round number:

- **Round 1:** CraftOpening → SynthesizeEvidence → ApplyRhetoric
- **Round 2+:** AnalyzeOpponent → DetectFallacies → AdaptStrategy → BuildCounterArgument → SynthesizeEvidence → ApplyRhetoric

All prompts in this section are passed through `_wrapped_llm()`, so the anti-sycophancy directive (Section 1) is always prepended at the API boundary.

---

### Skill 1 — CraftOpening

**Source:** `src/debate/agents/debaters/skills.py`, class `CraftOpening`

**Purpose:** Generate the debater's opening statement in Round 1. Establishes the stance boldly, previews the three strongest arguments, and sets a rhetorical hook to prime the audience. This skill only runs on `round_number == 1`; calling it on any other round raises `SkillNotApplicableError`.

#### Prompt Template

```
Topic: {topic}
Stance: {stance}
Deliver the strongest possible opening statement. State your position boldly,
preview your three strongest arguments, and end with a memorable hook.
Do NOT acknowledge the opposing side yet.
```

**Inputs:**

| Placeholder | Source |
|-------------|--------|
| `{topic}` | Passed from `BaseDebater._topic` |
| `{stance}` | Passed from `BaseDebater.STANCE` |

**Output:** `{"opening_statement": <str>}` — fed directly into `SynthesizeEvidence`.

#### Rationale and Design Decisions

- **"three strongest arguments"** — Forcing enumeration prevents rambling and produces a structured argument body that subsequent skills can target.
- **"end with a memorable hook"** — Rhetoric research shows that first and last impressions anchor audience memory; the hook cues `ApplyRhetoric` on what tone to sustain.
- **"Do NOT acknowledge the opposing side yet"** — On Round 1 the opponent has not spoken; acknowledging a non-existent position would look evasive. This clause prevents hallucinated concessions.

---

### Skill 2 — AnalyzeOpponent

**Source:** `src/debate/agents/debaters/skills.py`, class `AnalyzeOpponent`

**Purpose:** Deconstruct the opponent's last argument to expose its logical structure and identify the weakest claim. The output drives both fallacy detection and the targeted web-search query used in BuildCounterArgument.

#### Prompt Template

```
Analyze this argument:
{opponent_argument}
Identify: (1) main claim, (2) supporting points, (3) hidden assumptions, (4) weakest point.
```

**Inputs:**

| Placeholder | Source |
|-------------|--------|
| `{opponent_argument}` | `BaseDebater._last_opponent_arg`, set from the incoming routing message's `prompt_for_next` field |

**Output (expected dict):**
```json
{
  "main_claim": "<str>",
  "supporting_points": ["<str>", ...],
  "assumptions": ["<str>", ...],
  "weakest_point": "<str>"
}
```

If the LLM returns a plain string instead of JSON, the skill falls back gracefully: it stores the entire response as `main_claim` and `weakest_point` with empty lists for the array fields.

#### Rationale and Design Decisions

- **Four-part numbered structure** — Each number maps to a downstream consumer: `main_claim` goes to the counter-argument target; `supporting_points` informs which flanks to attack; `assumptions` expose implicit premises that can be challenged without arguing the stated facts; `weakest_point` drives the targeted web search (see context engineering improvement in Section 5).
- **Plain-string fallback** — Real LLM responses are not always valid JSON. Defensive parsing keeps the pipeline alive without requiring perfect structured output.

---

### Skill 3 — DetectFallacies

**Source:** `src/debate/agents/debaters/skills.py`, class `DetectFallacies`

**Purpose:** Explicitly name any logical fallacies present in the opponent's argument. Named fallacies can be quoted by name in the counter-argument, which is rhetorically powerful and also satisfies the Judge's `fallacy_ignored` rule check.

#### Prompt Template

```
Find logical fallacies in:
{opponent_argument}
Name each fallacy and explain how it appears. If none, state 'No fallacies detected.'
```

**Inputs:**

| Placeholder | Source |
|-------------|--------|
| `{opponent_argument}` | `BaseDebater._last_opponent_arg` (same source as AnalyzeOpponent) |

The `analysis` dict from `AnalyzeOpponent` is also passed as a parameter but is not currently interpolated into the prompt text; it is available for future skill extensions that want to cross-reference the structural analysis with the fallacy scan.

**Output (expected dict):**
```json
{
  "fallacies_found": ["<fallacy name>", ...],
  "fallacy_descriptions": ["<explanation>", ...]
}
```

If the LLM returns plain text, the skill wraps it as `{"fallacies_found": [], "fallacy_descriptions": [<text>]}`.

#### Rationale and Design Decisions

- **"Name each fallacy"** — Vague descriptions like "this is bad logic" score poorly with the Judge's `logical_consistency` dimension. Named fallacies (ad hominem, straw man, false dichotomy) demonstrate analytical rigour.
- **"If none, state 'No fallacies detected.'"** — Prevents the LLM from inventing fallacies. The Judge penalises `fallacy_ignored == True` only from Round 2 onwards, so false positives in Round 1 can cascade into a spurious reprimand.

---

### Skill 4 — AdaptStrategy

**Source:** `src/debate/agents/debaters/skills.py`, class `AdaptStrategy`

**Purpose:** Choose the optimal debate mode — offensive, defensive, or pivot — based on the current score differential. This skill is **fully deterministic** and makes **no LLM call**.

#### Logic (No Prompt)

```python
if own_score < opp_score:
    mode = "defensive"
elif own_score > opp_score:
    mode = "offensive"
else:
    mode = "pivot"

target = analysis.get("weakest_point", "opponent's main claim")
```

**Output:**
```json
{
  "mode": "<defensive|offensive|pivot>",
  "target": "<str>",
  "rationale": "Round N: <mode> chosen (own=X.XX, opp=Y.YY)."
}
```

#### Rationale and Design Decisions

- **Deterministic by design** — Strategy selection must be stable and auditable. Allowing an LLM to choose its own strategy creates an uncontrolled variable that could override the Judge's scoring signal with hallucinated reasoning about its competitive position.
- **Score inputs are placeholders at 0.5/0.5** — In the current implementation `own_score` and `opp_score` are both passed as `0.5` from `_run_pipeline`, meaning the strategy always resolves to `"pivot"`. This is intentional scaffolding: the architecture is wired to receive real scores when the Judge-to-Debater feedback loop is extended to carry numeric values alongside textual feedback.
- **`target` from `weakest_point`** — Passing the target forward ensures `BuildCounterArgument` attacks the same point that `AnalyzeOpponent` identified as most vulnerable.

---

### Skill 5 — BuildCounterArgument

**Source:** `src/debate/agents/debaters/skills.py`, class `BuildCounterArgument`

**Purpose:** Construct a logically airtight rebuttal that attacks the opponent's weakest point, calls out named fallacies, and cites at least one specific piece of evidence. This is the argumentative core of rounds 2+.

#### Prompt Template

```
Stance: {stance}
Topic: {topic}
Target: {target}
Construct a devastating counter-argument. Directly address the weakest point.
Call out any fallacies by name. Never agree or soften your position.
You MUST explicitly quote at least one specific statistic, study name, or expert opinion.
```

When `judge_feedback` is non-empty, the following block is appended:

```

JUDGE'S FEEDBACK (MANDATORY): {judge_feedback}
You MUST directly adapt your argument to address this feedback.
If the Judge asked for specific data, statistics, or citations, you MUST provide them NOW.
```

**Inputs:**

| Placeholder | Source |
|-------------|--------|
| `{stance}` | `BaseDebater.STANCE` |
| `{topic}` | `BaseDebater._topic` |
| `{target}` | `strategy["target"]` (from AdaptStrategy) |
| `{judge_feedback}` | `routing_message["judge_feedback"]` — the Judge's textual feedback from the previous round |

**Output:** `{"counter_argument": <str>}` — passed into `SynthesizeEvidence`.

#### Rationale and Design Decisions

- **"devastating counter-argument"** — Loaded language is intentional. It combats the LLM's tendency to produce balanced analysis when the desired output is one-sided advocacy.
- **"Call out any fallacies by name"** — Bridges the `DetectFallacies` output into the argument without requiring another LLM call; the debater is instructed to use the names it already identified.
- **"MUST explicitly quote at least one specific statistic"** — Forces citation behaviour even when the web search returns no results. The Judge's `citation_strength` score dimension heavily penalises uncited arguments.
- **`judge_feedback` block (context engineering)** — See Section 5 for full analysis. The `MANDATORY` label and the directive to provide data "NOW" are deliberate urgency signals. Without them, tests showed the LLM acknowledging the feedback but not acting on it.

---

### Skill 6 — SynthesizeEvidence

**Source:** `src/debate/agents/debaters/skills.py`, class `SynthesizeEvidence`

**Purpose:** Select up to three citations from the web-search results and physically append them to the argument draft. This skill is **fully deterministic** — it performs string concatenation only, with no LLM call.

#### Logic (No Prompt)

```python
MAX_CITATIONS = 3
citations = list(raw_search_results)[:MAX_CITATIONS]
if citations:
    sources_line = "\n\nSources: " + "; ".join(citations)
    enriched = argument_draft + sources_line
else:
    enriched = argument_draft
```

**Output:**
```json
{
  "citations": ["<url or title>", ...],
  "enriched_argument": "<argument text>\n\nSources: ..."
}
```

#### Rationale and Design Decisions

- **Deterministic evidence injection** — If evidence weaving were delegated to an LLM, it might paraphrase, selectively drop, or misattribute sources. Direct string append guarantees the citations appear verbatim in the final argument as transmitted to the Judge.
- **Three-citation cap** — Flooding an argument with sources reduces readability. The Judge scores `citation_strength` on quality not quantity; three well-chosen citations outperform ten marginal ones.
- **Round 2+ dual-search merge** — In rounds 2+, `SynthesizeEvidence` receives the merged result of `raw` (generic topic search) and `raw2` (targeted weakest-point search). This means the three selected citations are drawn from a richer pool that specifically targets the opponent's vulnerability.

---

### Skill 7 — ApplyRhetoric

**Source:** `src/debate/agents/debaters/skills.py`, class `ApplyRhetoric`

**Purpose:** Final polish pass. Elevate the evidence-enriched argument with classical rhetorical techniques — ethos, pathos, logos, analogy — and a memorable closing line, without altering factual content or citations.

#### Prompt Template

```
Round {round_number} | Stance: {stance}
Refine with ethos, pathos, logos, analogy, and a memorable closing:
{enriched_argument}
Do NOT change factual content or citations.
```

When `judge_feedback` is non-empty, the following is appended:

```
JUDGE'S MANDATE: {judge_feedback}  Ensure the final argument honors this.
```

**Inputs:**

| Placeholder | Source |
|-------------|--------|
| `{round_number}` | Current round integer |
| `{stance}` | `BaseDebater.STANCE` |
| `{enriched_argument}` | `SynthesizeEvidence` output — argument text with citations appended |
| `{judge_feedback}` | `routing_message["judge_feedback"]` |

**Output:** `{"final_argument": <str>}` — the string transmitted to the Judge as the debater's round submission.

#### Rationale and Design Decisions

- **"Do NOT change factual content or citations"** — Without this constraint the LLM tends to rephrase statistics and occasionally corrupts numeric values or drops source attributions during stylistic rewrites.
- **Ethos, pathos, logos enumeration** — Explicit naming prevents the skill from defaulting to only one mode. LLMs left to "refine" freely often add pathos (emotional appeals) at the expense of logos; naming all three forces balance.
- **`judge_feedback` as "MANDATE"** — The word "mandate" (stronger than "feedback" or "note") is chosen deliberately for the final polish stage. By the time the argument reaches `ApplyRhetoric` the logical substance is set; the mandate ensures the rhetorical framing also reflects the Judge's directive, not just the argument content.
- **Dual injection of `judge_feedback`** — Both `BuildCounterArgument` and `ApplyRhetoric` receive the judge feedback. This double-application pattern was added as a context engineering improvement (see Section 5) after observing that debaters sometimes incorporated the feedback into substance but reverted to prior rhetorical patterns in the final polish step.

---

## Section 3 — Judge Skills (4-Skill Pipeline)

The Judge runs a 4-skill pipeline after each debater's submission: `EnforceDebateMechanics` → `EvaluatePersuasionScore` → `RouteTurn` → (after all rounds) `DeclareVerdict`.

---

### Judge Skill 1 — EnforceDebateMechanics

**Source:** `src/debate/agents/judge/skills.py`, class `EnforceDebateMechanics`

**Purpose:** Rule-based validation of a submitted argument. Checks for three specific violations and issues a `ReprimandMessage` if any are found, triggering a mandatory rewrite by the debater. This skill makes **no LLM call**.

#### Logic (No Prompt — Rule-Based)

```python
# Rule 1: Citation requirement
if not msg.citations:
    return ReprimandMessage(
        target_agent=msg.agent_id,
        prompt_for_next="You must include at least one citation. Rewrite your argument with sources.",
    )

# Rule 2: Sycophancy phrase detection
_AGREEMENT_PHRASES = (
    "i agree", "you make a good point", "that's correct",
    "you're right", "well said", "i concede", "you are correct",
)
for phrase in _AGREEMENT_PHRASES:
    if phrase in arg_lower:
        return ReprimandMessage(
            target_agent=msg.agent_id,
            prompt_for_next="Sycophantic language detected. Maintain your position and rewrite.",
        )

# Rule 3: Fallacy evasion (round 2+)
if round_number >= 2 and fallacy_ignored:
    return ReprimandMessage(
        target_agent=msg.agent_id,
        prompt_for_next="You failed to identify an obvious logical fallacy. Address it and rewrite.",
    )
```

#### Rationale and Design Decisions

- **Rule-based not LLM-based** — Violations must be objective and consistent. An LLM judge evaluating sycophancy would produce variable verdicts; a substring match against a fixed phrase list is deterministic and auditable.
- **Phrase list mirrors anti-sycophancy directive** — The seven forbidden phrases in `_AGREEMENT_PHRASES` correspond directly to the categories in `_ANTI_SYCOPHANCY`. This creates a closed loop: the debater is instructed not to say them, and the Judge catches it if they slip through.
- **Fallacy rule activates from Round 2** — Round 1 has no opponent argument to analyse, so `fallacy_ignored` is structurally `False`. The guard prevents spurious reprimands on opening statements.

---

### Judge Skill 2 — EvaluatePersuasionScore

**Source:** `src/debate/agents/judge/skills.py`, class `EvaluatePersuasionScore`

**Purpose:** Score the submitted argument on three dimensions (logical consistency, citation strength, rhetoric quality) by delegating to the structured `evaluate_llm` callable. Incorporates `previous_feedback` context so the Judge can penalise debaters who ignore prior instructions.

#### Context Engineering: previous_feedback Injection

When `previous_feedback` is non-empty, the argument text is wrapped before being sent to the evaluate LLM:

```
[JUDGE CONTEXT: You previously instructed this debater: '{previous_feedback}'.
Penalize the score if this feedback was ignored.]

{argument}
```

The scoring call then receives this augmented text alongside the citations list.

#### Score Object

```python
@dataclass
class PersuasionScore:
    agent_id: str
    round: int
    logical_consistency: float   # 0.0 – 1.0
    citation_strength: float     # 0.0 – 1.0
    rhetoric_quality: float      # 0.0 – 1.0

    @property
    def weighted(self) -> float:
        return (
            SCORE_WEIGHT_LOGIC    * self.logical_consistency
            + SCORE_WEIGHT_CITATION * self.citation_strength
            + SCORE_WEIGHT_RHETORIC * self.rhetoric_quality
        )
```

The actual weight constants (`SCORE_WEIGHT_LOGIC`, `SCORE_WEIGHT_CITATION`, `SCORE_WEIGHT_RHETORIC`) are defined in `shared/constants.py`.

#### Rationale and Design Decisions

- **Three-dimension scoring** — A single holistic score gives no actionable feedback. Separating logic, citation, and rhetoric means the Judge's routing feedback can be specific ("your citation score dropped — add data") rather than generic ("do better").
- **`previous_feedback` penalisation context** — Without this injection, the evaluate LLM sees only the argument text and has no way to know whether the debater incorporated prior advice. Adding the context shifts the scoring model from purely evaluative to behaviourally aware, closing the feedback accountability loop.
- **Score the evaluator prompt is documented in Section 4.**

---

### Judge Skill 3 — RouteTurn

**Source:** `src/debate/agents/judge/skills.py`, class `RouteTurn`

**Purpose:** Produce the `RoutingMessage` that directs the next debater's turn. Calls the route LLM to generate 1–2 sentences of constructive feedback from the score, then constructs the `prompt_for_next` string — with or without a reminder of `previous_feedback`.

#### Routing Prompt Construction

The route LLM call (documented in Section 4) receives the `PersuasionScore` object and generates free-text feedback. The `prompt_for_next` field is then assembled deterministically:

**Without previous_feedback:**
```
It is your turn now, {next_agent}. Respond directly to the previous argument.
```

**With previous_feedback:**
```
It is your turn now, {next_agent}. Respond directly to the previous argument.
REMINDER — The Judge previously instructed you: '{previous_feedback}'.
You MUST address this directive explicitly. Failure to comply will result in a score penalty.
```

**Inputs:**

| Field | Source |
|-------|--------|
| `score` | `PersuasionScore` from `EvaluatePersuasionScore` |
| `next_agent` | Determined by orchestrator turn rotation |
| `previous_feedback` | The Judge's feedback text from the prior round for this agent |

**Output:** `RoutingMessage` with fields `target_agent`, `judge_feedback` (the new LLM-generated feedback), and `prompt_for_next`.

#### Rationale and Design Decisions

- **`previous_feedback` reminder in routing** — The `prompt_for_next` field is what the debater's `respond()` method reads first. Placing the reminder here, rather than only in `EvaluatePersuasionScore`, ensures the debater sees the directive at the start of its pipeline — before it has begun constructing any argument. This is the third point in the feedback chain (alongside `BuildCounterArgument` and `ApplyRhetoric`) where the Judge's previous instruction surfaces.
- **"Failure to comply will result in a score penalty"** — Explicit consequence language was added because tests showed debaters acknowledging the reminder but not changing behaviour when the consequence was implicit. The warning primes the debater's anti-sycophancy directive with stakes.

---

### Judge Skill 4 — DeclareVerdict

**Source:** `src/debate/agents/judge/skills.py`, class `DeclareVerdict`

**Purpose:** Compute cumulative weighted scores across all rounds, resolve ties, and produce the final `VerdictMessage`. This skill is **fully deterministic** — it performs arithmetic only, with no LLM call.

#### Logic (No Prompt — Deterministic)

```python
pro_avg = sum(s.weighted for s in scores_pro) / len(scores_pro)
con_avg = sum(s.weighted for s in scores_con) / len(scores_con)

# Tie-break by citation_strength
if abs(pro_avg - con_avg) < 1e-9:
    pro_cite = sum(s.citation_strength for s in scores_pro) / len(scores_pro)
    con_cite = sum(s.citation_strength for s in scores_con) / len(scores_con)
    if pro_cite >= con_cite:
        pro_avg += 0.01
    else:
        con_avg += 0.01

winner = AgentID.PRO if pro_avg > con_avg else AgentID.CON
```

The justification string is assembled as:

```
{winner} demonstrated superior persuasion across {rounds} round(s).
Logic {pro_avg:.2f} vs {con_avg:.2f};
rhetoric and citation quality consistently favoured {winner}.
```

#### Rationale and Design Decisions

- **Deterministic verdict** — Verdicts must be reproducible and not subject to LLM variance. A human student reviewing results must be able to verify the winner from the score log alone.
- **Citation-strength tie-break** — Among the three score dimensions, citation strength most directly reflects verifiable effort (providing sources). It is therefore the fairest single-axis tie-breaker.
- **No-tie guarantee** — The `+0.01` nudge ensures `DeclareVerdict` always produces a unique winner. This is required because `VerdictMessage` schema does not allow a draw; the debate system is designed to always produce a binary outcome.
- **`MIN_JUSTIFICATION_LENGTH` padding** — The justification string is padded with spaces if it falls below the minimum length constant, ensuring the schema validation in `VerdictMessage` always passes.

---

## Section 4 — LLM Evaluate and Route Prompts

These prompts live in `src/debate/shared/llm_provider.py` and are used exclusively by the Judge agent.

### 4.1 — Evaluate Prompt (EvaluatePersuasionScore)

Used by both `_anthropic_evaluate_llm` and `_gemini_evaluate_llm`. The argument text passed in may be pre-wrapped with the `previous_feedback` context block (see Section 3, Skill 2) before this prompt is constructed.

#### Prompt Template

```
Score this debate argument on three dimensions from 0.0 to 1.0.
Argument: {argument}
Citations: {citations}

Reply with ONLY a raw JSON object, no markdown, no code fences:
{"logical_consistency": <float>, "citation_strength": <float>, "rhetoric_quality": <float>}
```

**Inputs:**

| Field | Source |
|-------|--------|
| `{argument}` | `msg.argument` (possibly prefixed with judge-context block) |
| `{citations}` | `msg.citations` list |

**Expected output:**
```json
{"logical_consistency": 0.82, "citation_strength": 0.65, "rhetoric_quality": 0.78}
```

The `_extract_json()` helper strips any markdown fences the model might add despite the instruction, then parses the JSON.

#### Rationale and Design Decisions

- **"ONLY a raw JSON object, no markdown, no code fences"** — This instruction is repeated twice (implicitly by the example format). Markdown fences cause `json.loads()` to fail; the instruction minimises post-processing failures even though `_extract_json()` provides a fallback strip.
- **0.0–1.0 scale** — Normalised floats integrate cleanly into the weighted-sum formula in `PersuasionScore.weighted` without requiring any post-normalisation step.
- **Three dimensions not one** — See Section 3, Skill 2 rationale. Separate scores enable dimension-specific feedback in `RouteTurn`.
- **`max_tokens=256`** — The response is a JSON object of three floats; 256 tokens is generous without wasting quota.

---

### 4.2 — Route Prompt (RouteTurn feedback generation)

Used by both `_anthropic_route_llm` and `_gemini_route_llm`.

#### Prompt Template

```
A debate argument scored: logic={logic:.2f}, citation={citation:.2f}, rhetoric={rhetoric:.2f}.
Give 1-2 sentences of constructive feedback.
```

**Inputs:**

| Field | Source |
|-------|--------|
| `{logic:.2f}` | `score.logical_consistency` |
| `{citation:.2f}` | `score.citation_strength` |
| `{rhetoric:.2f}` | `score.rhetoric_quality` |

**Expected output:** 1–2 sentences of natural-language feedback, stored as `judge_feedback` in the `RoutingMessage` and threaded to the next debater.

#### Rationale and Design Decisions

- **Numeric scores in prompt** — Including the actual scores gives the LLM an anchor for calibrated feedback. Without numbers, feedback tends toward generic encouragement; with them, the model produces targeted advice ("your citation score of 0.45 is low — provide more sources").
- **"1-2 sentences"** — Constrained length keeps feedback actionable. Long feedback confuses the debater skill pipeline because `BuildCounterArgument` incorporates it verbatim; a paragraph-long mandate crowds out the actual argument instruction.
- **`max_tokens=150`** — Matches the 1–2 sentence constraint with a comfortable margin.

---

## Section 5 — Context Engineering Improvements

Two distinct context engineering problems were identified and resolved during system development. Both improvements involve threading information from a later stage (the Judge) backwards to earlier stages (the debater skills), creating closed feedback loops.

---

### Improvement 1 — Closing the Judge-Feedback Loop

#### Problem

In early versions, the Judge generated textual feedback (route LLM output) and placed it in `RoutingMessage.judge_feedback`. The debater's `respond()` method extracted this field and passed it to `_run_pipeline()`, but `_run_pipeline()` only forwarded it to `ApplyRhetoric`. This meant the feedback influenced only the final rhetorical polish step. The argumentative substance — generated by `BuildCounterArgument` — was completely unaware of what the Judge had criticised in the previous round. Observed outcome: debaters would rephrase the same weak argument more elegantly, satisfying the rhetoric score while still ignoring the Judge's substantive critique.

#### Fix

The `judge_feedback` parameter was threaded through the entire pipeline at two critical injection points:

**Injection point A — `BuildCounterArgument`:**

```python
counter = self._build.run(
    self.STANCE, self._topic, analysis, fallacies, strategy, raw2, llm,
    judge_feedback=judge_feedback,   # <-- added
)
```

Inside `BuildCounterArgument.run()`, when `judge_feedback` is non-empty, a mandatory block is appended to the base prompt:

```
JUDGE'S FEEDBACK (MANDATORY): {judge_feedback}
You MUST directly adapt your argument to address this feedback.
If the Judge asked for specific data, statistics, or citations, you MUST provide them NOW.
```

This ensures the argument's logical substance is rebuilt around the Judge's critique before any evidence or rhetoric is applied.

**Injection point B — `ApplyRhetoric`:**

```python
rhetoric = self._rhetoric.run(
    evidence["enriched_argument"], self.STANCE, round_number, llm, judge_feedback
)
```

Inside `ApplyRhetoric.run()`, when `judge_feedback` is non-empty, a mandate is appended to the rhetoric prompt:

```
JUDGE'S MANDATE: {judge_feedback}  Ensure the final argument honors this.
```

This second injection ensures the rhetorical framing of the final output also reflects the Judge's directive, not just the argument's internal logic.

**Additionally**, the `previous_feedback` context block in `EvaluatePersuasionScore` closes the accountability loop on the Judge's side: the scoring model is informed of what it previously instructed and penalises the debater if it was ignored.

**Full feedback chain:**

```
Judge issues feedback (RouteTurn)
    → stored in RoutingMessage.judge_feedback
    → BaseDebater.respond() extracts judge_feedback
    → _run_pipeline() passes it to:
        [A] BuildCounterArgument (mandatory block — substantive)
        [B] ApplyRhetoric (mandate block — rhetorical)
    → next round: EvaluatePersuasionScore prepends previous_feedback context
        → Judge scores lower if feedback was ignored
    → RouteTurn appends REMINDER to prompt_for_next
        → debater sees the reminder before its next pipeline run
```

---

### Improvement 2 — Targeted Web Search via weakest_point

#### Problem

In early versions, the web search for evidence was always executed against the generic debate topic string. For a topic such as "Universal Basic Income improves societal well-being", every search query was `"Universal Basic Income improves societal well-being"` regardless of what the opponent had just argued. This produced thematically related but strategically irrelevant citations — the search results supported the debater's general position rather than refuting the opponent's specific claim.

#### Fix

`AnalyzeOpponent` extracts `weakest_point` from the opponent's argument. In `_run_pipeline()`, this field is used to build a targeted search query instead of the generic topic:

```python
weakest = analysis.get("weakest_point", "") or analysis.get("main_claim", "")
search_query = f"evidence statistics: {weakest}" if weakest else self._topic
raw2 = self._web_search.search(search_query)
```

The prefix `"evidence statistics: "` biases the search toward empirical sources rather than opinion pieces — directly addressing the `citation_strength` score dimension.

`SynthesizeEvidence` then receives `raw + raw2` (the generic topic results merged with the targeted results), so the three selected citations can be drawn from the richer combined pool.

**Effect:** When the opponent argues "studies show GDP growth does not benefit lower-income groups", the debater's search query becomes `"evidence statistics: GDP growth does not benefit lower-income groups"` — returning directly contradicting empirical literature rather than generic UBI advocacy articles.

---

*End of Prompts Book*
