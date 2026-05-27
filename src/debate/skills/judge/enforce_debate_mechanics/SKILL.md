---
name: enforce_debate_mechanics
type: deterministic
description: Pure-logic skill — gate an incoming argument against debate rules and emit a ReprimandMessage if any rule is violated.
when_to_use: Invoke this skill as the first step of judge processing for every incoming ArgumentMessage, before evaluate_persuasion_score. If it returns a reprimand the judge sends it instead of scoring and routing; if it returns None the argument is accepted and the pipeline continues.
inputs:
  - msg: The incoming ArgumentMessage (fields used — `agent_id`, `argument`, `citations`).
  - round_number: The 1-indexed round the argument belongs to.
  - fallacy_ignored: True when the judge has independently determined the debater ignored an obvious fallacy; only enforced on round 2+.
outputs:
  - reprimand: A `ReprimandMessage` (with a fixed `prompt_for_next` matching the violated rule) when any rule fails, otherwise `None`.
---

# Enforce Debate Mechanics

## Rules

The skill is a deterministic gate with no LLM call. Rules are checked in order; the first violation short-circuits and returns its `ReprimandMessage`. If all rules pass, return `None`.

1. **Citation required** — if `msg.citations` is empty (falsy), reprimand with:
   `"You must include at least one citation. Rewrite your argument with sources."`
2. **No sycophancy** — lowercase `msg.argument` and check for any of the agreement phrases listed below. If any phrase is found anywhere in the text, reprimand with:
   `"Sycophantic language detected. Maintain your position and rewrite."`
3. **No ignored fallacies on round 2+** — if `round_number >= 2` AND `fallacy_ignored` is True, reprimand with:
   `"You failed to identify an obvious logical fallacy. Address it and rewrite."`

### Agreement phrases (sycophancy detection)

The match is case-insensitive substring search against the lowercased argument text:

- `i agree`
- `you make a good point`
- `that's correct`
- `you're right`
- `well said`
- `i concede`
- `you are correct`

Every reprimand sets `target_agent = msg.agent_id`.

## Implementation

The deterministic logic is implemented in `script.py` alongside this SKILL.md.
