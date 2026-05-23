"""Tests for debate.agents.debaters.pro_agent — TDD RED phase."""

import json
from io import BytesIO
from unittest.mock import MagicMock

from debate.agents.debaters.base_debater import BaseDebater
from debate.agents.debaters.pro_agent import ProAgent
from debate.shared.constants import AgentID, MessageType, Stance


def _make_pro(topic="AI and jobs"):
    buf = BytesIO()
    agent = ProAgent(
        topic=topic,
        llm_call=MagicMock(return_value="Pro argument text."),
        search_call=MagicMock(return_value=["Source A."]),
        stdin=BytesIO(),
        stdout=buf,
    )
    return agent, buf


def test_pro_agent_is_base_debater():
    agent, _ = _make_pro()
    assert isinstance(agent, BaseDebater)


def test_pro_agent_id_is_agent_pro():
    agent, _ = _make_pro()
    assert agent.agent_id == AgentID.PRO


def test_pro_stance_is_for():
    agent, _ = _make_pro()
    assert "FOR" in agent.STANCE.upper()


def test_pro_stance_matches_constant():
    agent, _ = _make_pro()
    assert agent.STANCE == Stance.PRO


def test_pro_respond_sends_argument():
    agent, buf = _make_pro()
    agent.respond({"message_type": MessageType.ROUTING, "target_agent": AgentID.PRO,
                   "judge_feedback": "Good.", "prompt_for_next": "Your turn."})
    buf.seek(0)
    msg = json.loads(buf.read().decode("utf-8").strip())
    assert msg["message_type"] == MessageType.ARGUMENT
    assert msg["agent_id"] == AgentID.PRO
