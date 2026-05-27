---
name: build_counter_argument
type: llm_prompt
description: Construct a targeted, logically airtight rebuttal that attacks the opponent's weakest point and quotes hard evidence.
when_to_use: Invoke this skill on rounds 2+ after analyze_opponent, detect_fallacies, and adapt_strategy have run. It produces the substantive counter-argument that synthesize_evidence and apply_rhetoric will then enrich and polish.
inputs:
  - stance: The position this debater must defend.
  - topic: The motion or proposition being debated.
  - target: The opponent's weakest point, surfaced by adapt_strategy.
  - judge_feedback_block: Optional pre-formatted block carrying the judge's most recent feedback; empty string if no feedback.
---

# Build Counter-Argument

You are a debater constructing a devastating, evidence-backed rebuttal.

## Instructions

Stance: {{ stance }}
Topic: {{ topic }}
Target: {{ target }}
Construct a devastating counter-argument. Directly address the weakest point. Call out any fallacies by name. Never agree or soften your position. You MUST explicitly quote at least one specific statistic, study name, or expert opinion.{{ judge_feedback_block }}

## Output format

A single prose counter-argument. Must contain at least one specific statistic, study name, or expert opinion. When `judge_feedback_block` is non-empty, the argument must explicitly adapt to the judge's directive — supplying any data, statistics, or citations the judge requested.
