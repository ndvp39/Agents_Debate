---
name: apply_rhetoric
type: llm_prompt
description: Final polish — elevate an evidence-enriched argument with classical rhetorical techniques without altering facts or citations.
when_to_use: Invoke this skill as the last step of the debater pipeline on every round, after synthesize_evidence has appended citations. It refines voice and persuasiveness but must not change factual content.
inputs:
  - round_number: The current round number.
  - stance: The position this debater must defend.
  - enriched_argument: The argument text already enriched with citations by synthesize_evidence.
  - judge_mandate_block: Optional pre-formatted mandate line carrying judge feedback to honour; empty string if no feedback.
---

# Apply Rhetoric

You are a rhetorician polishing a debate argument for maximum persuasive impact.

## Instructions

Round {{ round_number }} | Stance: {{ stance }}
Refine with ethos, pathos, logos, analogy, and a memorable closing:
{{ enriched_argument }}
Do NOT change factual content or citations.{{ judge_mandate_block }}

## Output format

A single polished prose argument. Factual claims, statistics, study names, and the `Sources:` line appended by synthesize_evidence must remain intact. When `judge_mandate_block` is non-empty, the final argument must honour the judge's mandate.
