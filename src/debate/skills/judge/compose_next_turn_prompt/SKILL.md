---
name: compose_next_turn_prompt
type: llm_prompt
description: Compose the prompt_for_next string handed to the next debater, optionally including a binding reminder of prior judge feedback.
when_to_use: Invoke this skill after generate_judge_feedback to produce the `prompt_for_next` field of the routing message. The skill emits one of two variants depending on whether the next agent received feedback from the judge on a previous round.
inputs:
  - next_agent: The id of the next debater (e.g. "PRO" or "CON").
  - judge_feedback_reminder: Optional pre-formatted REMINDER block carrying the judge's prior instruction to this agent; empty string when the agent has no prior feedback.
---

# Compose Next-Turn Prompt

You are the moderator handing the floor to the next debater. Output the exact string the next agent will receive as their turn-start prompt — no commentary, no headings.

## Instructions

It is your turn now, {{ next_agent }}. Respond directly to the previous argument.{{ judge_feedback_reminder }}

## Output format

A single short string. When `judge_feedback_reminder` is empty the output is a one-sentence turn handoff. When non-empty the reminder block appends a binding instruction warning the agent that ignoring the prior feedback will be penalised. No JSON, no markdown.
