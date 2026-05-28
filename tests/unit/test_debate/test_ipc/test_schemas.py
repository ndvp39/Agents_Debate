"""Tests for debate.ipc.schemas — written before implementation (TDD RED)."""

import pytest

from debate.ipc.schemas import (
    ArgumentMessage,
    ReprimandMessage,
    RoutingMessage,
    VerdictMessage,
    message_from_dict,
)
from debate.shared.constants import AgentID, MessageType
from debate.shared.exceptions import IPCSchemaError

# ---------------------------------------------------------------------------
# RoutingMessage
# ---------------------------------------------------------------------------

def test_routing_from_dict_valid():
    data = {
        "message_type": MessageType.ROUTING,
        "target_agent": AgentID.PRO,
        "judge_feedback": "Strong point.",
        "prompt_for_next": "Counter the claim.",
    }
    msg = RoutingMessage.from_dict(data)
    assert msg.target_agent == AgentID.PRO
    assert msg.prompt_for_next == "Counter the claim."


def test_routing_missing_target_raises():
    with pytest.raises(IPCSchemaError):
        RoutingMessage.from_dict({"message_type": MessageType.ROUTING, "prompt_for_next": "x"})


def test_routing_missing_prompt_raises():
    with pytest.raises(IPCSchemaError):
        RoutingMessage.from_dict({"message_type": MessageType.ROUTING, "target_agent": AgentID.PRO})


def test_routing_to_dict_roundtrip():
    msg = RoutingMessage(
        target_agent=AgentID.CON,
        judge_feedback="Good.",
        prompt_for_next="Your turn.",
        previous_argument="The opponent's full argument prose...",
    )
    parsed = message_from_dict(msg.to_dict())
    assert parsed.target_agent == AgentID.CON
    assert parsed.previous_argument == "The opponent's full argument prose..."


def test_routing_previous_argument_defaults_empty():
    msg = RoutingMessage(
        target_agent=AgentID.PRO,
        judge_feedback="",
        prompt_for_next="Open the debate.",
    )
    assert msg.previous_argument == ""
    assert msg.to_dict()["previous_argument"] == ""


def test_routing_previous_argument_survives_from_dict():
    data = {
        "message_type": MessageType.ROUTING,
        "target_agent": AgentID.PRO,
        "judge_feedback": "Strong point.",
        "prompt_for_next": "Counter the claim.",
        "previous_argument": "Con's full round-1 argument with citations.",
    }
    msg = RoutingMessage.from_dict(data)
    assert msg.previous_argument == "Con's full round-1 argument with citations."


# ---------------------------------------------------------------------------
# ReprimandMessage
# ---------------------------------------------------------------------------

def test_reprimand_from_dict_valid():
    data = {
        "message_type": MessageType.REPRIMAND,
        "target_agent": AgentID.PRO,
        "reprimand_issued": True,
        "prompt_for_next": "Rewrite with citations.",
    }
    msg = ReprimandMessage.from_dict(data)
    assert msg.reprimand_issued is True


def test_reprimand_missing_target_raises():
    with pytest.raises(IPCSchemaError):
        ReprimandMessage.from_dict({
            "message_type": MessageType.REPRIMAND,
            "prompt_for_next": "Rewrite.",
        })


def test_reprimand_issued_false_raises():
    with pytest.raises(IPCSchemaError):
        ReprimandMessage(
            target_agent=AgentID.PRO,
            prompt_for_next="Rewrite.",
            reprimand_issued=False,
        )


def test_reprimand_to_dict_roundtrip():
    msg = ReprimandMessage(target_agent=AgentID.CON, prompt_for_next="Try again.")
    assert message_from_dict(msg.to_dict()).target_agent == AgentID.CON


# ---------------------------------------------------------------------------
# VerdictMessage
# ---------------------------------------------------------------------------

def test_verdict_from_dict_valid():
    data = {
        "message_type": MessageType.VERDICT,
        "winner": AgentID.PRO,
        "scores": {AgentID.PRO: 85, AgentID.CON: 72},
        "justification": "Agent_Pro consistently provided stronger evidence and rhetoric across all 10 rounds.",
    }
    msg = VerdictMessage.from_dict(data)
    assert msg.winner == AgentID.PRO
    assert msg.scores[AgentID.PRO] == 85


