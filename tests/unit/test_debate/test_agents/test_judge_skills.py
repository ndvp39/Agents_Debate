"""Tests for debate.agents.judge.skills — TDD RED phase."""

import pytest

from debate.agents.judge.skills import (
    DeclareVerdict,
    EnforceDebateMechanics,
    EvaluatePersuasionScore,
    PersuasionScore,
    RouteTurn,
)
from debate.ipc.schemas import ArgumentMessage
from debate.shared.constants import (
    SCORE_WEIGHT_CITATION,
    SCORE_WEIGHT_LOGIC,
    SCORE_WEIGHT_RHETORIC,
    AgentID,
)
from debate.shared.exceptions import InsufficientDataError

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _arg(agent_id=AgentID.PRO, round_=1, argument="AI creates jobs.", citations=None) -> ArgumentMessage:
    return ArgumentMessage(
        agent_id=agent_id,
        round=round_,
        argument=argument,
        citations=citations or ["MIT Study 2024."],
    )


def _score(agent_id=AgentID.PRO, round_=1, logic=0.8, citation=0.7, rhetoric=0.6) -> PersuasionScore:
    return PersuasionScore(
        agent_id=agent_id, round=round_,
        logical_consistency=logic,
        citation_strength=citation,
        rhetoric_quality=rhetoric,
    )


# ---------------------------------------------------------------------------
# PersuasionScore
# ---------------------------------------------------------------------------

def test_persuasion_score_weighted_calculation():
    s = _score(logic=1.0, citation=1.0, rhetoric=1.0)
    expected = SCORE_WEIGHT_LOGIC * 1.0 + SCORE_WEIGHT_CITATION * 1.0 + SCORE_WEIGHT_RHETORIC * 1.0
    assert abs(s.weighted - expected) < 1e-9


def test_persuasion_score_weighted_partial():
    s = _score(logic=0.5, citation=0.0, rhetoric=0.0)
    assert abs(s.weighted - SCORE_WEIGHT_LOGIC * 0.5) < 1e-9


# ---------------------------------------------------------------------------
# EnforceDebateMechanics
# ---------------------------------------------------------------------------

def test_enforce_passes_valid_argument():
    result = EnforceDebateMechanics().run(_arg())
    assert result is None


def test_enforce_reprimands_empty_citations():
    # ArgumentMessage validates non-empty citations, so we use a MagicMock
    # to simulate a message that somehow has empty citations at the skill level.
    from unittest.mock import MagicMock  # noqa: PLC0415
    mock_msg = MagicMock()
    mock_msg.citations = []
    mock_msg.agent_id = AgentID.PRO
    mock_msg.argument = "Some argument."
    result = EnforceDebateMechanics().run(mock_msg)
    assert result is not None
    assert result.target_agent == AgentID.PRO


def test_enforce_reprimands_agreement_phrase_i_agree():
    from unittest.mock import MagicMock  # noqa: PLC0415
    mock_msg = MagicMock()
    mock_msg.citations = ["Source."]
    mock_msg.agent_id = AgentID.PRO
    mock_msg.argument = "I agree with your point about climate change."
    result = EnforceDebateMechanics().run(mock_msg)
    assert result is not None
    assert result.target_agent == AgentID.PRO


def test_enforce_reprimands_agreement_phrase_good_point():
    from unittest.mock import MagicMock  # noqa: PLC0415
    mock_msg = MagicMock()
    mock_msg.citations = ["Source."]
    mock_msg.agent_id = AgentID.CON
    mock_msg.argument = "You make a good point, however..."
    result = EnforceDebateMechanics().run(mock_msg)
    assert result is not None
    assert result.target_agent == AgentID.CON


def test_enforce_reprimands_fallacy_ignored_round_2plus():
    from unittest.mock import MagicMock  # noqa: PLC0415
    mock_msg = MagicMock()
    mock_msg.citations = ["Source."]
    mock_msg.agent_id = AgentID.PRO
    mock_msg.argument = "AI is simply better for jobs overall."
    result = EnforceDebateMechanics().run(mock_msg, round_number=2, fallacy_ignored=True)
    assert result is not None


def test_enforce_no_fallacy_check_on_round_1():
    from unittest.mock import MagicMock  # noqa: PLC0415
    mock_msg = MagicMock()
    mock_msg.citations = ["Source."]
    mock_msg.agent_id = AgentID.PRO
    mock_msg.argument = "AI is better for jobs."
    result = EnforceDebateMechanics().run(mock_msg, round_number=1, fallacy_ignored=True)
    assert result is None  # round 1: fallacy check skipped


