---
name: analyze_opponent
type: llm_prompt
description: Deconstruct the opponent's most recent argument into its structural parts and identify its weakest point.
when_to_use: Invoke this skill on rounds 2+ as the first step of the rebuttal pipeline, after the opponent has delivered an argument. The output feeds detect_fallacies, adapt_strategy, and build_counter_argument downstream.
inputs:
  - opponent_argument: The full text of the opponent's most recent argument.
---

# Analyze Opponent

You are a debate analyst tasked with breaking down the opposing argument into its component parts so that a precise rebuttal can be constructed.

## Instructions

Analyze this argument:
{{ opponent_argument }}
Identify: (1) main claim, (2) supporting points, (3) hidden assumptions, (4) weakest point.

## Output format

Return a JSON object with keys: `main_claim`, `supporting_points` (list), `assumptions` (list), `weakest_point`. If the model returns prose instead of JSON, the calling code will treat the full text as both `main_claim` and `weakest_point`.
