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
    # Distinguish "caller wants empty results" from "caller didn't specify" —
    # an empty list is falsy and the old `or` shortcut swallowed it.
    if search_results is None:
        search_results = ["Source A."]
    search_call = MagicMock(return_value=search_results)
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

def test_respond_with_no_search_results_uses_honest_marker():
    """Empty search must NOT fabricate a citation-looking string (the old
    `"Searched: <topic>"` stub). Use an honest, clearly-not-a-source marker."""
    agent, buf, *_ = _make_debater(search_results=[])
    agent.respond(_routing_msg())
    buf.seek(0)
    msg = json.loads(buf.read().decode("utf-8").strip())
    assert msg["message_type"] == MessageType.ARGUMENT
    assert len(msg["citations"]) == 1
    citation = msg["citations"][0]
    assert "no web sources retrieved" in citation.lower()
    assert "searched:" not in citation.lower()  # the old fabricated fallback


# ---------------------------------------------------------------------------
# _build_search_query — tethered to debate topic, capped under Tavily's 400-char limit
# ---------------------------------------------------------------------------

TOPIC = "Will artificial intelligence replace human jobs"


def test_build_search_query_both_empty_returns_empty():
    assert BaseDebater._build_search_query("", "") == ""
    assert BaseDebater._build_search_query(None, None) == ""
    assert BaseDebater._build_search_query("   ", "  ") == ""


def test_build_search_query_falls_back_to_topic_when_weakest_empty():
    assert BaseDebater._build_search_query(TOPIC, "") == TOPIC
    assert BaseDebater._build_search_query(TOPIC, None) == TOPIC


def test_build_search_query_leads_with_topic_then_weakest():
    out = BaseDebater._build_search_query(TOPIC, "reliance on the 'Luddite Fallacy'")
    assert out == f"{TOPIC} reliance on the 'Luddite Fallacy'"


def test_build_search_query_takes_first_sentence_of_weakest():
    weakest = (
        "The opponent relies on the Luddite Fallacy. They also cite outdated 2014 data. "
        "Furthermore, they ignore productivity research from 2024."
    )
    out = BaseDebater._build_search_query(TOPIC, weakest)
    assert out == f"{TOPIC} The opponent relies on the Luddite Fallacy"


def test_build_search_query_truncates_single_long_sentence():
    weakest = "a" * 500
    out = BaseDebater._build_search_query(TOPIC, weakest)
    # Topic prefix (47 chars) + " " + 250-char weakest cap = 298 chars total.
    assert out.startswith(f"{TOPIC} ")
    assert len(out) == len(TOPIC) + 1 + 250
    assert len(out) < 400


def test_build_search_query_always_under_400_chars_for_pathological_input():
    weakest = (
        "This is an extremely long single-sentence weakest-point output where the LLM "
        "rambled on about supporting points, hidden assumptions, falsified premises, "
        "and various rhetorical flourishes that should never end and definitely keep "
        "going far beyond what any reasonable search engine would accept as a query, "
        "extending well past 400 characters of continuous prose with no punctuation "
        "that could serve as a sentence boundary anywhere in this entire mess of words"
    )
    out = BaseDebater._build_search_query(TOPIC, weakest)
    assert len(out) < 400


def test_build_search_query_handles_newline_terminator():
    weakest = "Main claim about AI displacement\nSecondary point about retraining"
    out = BaseDebater._build_search_query(TOPIC, weakest)
    assert out == f"{TOPIC} Main claim about AI displacement"


def test_build_search_query_returns_weakest_only_when_topic_empty():
    out = BaseDebater._build_search_query("", "Just the weakest point")
    assert out == "Just the weakest point"


def test_respond_with_real_search_results_uses_them():
    agent, buf, *_ = _make_debater(search_results=[
        "AI Job Impact Study — https://example.org/study",
        "BLS 2024 Report — https://bls.gov/report",
    ])
    agent.respond(_routing_msg())
    buf.seek(0)
    msg = json.loads(buf.read().decode("utf-8").strip())
    assert "no web sources retrieved" not in " ".join(msg["citations"]).lower()
    assert any("example.org" in c for c in msg["citations"])
