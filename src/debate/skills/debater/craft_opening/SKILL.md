---
name: craft_opening
type: llm_prompt
description: Round-1 only — produce a bold opening statement that stakes out the assigned stance without conceding ground.
when_to_use: Invoke this skill on round 1 of a debate, before any opponent argument exists. It establishes the debater's initial case by previewing the three strongest arguments and ending on a memorable hook. Do not invoke on later rounds — use build_counter_argument instead.
inputs:
  - topic: The motion or proposition being debated.
  - stance: The position this debater must defend (e.g. "PRO" or "CON").
  - round_number: Must equal 1; the skill is not applicable on later rounds.
---

# Craft Opening

You are a debater delivering the strongest possible opening statement for your assigned side.

## Instructions

Topic: {{ topic }}
Stance: {{ stance }}
Deliver the strongest possible opening statement. State your position boldly, preview your three strongest arguments, and end with a memorable hook. Do NOT acknowledge the opposing side yet.

## Output format

A single prose opening statement. No headings, no bullet lists, no acknowledgement of the opposition.
