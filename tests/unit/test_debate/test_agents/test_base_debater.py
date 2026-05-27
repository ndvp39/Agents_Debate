"""Tests for debate.agents.debaters.base_debater — drives the SkillLoader pipeline."""

import json
from io import BytesIO
from pathlib import Path
from unittest.mock import MagicMock

from debate.agents.debaters.base_debater import BaseDebater
from debate.shared.constants import AgentID, MessageType, Stance
from debate.skills.loader import SkillLoader

SKILLS_ROOT = Path(__file__).resolve().parents[4] / "src" / "debate" / "skills"


# ---------------------------------------------------------------------------
# Concrete subclass for testing (BaseDebater is abstract)
# ---------------------------------------------------------------------------

class _ProDebater(BaseDebater):
    STANCE = Stance.PRO


def _make_debater(llm_response="Argument text.", search_results=None):
    buf = BytesIO()
    llm_call = MagicMock(return_value=llm_response)
    search_call = MagicMock(return_value=search_results or ["Source A."])
    agent = _ProDebater(
        topic="AI and jobs",
        llm_call=llm_call,
        search_call=search_call,
        stdin=BytesIO(),
        stdout=buf,
        skills=SkillLoader(SKILLS_ROOT),
    )
    return agent, buf, llm_call, search_call


def _routing_msg(prompt="Your turn.", feedback="Good."):
    return {
        "message_type": MessageType.ROUTING,
        "target_agent": AgentID.PRO,
        "judge_feedback": feedback,
        "prompt_for_next": prompt,
    }


# ---------------------------------------------------------------------------
# SkillLoader plumbing
# ---------------------------------------------------------------------------

def test_skill_loader_is_injected():
    agent, *_ = _make_debater()
    assert isinstance(agent._skills, SkillLoader)


def test_web_search_tool_is_held_outside_skill_loader():
    agent, *_ = _make_debater()
    from debate.agents.debaters.web_search_tool import WebSearchTool
    assert isinstance(agent._web_search, WebSearchTool)


# ---------------------------------------------------------------------------
# respond() — round 1 output
# ---------------------------------------------------------------------------

def test_round_1_sends_argument_message():
    agent, buf, *_ = _make_debater()
    agent.respond(_routing_msg())
    buf.seek(0)
    msg = json.loads(buf.read().decode("utf-8").strip())
    assert msg["message_type"] == MessageType.ARGUMENT


def test_round_1_argument_has_citations():
    agent, buf, *_ = _make_debater(search_results=["Source A."])
    agent.respond(_routing_msg())
    buf.seek(0)
    msg = json.loads(buf.read().decode("utf-8").strip())
    assert len(msg["citations"]) >= 1


def test_round_1_argument_round_number_is_1():
    agent, buf, *_ = _make_debater()
    agent.respond(_routing_msg())
    buf.seek(0)
    msg = json.loads(buf.read().decode("utf-8").strip())
    assert msg["round"] == 1


# ---------------------------------------------------------------------------
# respond() — round 2+ output
# ---------------------------------------------------------------------------

def test_round_2_sends_argument_message():
    agent, buf, *_ = _make_debater()
    agent.respond(_routing_msg())  # round 1
    buf.seek(0)
    buf.read()
    buf.seek(0)
    buf.truncate(0)

    agent.respond(_routing_msg("Opponent argument for round 2."))
    buf.seek(0)
    msg = json.loads(buf.read().decode("utf-8").strip())
    assert msg["message_type"] == MessageType.ARGUMENT
    assert msg["round"] == 2


def test_round_increments_after_each_respond():
    agent, *_ = _make_debater()
    agent.respond(_routing_msg())
    assert agent._round == 1
    agent.respond(_routing_msg())
    assert agent._round == 2


# ---------------------------------------------------------------------------
# Anti-sycophancy
# ---------------------------------------------------------------------------

def test_anti_sycophancy_injected_in_llm_prompt():
    agent, _, llm_call, _ = _make_debater()
    agent.respond(_routing_msg())
    assert llm_call.called
    all_prompts = " ".join(str(c) for c in llm_call.call_args_list)
    assert any(kw in all_prompts.upper() for kw in ("FORBIDDEN", "NEVER AGREE", "DIRECTIVE", "STRICTLY"))


# ---------------------------------------------------------------------------
# SKILL.md content actually flows through to the LLM
# ---------------------------------------------------------------------------

def test_craft_opening_template_text_reaches_llm_on_round_1():
    agent, _, llm_call, _ = _make_debater()
    agent.respond(_routing_msg())
    all_prompts = " ".join(str(c) for c in llm_call.call_args_list)
    # Phrase taken verbatim from craft_opening/SKILL.md instructions:
    assert "Deliver the strongest possible opening statement" in all_prompts


# ---------------------------------------------------------------------------
# Graceful handling when search returns nothing
# ---------------------------------------------------------------------------

def test_respond_with_no_search_results_still_sends_argument():
    agent, buf, *_ = _make_debater(search_results=[])
    agent.respond(_routing_msg())
    buf.seek(0)
    msg = json.loads(buf.read().decode("utf-8").strip())
    assert msg["message_type"] == MessageType.ARGUMENT
    assert len(msg["citations"]) >= 1  # fallback citation added
