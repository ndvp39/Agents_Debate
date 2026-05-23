"""Tests for debate.shared.constants — written before implementation (TDD RED)."""

from debate.shared.constants import (
    MIN_JUSTIFICATION_LENGTH,
    REQUIRED_CONFIG_VERSION,
    SCORE_WEIGHT_CITATION,
    SCORE_WEIGHT_LOGIC,
    SCORE_WEIGHT_RHETORIC,
    AgentID,
    MessageType,
    Stance,
)


def test_message_type_routing():
    assert MessageType.ROUTING == "routing"


def test_message_type_reprimand():
    assert MessageType.REPRIMAND == "reprimand"


def test_message_type_verdict():
    assert MessageType.VERDICT == "verdict"


def test_message_type_argument():
    assert MessageType.ARGUMENT == "argument"


def test_agent_id_judge():
    assert AgentID.JUDGE == "Agent_Judge"


def test_agent_id_pro():
    assert AgentID.PRO == "Agent_Pro"


def test_agent_id_con():
    assert AgentID.CON == "Agent_Con"


def test_stance_pro_contains_for():
    assert "FOR" in Stance.PRO


def test_stance_con_contains_against():
    assert "AGAINST" in Stance.CON


def test_score_weights_sum_to_one():
    total = SCORE_WEIGHT_LOGIC + SCORE_WEIGHT_CITATION + SCORE_WEIGHT_RHETORIC
    assert abs(total - 1.0) < 1e-9


def test_score_weight_logic_dominant():
    assert SCORE_WEIGHT_LOGIC > SCORE_WEIGHT_CITATION
    assert SCORE_WEIGHT_LOGIC > SCORE_WEIGHT_RHETORIC


def test_score_weight_rhetoric_exists():
    assert 0.0 < SCORE_WEIGHT_RHETORIC < 1.0


def test_min_justification_length():
    assert MIN_JUSTIFICATION_LENGTH >= 50


def test_required_config_version_format():
    assert REQUIRED_CONFIG_VERSION == "1.00"
    assert isinstance(REQUIRED_CONFIG_VERSION, str)
