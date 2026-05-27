---
name: synthesize_evidence
type: deterministic
description: Pure-logic skill — append up to 3 citation strings to an argument draft and surface the chosen citations.
when_to_use: Invoke this skill between the substantive-argument step (craft_opening on round 1, or build_counter_argument on rounds 2+) and apply_rhetoric. It enriches the argument with sources without changing the argument's body.
inputs:
  - argument_draft: The raw argument text produced upstream.
  - raw_search_results: An ordered list of citation strings (e.g. from web search). May be empty.
outputs:
  - citations: The first up-to-3 entries of raw_search_results.
  - enriched_argument: The argument_draft with a trailing Sources line appended (semicolon-separated citations), or unchanged when no citations were selected.
---

# Synthesize Evidence

## Rules

The skill is a pure transformation with no LLM call.

1. **Constants**
   - `MAX_CITATIONS = 3` — at most three citations are attached per argument, regardless of input length.
2. **Selection** — take the first `MAX_CITATIONS` items of `raw_search_results` (preserving order). Excess citations are dropped silently.
3. **Enrichment**
   - If no citations were selected, return `argument_draft` unchanged as `enriched_argument`.
   - Otherwise append a single block of the form `"\n\nSources: " + "; ".join(citations)` to the draft.
4. The skill returns a dict with keys `citations` (list) and `enriched_argument` (string).

## Implementation

The deterministic logic is implemented in `script.py` alongside this SKILL.md.