def test_verdict_equal_scores_raises():
    with pytest.raises(IPCSchemaError, match="ties"):
        VerdictMessage(
            winner=AgentID.PRO,
            scores={AgentID.PRO: 75, AgentID.CON: 75},
            justification="A" * 60,
        )


def test_verdict_winner_not_in_scores_raises():
    with pytest.raises(IPCSchemaError):
        VerdictMessage(
            winner="Agent_Unknown",
            scores={AgentID.PRO: 80, AgentID.CON: 70},
            justification="A" * 60,
        )


def test_verdict_short_justification_raises():
    with pytest.raises(IPCSchemaError):
        VerdictMessage(
            winner=AgentID.CON,
            scores={AgentID.PRO: 70, AgentID.CON: 80},
            justification="Too short.",
        )


def test_verdict_to_dict_roundtrip():
    msg = VerdictMessage(
        winner=AgentID.CON,
        scores={AgentID.PRO: 70, AgentID.CON: 80},
        justification="Agent_Con demonstrated superior rhetoric and fallacy detection across all debate rounds.",
    )
    d = msg.to_dict()
    assert d["winner"] == AgentID.CON
    assert d["scores"][AgentID.CON] == 80


# ---------------------------------------------------------------------------
# ArgumentMessage
# ---------------------------------------------------------------------------

def test_argument_from_dict_valid():
    data = {
        "message_type": MessageType.ARGUMENT,
        "agent_id": AgentID.PRO,
        "round": 1,
        "argument": "AI creates more jobs than it destroys.",
        "citations": ["MIT Study 2024: AI net job creation."],
    }
    msg = ArgumentMessage.from_dict(data)
    assert msg.round == 1
    assert len(msg.citations) == 1


def test_argument_empty_citations_raises():
    with pytest.raises(IPCSchemaError, match="citations"):
        ArgumentMessage(
            agent_id=AgentID.PRO, round=1,
            argument="Some argument.", citations=[],
        )


def test_argument_round_zero_raises():
    with pytest.raises(IPCSchemaError, match="round"):
        ArgumentMessage(
            agent_id=AgentID.PRO, round=0,
            argument="Arg.", citations=["Source."],
        )


def test_argument_to_dict_roundtrip():
    msg = ArgumentMessage(
        agent_id=AgentID.CON, round=3,
        argument="Counter-argument.", citations=["BBC 2024."],
    )
    d = msg.to_dict()
    assert d["round"] == 3
    assert d["citations"] == ["BBC 2024."]


# ---------------------------------------------------------------------------
# message_from_dict factory
# ---------------------------------------------------------------------------

def test_factory_routing():
    d = {"message_type": MessageType.ROUTING, "target_agent": AgentID.PRO,
         "judge_feedback": "ok", "prompt_for_next": "go"}
    assert isinstance(message_from_dict(d), RoutingMessage)


def test_factory_reprimand():
    d = {"message_type": MessageType.REPRIMAND, "target_agent": AgentID.CON,
         "reprimand_issued": True, "prompt_for_next": "retry"}
    assert isinstance(message_from_dict(d), ReprimandMessage)


def test_factory_verdict():
    d = {"message_type": MessageType.VERDICT, "winner": AgentID.PRO,
         "scores": {AgentID.PRO: 80, AgentID.CON: 70},
         "justification": "Agent_Pro showed superior reasoning and rhetoric throughout all debate rounds."}
    assert isinstance(message_from_dict(d), VerdictMessage)


def test_factory_argument():
    d = {"message_type": MessageType.ARGUMENT, "agent_id": AgentID.PRO,
         "round": 2, "argument": "Arg.", "citations": ["Source."]}
    assert isinstance(message_from_dict(d), ArgumentMessage)


def test_factory_unknown_type_raises():
    with pytest.raises(IPCSchemaError, match="Unknown"):
        message_from_dict({"message_type": "unknown"})
