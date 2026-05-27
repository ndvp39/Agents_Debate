---
name: detect_fallacies
type: llm_prompt
description: Explicitly name and explain any logical fallacies present in the opponent's most recent argument.
when_to_use: Invoke this skill on rounds 2+ after analyze_opponent. Its output gives the debater concrete fallacy names to call out by name in the counter-argument, raising the rhetorical stakes.
inputs:
  - opponent_argument: The full text of the opponent's most recent argument.
  - analysis: The structured output of analyze_opponent (main claim, supporting points, assumptions, weakest point).
---

# Detect Fallacies

You are a logician auditing a debate argument for formal and informal fallacies.

## Instructions

Find logical fallacies in:
{{ opponent_argument }}
Name each fallacy and explain how it appears. If none, state 'No fallacies detected.'

## Output format

Return a JSON object with keys: `fallacies_found` (list of fallacy names) and `fallacy_descriptions` (list of explanations). If the model returns prose, the calling code will treat the full text as a single description entry.
