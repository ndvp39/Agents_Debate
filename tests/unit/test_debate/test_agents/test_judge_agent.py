"""Tests for debate.agents.judge.judge_agent — drives the SkillLoader pipeline."""

import json
from io import BytesIO
from pathlib import Path

import pytest

from debate.agents.judge.judge_agent import JudgeAgent
from debate.ipc.schemas import ArgumentMessage
from debate.shared.constants import AgentID, MessageType
from debate.shared.exceptions import InsufficientDataError
from debate.skills.loader import SkillLoader

SKILLS_ROOT = Path(__file__).resolve().parents[4] / "src" / "debate" / "skills"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _evaluate_llm(prompt: str):
    return {"logical_consistency": 0.8, "citation_strength": 0.7, "rhetoric_quality": 0.6}


def _route_llm(prompt: str):
    return "Strong argument with solid citations and clear rhetoric."


def _verdict_llm(prompt: str):
    return (
        "KEY CLASHES — Round 1 was decisive. FEEDBACK ADHERENCE — Pro adapted well. "
        "SCORING BREAKDOWN — Logic dominated. FINAL CONCLUSION — Pro wins on logic."
    )


def _make_judge(stdout_buf=None, *, verdict_llm=_verdict_llm):
    buf = stdout_buf if stdout_buf is not None else BytesIO()
    agent = JudgeAgent(
        evaluate_llm=_evaluate_llm,
        route_llm=_route_llm,
        verdict_llm=verdict_llm,
        stdout=buf,
        skills=SkillLoader(SKILLS_ROOT),
    )
    return agent, buf


def _arg(agent_id=AgentID.PRO, round_=1, argument="AI creates more jobs.", citations=None):
    return ArgumentMessage(
        agent_id=agent_id,
        round=round_,
        argument=argument,
        citations=citations or ["MIT Study 2024: AI net job creation."],
    )


# ---------------------------------------------------------------------------
# SkillLoader plumbing
# ---------------------------------------------------------------------------

def test_skill_loader_is_injected():
    agent, _ = _make_judge()
    assert isinstance(agent._skills, SkillLoader)


def test_judge_has_no_web_search_capability():
    agent, _ = _make_judge()
    assert not hasattr(agent, "_web_search")


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


def test_routing_carries_speaker_argument_as_previous_argument():
    """The next debater must receive the full argument text it has to respond to,
    not just the handoff string. Verifies the previous_argument wiring."""
    agent, buf = _make_judge()
    arg_text = "Agent_Pro's actual round-1 prose with specific statistics and citations."
    agent.process_argument(_arg(agent_id=AgentID.PRO, argument=arg_text))
    buf.seek(0)
    msg = json.loads(buf.read().decode("utf-8").strip())
    assert msg["message_type"] == MessageType.ROUTING
    assert msg["target_agent"] == AgentID.CON
    assert msg["previous_argument"] == arg_text
    # And confirm it is NOT the handoff string.
    assert "It is your turn now" not in msg["previous_argument"]


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


def test_declare_verdict_uses_llm_justification():
    agent, buf = _make_judge()
    agent.process_argument(_arg(AgentID.PRO, round_=1))
    agent.process_argument(_arg(AgentID.CON, round_=1))
    agent.declare_verdict()
    buf.seek(0)
    lines = [ln for ln in buf.read().decode("utf-8").splitlines() if ln.strip()]
    verdict = json.loads(lines[-1])
    assert "KEY CLASHES" in verdict["justification"]
    assert "FINAL CONCLUSION" in verdict["justification"]


def test_declare_verdict_without_llm_uses_score_context():
    agent, buf = _make_judge(verdict_llm=None)
    agent.process_argument(_arg(AgentID.PRO, round_=1))
    agent.process_argument(_arg(AgentID.CON, round_=1))
    agent.declare_verdict()
    buf.seek(0)
    lines = [ln for ln in buf.read().decode("utf-8").splitlines() if ln.strip()]
    verdict = json.loads(lines[-1])
    assert "RESULT" in verdict["justification"]