# ---------------------------------------------------------------------------
# EvaluatePersuasionScore
# ---------------------------------------------------------------------------

def test_evaluate_returns_persuasion_score():
    def llm_call(arg, cit):
        return {"logical_consistency": 0.8, "citation_strength": 0.7, "rhetoric_quality": 0.9}
    score = EvaluatePersuasionScore().run(_arg(), llm_call)
    assert isinstance(score, PersuasionScore)
    assert score.agent_id == AgentID.PRO
    assert score.logical_consistency == 0.8
    assert score.citation_strength == 0.7
    assert score.rhetoric_quality == 0.9


def test_evaluate_calls_llm_with_argument_and_citations():
    calls = []
    def llm_call(arg, cit):
        calls.append((arg, cit))
        return {"logical_consistency": 0.5, "citation_strength": 0.5, "rhetoric_quality": 0.5}
    msg = _arg(argument="Test arg.", citations=["Src."])
    EvaluatePersuasionScore().run(msg, llm_call)
    assert len(calls) == 1
    assert calls[0][0] == "Test arg."
    assert calls[0][1] == ["Src."]


# ---------------------------------------------------------------------------
# RouteTurn
# ---------------------------------------------------------------------------

def test_route_turn_produces_routing_message():
    from debate.ipc.schemas import RoutingMessage  # noqa: PLC0415
    def llm_call(s):
        return "Strong argument noted."
    routing = RouteTurn().run(_score(), AgentID.CON, llm_call)
    assert isinstance(routing, RoutingMessage)
    assert routing.target_agent == AgentID.CON


def test_route_turn_respects_next_agent():
    def llm_call(s):
        return "Feedback."
    routing = RouteTurn().run(_score(), AgentID.PRO, llm_call)
    assert routing.target_agent == AgentID.PRO


def test_route_turn_includes_llm_feedback():
    def llm_call(s):
        return "Outstanding rhetoric and solid citations."
    routing = RouteTurn().run(_score(), AgentID.CON, llm_call)
    assert "Outstanding" in routing.judge_feedback


# ---------------------------------------------------------------------------
# DeclareVerdict
# ---------------------------------------------------------------------------

def test_declare_verdict_names_winner():
    pro_scores = [_score(AgentID.PRO, logic=0.9, citation=0.8, rhetoric=0.8)]
    con_scores = [_score(AgentID.CON, logic=0.5, citation=0.4, rhetoric=0.4)]
    verdict = DeclareVerdict().run(pro_scores, con_scores)
    assert verdict.winner == AgentID.PRO


def test_declare_verdict_con_wins_when_higher():
    pro_scores = [_score(AgentID.PRO, logic=0.4, citation=0.3, rhetoric=0.3)]
    con_scores = [_score(AgentID.CON, logic=0.9, citation=0.9, rhetoric=0.9)]
    verdict = DeclareVerdict().run(pro_scores, con_scores)
    assert verdict.winner == AgentID.CON


def test_declare_verdict_scores_differ():
    pro_scores = [_score(AgentID.PRO, logic=0.8, citation=0.7, rhetoric=0.6)]
    con_scores = [_score(AgentID.CON, logic=0.5, citation=0.4, rhetoric=0.3)]
    verdict = DeclareVerdict().run(pro_scores, con_scores)
    vals = list(verdict.scores.values())
    assert vals[0] != vals[1]


def test_declare_verdict_tie_breaker_fires():
    # Equal weighted scores → tie-breaker must pick a winner
    pro_scores = [PersuasionScore(AgentID.PRO, 1, 0.7, 0.7, 0.7)]
    con_scores = [PersuasionScore(AgentID.CON, 1, 0.7, 0.7, 0.7)]
    verdict = DeclareVerdict().run(pro_scores, con_scores)
    assert verdict.winner in (AgentID.PRO, AgentID.CON)
    vals = list(verdict.scores.values())
    assert vals[0] != vals[1]


def test_declare_verdict_raises_on_empty_pro_scores():
    with pytest.raises(InsufficientDataError):
        DeclareVerdict().run([], [_score(AgentID.CON)])


def test_declare_verdict_raises_on_empty_con_scores():
    with pytest.raises(InsufficientDataError):
        DeclareVerdict().run([_score(AgentID.PRO)], [])


def test_declare_verdict_justification_length():
    pro_scores = [_score(AgentID.PRO, logic=0.8, citation=0.7, rhetoric=0.8)]
    con_scores = [_score(AgentID.CON, logic=0.5, citation=0.5, rhetoric=0.5)]
    verdict = DeclareVerdict().run(pro_scores, con_scores)
    assert len(verdict.justification) >= 50
