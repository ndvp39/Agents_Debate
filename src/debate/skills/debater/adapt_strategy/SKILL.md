---
name: adapt_strategy
type: deterministic
description: Pure-logic skill — choose defensive, offensive, or pivot mode for the current round based on comparing own vs opponent average scores.
when_to_use: Invoke this skill on rounds 2+ between detect_fallacies and build_counter_argument. It produces a small strategy object (mode, target, rationale) that determines what build_counter_argument attacks and how aggressively.
inputs:
  - round_number: The current round number.
  - own_score: Running average persuasion score for this debater (float in [0.0, 1.0]).
  - opp_score: Running average persuasion score for the opponent (float in [0.0, 1.0]).
  - analysis: The structured output of analyze_opponent — the `weakest_point` key (falling back to `main_claim`) determines the strategic target.
  - fallacies: The structured output of detect_fallacies (accepted but not currently used by the rules; kept for forward compatibility).
---

# Adapt Strategy

## Rules

The skill is a pure decision procedure with no LLM call.

1. **Mode selection** — compare the two running scores:
   - if `own_score < opp_score` → mode = `"defensive"`
   - if `own_score > opp_score` → mode = `"offensive"`
   - if scores are equal → mode = `"pivot"`
2. **Target selection** — read `analysis["weakest_point"]`. If absent or empty, fall back to the literal string `"opponent's main claim"`.
3. **Rationale** — emit a short human-readable trace of the decision in the form:
   `"Round {round_number}: {mode} chosen (own={own_score:.2f}, opp={opp_score:.2f})."`

The skill returns a dict with keys `mode`, `target`, `rationale`.

## Implementation

The deterministic logic is implemented in `script.py` alongside this SKILL.md.
