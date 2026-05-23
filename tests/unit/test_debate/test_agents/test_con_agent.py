"""Tests for debate.agents.debaters.con_agent — TDD RED phase."""

import json
from io import BytesIO
from unittest.mock import MagicMock

from debate.agents.debaters.base_debater import BaseDebater
from debate.agents.debaters.con_agent import ConAgent
from debate.shared.constants import AgentID, MessageType, Stance


def _make_con(topic="AI and jobs"):
    buf = BytesIO()
    agent = ConAgent(
        topic=topic,
        llm_call=MagicMock(return_value="Con argument text."),
        search_call=MagicMock(return_value=["Source B."]),
        stdin=BytesIO(),
        stdout=buf,
    )
    return agent, buf


def test_con_agent_is_base_debater():
    agent, _ = _make_con()
    assert isinstance(agent, BaseDebater)


def test_con_agent_id_is_agent_con():
    agent, _ = _make_con()
    assert agent.agent_id == AgentID.CON


def test_con_stance_is_against():
    agent, _ = _make_con()
    assert "AGAINST" in agent.STANCE.upper()


def test_con_stance_matches_constant():
    agent, _ = _make_con()
    assert agent.STANCE == Stance.CON


def test_con_respond_sends_argument():
    agent, buf = _make_con()
    agent.respond({"message_type": MessageType.ROUTING, "target_agent": AgentID.CON,
                   "judge_feedback": "Noted.", "prompt_for_next": "Your turn."})
    buf.seek(0)
    msg = json.loads(buf.read().decode("utf-8").strip())
    assert msg["message_type"] == MessageType.ARGUMENT
    assert msg["agent_id"] == AgentID.CON
