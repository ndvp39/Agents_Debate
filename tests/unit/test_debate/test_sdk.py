"""Tests for debate.sdk.sdk — TDD RED phase."""

from unittest.mock import MagicMock

import pytest

from debate.sdk.sdk import DebateSDK
from debate.services.orchestrator import DebateResult
from debate.shared.constants import AgentID, MessageType
from debate.shared.exceptions import InsufficientDataError

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _result(topic="AI and jobs", rounds=2):
    return DebateResult(
        topic=topic,
        rounds_completed=rounds,
        transcript=[
            {"message_type": MessageType.ARGUMENT, "agent_id": AgentID.PRO},
            {"message_type": MessageType.ROUTING, "target_agent": AgentID.CON},
            {"message_type": MessageType.VERDICT, "winner": AgentID.PRO},
        ],
        verdict={
            "message_type": MessageType.VERDICT,
            "winner": AgentID.PRO,
            "scores": {AgentID.PRO: 80, AgentID.CON: 70},
            "justification": "Pro demonstrated superior rhetoric throughout.",
        },
        cost_summary={"total_tokens": 1500, "estimated_cost_usd": 0.05},
        reprimand_count=1,
    )


def _make_sdk(result=None):
    mock_orch = MagicMock()
    mock_orch.run.return_value = result or _result()
    mock_factory = MagicMock(return_value=(MagicMock(), MagicMock(), MagicMock()))
    mock_gatekeeper = MagicMock()
    mock_gatekeeper.get_queue_status.return_value = {"queue_depth": 0, "active": False}
    sdk = DebateSDK(
        orchestrator=mock_orch,
        process_factory=mock_factory,
        gatekeeper=mock_gatekeeper,
    )
    return sdk, mock_orch, mock_factory, mock_gatekeeper


# ---------------------------------------------------------------------------
# start_debate()
# ---------------------------------------------------------------------------

def test_start_debate_returns_debate_result():
    sdk, *_ = _make_sdk()
    result = sdk.start_debate("AI and jobs", 2)
    assert isinstance(result, DebateResult)


def test_start_debate_calls_orchestrator_run():
    sdk, mock_orch, mock_factory, _ = _make_sdk()
    sdk.start_debate("AI and jobs", 2)
    mock_orch.run.assert_called_once()


def test_start_debate_passes_topic_and_rounds():
    sdk, mock_orch, mock_factory, _ = _make_sdk()
    sdk.start_debate("Blockchain ethics", 5)
    call_args = mock_orch.run.call_args
    assert call_args.args[0] == "Blockchain ethics"
    assert call_args.args[1] == 5


def test_start_debate_spawns_three_processes():
    sdk, _, mock_factory, _ = _make_sdk()
    sdk.start_debate("AI and jobs", 2)
    mock_factory.assert_called_once()
    pro, con, judge = mock_factory.return_value
    assert pro is not None
    assert con is not None
    assert judge is not None


# ---------------------------------------------------------------------------
# get_transcript()
# ---------------------------------------------------------------------------

def test_get_transcript_returns_list():
    sdk, *_ = _make_sdk()
    sdk.start_debate("AI and jobs", 2)
    transcript = sdk.get_transcript()
    assert isinstance(transcript, list)


def test_get_transcript_matches_result():
    sdk, *_ = _make_sdk()
    sdk.start_debate("AI and jobs", 2)
    assert sdk.get_transcript() == sdk._result.transcript


def test_get_transcript_before_debate_raises():
    sdk, *_ = _make_sdk()
    with pytest.raises(InsufficientDataError):
        sdk.get_transcript()


# ---------------------------------------------------------------------------
# get_verdict()
# ---------------------------------------------------------------------------

def test_get_verdict_returns_dict():
    sdk, *_ = _make_sdk()
    sdk.start_debate("AI and jobs", 2)
    verdict = sdk.get_verdict()
    assert isinstance(verdict, dict)
    assert "winner" in verdict


def test_get_verdict_winner_is_valid_agent():
    sdk, *_ = _make_sdk()
    sdk.start_debate("AI and jobs", 2)
    assert sdk.get_verdict()["winner"] in (AgentID.PRO, AgentID.CON)


def test_get_verdict_before_debate_raises():
    sdk, *_ = _make_sdk()
    with pytest.raises(InsufficientDataError):
        sdk.get_verdict()


# ---------------------------------------------------------------------------
# get_cost_summary()
# ---------------------------------------------------------------------------

def test_get_cost_summary_returns_dict():
    sdk, *_ = _make_sdk()
    sdk.start_debate("AI and jobs", 2)
    summary = sdk.get_cost_summary()
    assert isinstance(summary, dict)


def test_get_cost_summary_before_debate_returns_empty():
    sdk, *_ = _make_sdk()
    assert sdk.get_cost_summary() == {}


# ---------------------------------------------------------------------------
# get_queue_status()
# ---------------------------------------------------------------------------

def test_get_queue_status_returns_dict():
    sdk, *_ = _make_sdk()
    status = sdk.get_queue_status()
    assert isinstance(status, dict)


def test_get_queue_status_delegates_to_gatekeeper():
    sdk, _, _, mock_gk = _make_sdk()
    sdk.get_queue_status()
    mock_gk.get_queue_status.assert_called_once()


def test_get_queue_status_without_gatekeeper_returns_empty():
    mock_orch = MagicMock()
    mock_orch.run.return_value = _result()
    sdk = DebateSDK(orchestrator=mock_orch, process_factory=MagicMock(return_value=(MagicMock(), MagicMock(), MagicMock())))
    assert sdk.get_queue_status() == {}
