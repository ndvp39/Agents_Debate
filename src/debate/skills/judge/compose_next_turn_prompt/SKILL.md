---
name: compose_next_turn_prompt
type: deterministic
description: Build the literal prompt_for_next handoff string sent to the next debater, optionally including a binding reminder of prior judge feedback.
when_to_use: Invoke this skill after generate_judge_feedback to produce the `prompt_for_next` field of the routing message. There is no LLM call — the skill returns the exact string the next agent will receive.
inputs:
  - next_agent: The id of the next debater (e.g. "Agent_Pro" or "Agent_Con").
  - judge_feedback_reminder: Optional pre-formatted REMINDER clause carrying the judge's prior instruction to this agent. Empty string when the agent has no prior feedback.
outputs:
  - prompt_for_next: The literal handoff string.
---

# Compose Next-Turn Prompt

## Rules

The skill is a pure string formatter with no LLM call.

1. **Base sentence** — always emit:
   `"It is your turn now, {next_agent}. Respond directly to the previous argument."`
2. **Reminder variant** — when `judge_feedback_reminder` is a non-empty string, append a single space then the reminder verbatim. The expected reminder shape (assembled by the judge agent) is:
   `"REMINDER — The Judge previously instructed you: '<prior feedback>'. You MUST address this directive explicitly. Failure to comply will result in a score penalty."`
3. **No-reminder variant** — when `judge_feedback_reminder` is empty, return the base sentence unchanged.

The skill returns a single string. No markdown, no headings.

## Implementation

The deterministic logic is implemented in `script.py` alongside this SKILL.md.
