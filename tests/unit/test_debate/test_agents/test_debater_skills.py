"""Tests for debate.agents.debaters.skills — TDD RED phase."""

import pytest

from debate.agents.debaters.skills import (
    AdaptStrategy,
    AnalyzeOpponent,
    ApplyRhetoric,
    BuildCounterArgument,
    CraftOpening,
    DetectFallacies,
    SynthesizeEvidence,
)
from debate.shared.exceptions import SkillNotApplicableError


def _llm(response):
    return lambda prompt: response


# ---------------------------------------------------------------------------
# CraftOpening
# ---------------------------------------------------------------------------

def test_craft_opening_round_1_returns_opening_statement():
    result = CraftOpening().run("AI and jobs", "completely FOR", 1, _llm("Bold opening here."))
    assert "opening_statement" in result
    assert len(result["opening_statement"]) > 0


def test_craft_opening_raises_on_round_2():
    with pytest.raises(SkillNotApplicableError):
        CraftOpening().run("AI and jobs", "completely FOR", 2, _llm("..."))


def test_craft_opening_raises_on_round_3():
    with pytest.raises(SkillNotApplicableError):
        CraftOpening().run("AI and jobs", "completely FOR", 3, _llm("..."))


def test_craft_opening_calls_llm():
    calls = []
    def llm(prompt):
        calls.append(prompt)
        return "Opening."
    CraftOpening().run("AI", "FOR", 1, llm)
    assert len(calls) == 1


# ---------------------------------------------------------------------------
# AnalyzeOpponent
# ---------------------------------------------------------------------------

def test_analyze_opponent_returns_required_keys():
    llm = _llm({"main_claim": "X", "supporting_points": [], "assumptions": [], "weakest_point": "Y"})
    result = AnalyzeOpponent().run("Opponent argument.", llm)
    assert "main_claim" in result
    assert "weakest_point" in result


def test_analyze_opponent_handles_string_llm_response():
    result = AnalyzeOpponent().run("Argument.", _llm("Main claim here."))
    assert "main_claim" in result


def test_analyze_opponent_calls_llm():
    calls = []
    def llm(p):
        calls.append(p)
        return "Claim."
    AnalyzeOpponent().run("Arg.", llm)
    assert len(calls) == 1


# ---------------------------------------------------------------------------
# DetectFallacies
# ---------------------------------------------------------------------------

def test_detect_fallacies_returns_required_keys():
    analysis = {"main_claim": "X", "supporting_points": [], "assumptions": [], "weakest_point": "Y"}
    llm = _llm({"fallacies_found": ["Strawman"], "fallacy_descriptions": ["Misrepresents position."]})
    result = DetectFallacies().run("Opponent arg.", analysis, llm)
    assert "fallacies_found" in result
    assert "fallacy_descriptions" in result


def test_detect_fallacies_handles_string_response():
    analysis = {"weakest_point": "point"}
    result = DetectFallacies().run("Arg.", analysis, _llm("Slippery slope detected."))
    assert "fallacies_found" in result


def test_detect_fallacies_dict_response_preserved():
    analysis = {}
    expected = {"fallacies_found": ["Slippery Slope"], "fallacy_descriptions": ["desc"]}
    result = DetectFallacies().run("Arg.", analysis, _llm(expected))
    assert result["fallacies_found"] == ["Slippery Slope"]


# ---------------------------------------------------------------------------
# AdaptStrategy
# ---------------------------------------------------------------------------

def test_adapt_strategy_offensive_when_ahead():
    analysis = {"weakest_point": "automation claim"}
    result = AdaptStrategy().run(3, 0.8, 0.5, analysis, {})
    assert result["mode"] == "offensive"


def test_adapt_strategy_defensive_when_behind():
    analysis = {"weakest_point": "automation claim"}
    result = AdaptStrategy().run(5, 0.4, 0.7, analysis, {})
    assert result["mode"] == "defensive"


def test_adapt_strategy_pivot_when_tied():
    analysis = {"weakest_point": "automation claim"}
    result = AdaptStrategy().run(2, 0.6, 0.6, analysis, {})
    assert result["mode"] == "pivot"


def test_adapt_strategy_returns_target():
    analysis = {"weakest_point": "the strawman claim"}
    result = AdaptStrategy().run(1, 0.5, 0.5, analysis, {})
    assert "target" in result


# ---------------------------------------------------------------------------
# BuildCounterArgument
# ---------------------------------------------------------------------------

def test_build_counter_argument_returns_counter():
    result = BuildCounterArgument().run(
        "completely FOR", "AI jobs", {}, {}, {"target": "weakest"}, [], _llm("Counter argument text.")
    )
    assert "counter_argument" in result
    assert len(result["counter_argument"]) > 0


def test_build_counter_argument_calls_llm():
    calls = []
    def llm(p):
        calls.append(p)
        return "Counter."
    BuildCounterArgument().run("FOR", "AI", {}, {}, {}, [], llm)
    assert len(calls) == 1


# ---------------------------------------------------------------------------
# SynthesizeEvidence
# ---------------------------------------------------------------------------

def test_synthesize_evidence_returns_top_3():
    raw = ["Src1", "Src2", "Src3", "Src4", "Src5"]
    result = SynthesizeEvidence().run("Draft argument.", raw)
    assert len(result["citations"]) == 3


def test_synthesize_evidence_empty_results():
    result = SynthesizeEvidence().run("Draft argument.", [])
    assert result["citations"] == []
    assert result["enriched_argument"] == "Draft argument."


def test_synthesize_evidence_enriches_draft():
    result = SynthesizeEvidence().run("Draft.", ["Source A"])
    assert "Draft." in result["enriched_argument"]


def test_synthesize_evidence_citations_in_enriched():
    result = SynthesizeEvidence().run("Draft.", ["Source A", "Source B"])
    assert "Source A" in result["enriched_argument"] or len(result["citations"]) > 0


# ---------------------------------------------------------------------------
# ApplyRhetoric
# ---------------------------------------------------------------------------

def test_apply_rhetoric_returns_final_argument():
    result = ApplyRhetoric().run("Enriched argument here.", "completely FOR", 1, _llm("Rhetoric applied."))
    assert "final_argument" in result
    assert len(result["final_argument"]) > 0


def test_apply_rhetoric_calls_llm():
    calls = []
    def llm(p):
        calls.append(p)
        return "Enhanced."
    ApplyRhetoric().run("Argument.", "FOR", 2, llm)
    assert len(calls) == 1
