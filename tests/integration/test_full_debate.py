"""Integration test — full debate pipeline with mocked LLMs (no real API calls)."""

import io
import json

from debate.agents.debaters.con_agent import ConAgent
from debate.agents.debaters.pro_agent import ProAgent
from debate.agents.judge.judge_agent import JudgeAgent
from debate.ipc.schemas import ArgumentMessage
from debate.shared.constants import AgentID, MessageType


# ---------------------------------------------------------------------------
# Mocked LLMs (no network, no API key required)
# ---------------------------------------------------------------------------

def _mock_llm(prompt: str) -> str:
    return "This is a well-reasoned argument supported by concrete evidence."


def _mock_evaluate(argument: str, citations: list) -> dict:
    return {"logical_consistency": 0.7, "citation_strength": 0.6, "rhetoric_quality": 0.8}


def _mock_route(score) -> str:
    return "Strong argument presented. Please continue with your rebuttal."


def _mock_search(query: str) -> list:
    return ["Evidence A: Studies show measurable impact.", "Evidence B: Expert consensus supports."]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_pro(topic: str):
    out = io.BytesIO()
    agent = ProAgent(topic=topic, llm_call=_mock_llm, search_call=_mock_search,
                     stdin=io.BytesIO(), stdout=out)
    return agent, out


def _make_con(topic: str):
    out = io.BytesIO()
    agent = ConAgent(topic=topic, llm_call=_mock_llm, search_call=_mock_search,
                     stdin=io.BytesIO(), stdout=out)
    return agent, out


def _make_judge():
    out = io.BytesIO()
    agent = JudgeAgent(evaluate_llm=_mock_evaluate, route_llm=_mock_route,
                       stdin=io.BytesIO(), stdout=out)
    return agent, out


def _pop(buf: io.BytesIO) -> dict:
    buf.seek(0)
    data = json.loads(buf.readline())
    buf.seek(0)
    buf.truncate(0)
    return data


def _run_debate(topic: str, rounds: int) -> tuple[list[dict], dict]:
    """Drive a full in-process debate; return (transcript, verdict_dict)."""
    pro, pro_out = _make_pro(topic)
    con, con_out = _make_con(topic)
    judge, judge_out = _make_judge()

    routing: dict = {
        "message_type": MessageType.ROUTING,
        "target_agent": AgentID.PRO,
        "judge_feedback": "",
        "prompt_for_next": f"You are arguing completely FOR: {topic}. Open the debate.",
    }

    current, current_out = pro, pro_out
    nxt, nxt_out = con, con_out
    transcript: list[dict] = []
    rounds_completed = 0

    while rounds_completed < rounds:
        current.respond(routing)
        arg_dict = _pop(current_out)
        transcript.append(arg_dict)

        judge.process_argument(ArgumentMessage.from_dict(arg_dict))
        judge_resp = _pop(judge_out)

        if judge_resp["message_type"] == MessageType.REPRIMAND:
            routing = judge_resp
        else:
            rounds_completed += 1
            transcript.append(judge_resp)
            current, current_out, nxt, nxt_out = nxt, nxt_out, current, current_out
            routing = judge_resp

    judge.declare_verdict()
    verdict = _pop(judge_out)
    transcript.append(verdict)
    return transcript, verdict


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_full_debate_2_rounds_produces_verdict():
    transcript, verdict = _run_debate("AI will replace human jobs", rounds=2)

    assert verdict["message_type"] == MessageType.VERDICT
    assert verdict["winner"] in (AgentID.PRO, AgentID.CON)
    scores = list(verdict["scores"].values())
    assert scores[0] != scores[1]
    assert len(verdict["justification"]) >= 50
    assert len(transcript) >= 5  # 2 args + 2 routings + 1 verdict minimum


def test_verdict_contains_both_agents_in_scores():
    _, verdict = _run_debate("Renewable energy is viable", rounds=2)

    assert AgentID.PRO in verdict["scores"]
    assert AgentID.CON in verdict["scores"]


def test_pro_argues_round_1_correctly():
    topic = "Technology improves society"
    pro, pro_out = _make_pro(topic)
    routing = {
        "message_type": MessageType.ROUTING,
        "target_agent": AgentID.PRO,
        "judge_feedback": "",
        "prompt_for_next": f"FOR: {topic}. Open the debate.",
    }
    pro.respond(routing)
    arg = _pop(pro_out)

    assert arg["message_type"] == MessageType.ARGUMENT
    assert arg["agent_id"] == AgentID.PRO
    assert arg["round"] == 1
    assert len(arg["citations"]) > 0


def test_con_argues_round_1_correctly():
    topic = "Technology improves society"
    con, con_out = _make_con(topic)
    routing = {
        "message_type": MessageType.ROUTING,
        "target_agent": AgentID.CON,
        "judge_feedback": "",
        "prompt_for_next": f"AGAINST: {topic}. Open.",
    }
    con.respond(routing)
    arg = _pop(con_out)

    assert arg["message_type"] == MessageType.ARGUMENT
    assert arg["agent_id"] == AgentID.CON
    assert arg["round"] == 1


def test_judge_scores_both_agents_after_full_debate():
    topic = "Universal basic income works"
    transcript, verdict = _run_debate(topic, rounds=2)

    pro_args = [m for m in transcript if m.get("agent_id") == AgentID.PRO]
    con_args = [m for m in transcript if m.get("agent_id") == AgentID.CON]
    assert len(pro_args) >= 1
    assert len(con_args) >= 1
