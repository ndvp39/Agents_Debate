"""Tests for debate.agents.judge.judge_agent — TDD RED phase."""

import json
from io import BytesIO

import pytest

from debate.agents.judge.judge_agent import JudgeAgent
from debate.ipc.schemas import ArgumentMessage
from debate.shared.constants import AgentID, MessageType
from debate.shared.exceptions import InsufficientDataError

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _evaluate_llm(argument, citations):
    return {"logical_consistency": 0.8, "citation_strength": 0.7, "rhetoric_quality": 0.6}


def _route_llm(score):
    return "Strong argument with solid citations and clear rhetoric."


def _make_judge(stdout_buf=None):
    buf = stdout_buf if stdout_buf is not None else BytesIO()
    agent = JudgeAgent(evaluate_llm=_evaluate_llm, route_llm=_route_llm, stdout=buf)
    return agent, buf


def _arg(agent_id=AgentID.PRO, round_=1, argument="AI creates more jobs.", citations=None):
    return ArgumentMessage(
        agent_id=agent_id,
        round=round_,
        argument=argument,
        citations=citations or ["MIT Study 2024: AI net job creation."],
    )


# ---------------------------------------------------------------------------
# No internet access
# ---------------------------------------------------------------------------

def test_no_web_search_tool_in_skills():
    agent, _ = _make_judge()
    skill_types = [type(s).__name__ for s in agent._skills]
    assert "WebSearchTool" not in skill_types


def test_judge_has_exactly_four_skills():
    agent, _ = _make_judge()
    assert len(agent._skills) == 4


# ---------------------------------------------------------------------------
# process_argument — valid argument → routing
# ---------------------------------------------------------------------------

def test_process_valid_argument_sends_routing():
    agent, buf = _make_judge()
    agent.process_argument(_arg())
    buf.seek(0)
    msg = json.loads(buf.read().decode("utf-8").strip())
    assert msg["message_type"] == MessageType.ROUTING


def test_process_valid_argument_routes_to_con():
    agent, buf = _make_judge()
    agent.process_argument(_arg(agent_id=AgentID.PRO))
    buf.seek(0)
    msg = json.loads(buf.read().decode("utf-8").strip())
    assert msg["target_agent"] == AgentID.CON


def test_process_valid_con_argument_routes_to_pro():
    agent, buf = _make_judge()
    agent.process_argument(_arg(agent_id=AgentID.CON))
    buf.seek(0)
    msg = json.loads(buf.read().decode("utf-8").strip())
    assert msg["target_agent"] == AgentID.PRO


# ---------------------------------------------------------------------------
# process_argument — agreement phrase → reprimand
# ---------------------------------------------------------------------------

def test_agreement_phrase_sends_reprimand():
    agent, buf = _make_judge()
    bad_arg = ArgumentMessage(
        agent_id=AgentID.PRO, round=1,
        argument="I agree with your point about employment.",
        citations=["Source."],
    )
    agent.process_argument(bad_arg)
    buf.seek(0)
    msg = json.loads(buf.read().decode("utf-8").strip())
    assert msg["message_type"] == MessageType.REPRIMAND
    assert msg["target_agent"] == AgentID.PRO


# ---------------------------------------------------------------------------
# process_argument — score accumulation
# ---------------------------------------------------------------------------

def test_valid_argument_accumulates_score():
    agent, _ = _make_judge()
    agent.process_argument(_arg(agent_id=AgentID.PRO))
    assert len(agent._scores[AgentID.PRO]) == 1


def test_reprimand_does_not_accumulate_score():
    agent, _ = _make_judge()
    bad_arg = ArgumentMessage(
        agent_id=AgentID.PRO, round=1,
        argument="You make a good point about technology.",
        citations=["Source."],
    )
    agent.process_argument(bad_arg)
    assert len(agent._scores[AgentID.PRO]) == 0


def test_multiple_rounds_accumulate_scores():
    agent, _ = _make_judge()
    agent.process_argument(_arg(AgentID.PRO, round_=1))
    agent.process_argument(_arg(AgentID.CON, round_=1))
    assert len(agent._scores[AgentID.PRO]) == 1
    assert len(agent._scores[AgentID.CON]) == 1


# ---------------------------------------------------------------------------
# declare_verdict
# ---------------------------------------------------------------------------

def test_declare_verdict_sends_verdict_message():
    agent, buf = _make_judge()
    agent.process_argument(_arg(AgentID.PRO, round_=1))
    agent.process_argument(_arg(AgentID.CON, round_=1))
    agent.declare_verdict()
    # verdict is the last JSON line written
    buf.seek(0)
    lines = [ln for ln in buf.read().decode("utf-8").splitlines() if ln.strip()]
    verdict = json.loads(lines[-1])
    assert verdict["message_type"] == MessageType.VERDICT


def test_declare_verdict_no_ties():
    agent, buf = _make_judge()
    agent.process_argument(_arg(AgentID.PRO, round_=1))
    agent.process_argument(_arg(AgentID.CON, round_=1))
    agent.declare_verdict()
    buf.seek(0)
    lines = [ln for ln in buf.read().decode("utf-8").splitlines() if ln.strip()]
    verdict = json.loads(lines[-1])
    vals = list(verdict["scores"].values())
    assert vals[0] != vals[1]


def test_declare_verdict_raises_before_any_round():
    agent, _ = _make_judge()
    with pytest.raises(InsufficientDataError):
        agent.declare_verdict()
