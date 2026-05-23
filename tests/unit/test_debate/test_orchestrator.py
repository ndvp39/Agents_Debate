"""Tests for debate.services.orchestrator — TDD RED phase."""

from unittest.mock import MagicMock

from debate.services.orchestrator import DebateOrchestrator, DebateResult
from debate.shared.constants import AgentID, MessageType

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _proc():
    return MagicMock()


def _arg(agent_id=AgentID.PRO, round_=1):
    return {
        "message_type": MessageType.ARGUMENT,
        "agent_id": agent_id,
        "round": round_,
        "argument": "AI creates jobs.",
        "citations": ["Source A."],
    }


def _routing(target=AgentID.CON):
    return {
        "message_type": MessageType.ROUTING,
        "target_agent": target,
        "judge_feedback": "Good argument.",
        "prompt_for_next": f"It is your turn, {target}.",
    }


def _reprimand(target=AgentID.PRO):
    return {
        "message_type": MessageType.REPRIMAND,
        "target_agent": target,
        "reprimand_issued": True,
        "prompt_for_next": "Rewrite with citations.",
    }


def _verdict():
    return {
        "message_type": MessageType.VERDICT,
        "winner": AgentID.PRO,
        "scores": {AgentID.PRO: 80, AgentID.CON: 70},
        "justification": "Pro demonstrated superior reasoning and rhetoric throughout all rounds.",
    }


def _make_channel(receive_sequence):
    channel = MagicMock()
    channel.receive.side_effect = receive_sequence
    return channel


def _run(rounds=2, receive_sequence=None):
    if receive_sequence is None:
        # Default: N rounds without reprimands + verdict
        seq = []
        for i in range(rounds):
            speaker = AgentID.PRO if i % 2 == 0 else AgentID.CON
            seq.append(_arg(speaker, i + 1))
            seq.append(_routing(AgentID.CON if i % 2 == 0 else AgentID.PRO))
        seq.append(_verdict())
        receive_sequence = seq
    channel = _make_channel(receive_sequence)
    orch = DebateOrchestrator(channel=channel)
    result = orch.run("AI and jobs", rounds, _proc(), _proc(), _proc())
    return result, channel


# ---------------------------------------------------------------------------
# DebateResult structure
# ---------------------------------------------------------------------------

def test_result_is_debate_result():
    result, _ = _run(rounds=2)
    assert isinstance(result, DebateResult)


def test_result_rounds_completed():
    result, _ = _run(rounds=2)
    assert result.rounds_completed == 2


def test_result_topic_preserved():
    channel = _make_channel([_arg(), _routing(), _arg(AgentID.CON), _routing(AgentID.PRO), _verdict()])
    orch = DebateOrchestrator(channel=channel)
    result = orch.run("AI and jobs", 2, _proc(), _proc(), _proc())
    assert result.topic == "AI and jobs"


def test_result_verdict_present():
    result, _ = _run(rounds=2)
    assert result.verdict["winner"] == AgentID.PRO


def test_result_reprimand_count_zero_when_no_reprimands():
    result, _ = _run(rounds=2)
    assert result.reprimand_count == 0


# ---------------------------------------------------------------------------
# Transcript
# ---------------------------------------------------------------------------

def test_transcript_contains_arguments_and_routings():
    result, _ = _run(rounds=2)
    types = [m["message_type"] for m in result.transcript]
    assert MessageType.ARGUMENT in types
    assert MessageType.ROUTING in types


def test_transcript_contains_verdict():
    result, _ = _run(rounds=2)
    types = [m["message_type"] for m in result.transcript]
    assert MessageType.VERDICT in types


def test_transcript_length_for_2_rounds():
    result, _ = _run(rounds=2)
    # 2 arguments + 2 routings + 1 verdict = 5
    assert len(result.transcript) == 5


# ---------------------------------------------------------------------------
# Reprimand handling
# ---------------------------------------------------------------------------

def test_reprimand_does_not_advance_round():
    # round 1: arg from pro, reprimand, arg from pro again, routing, arg from con, routing, verdict
    seq = [
        _arg(AgentID.PRO, 1),   # first attempt
        _reprimand(AgentID.PRO),
        _arg(AgentID.PRO, 1),   # retry
        _routing(AgentID.CON),  # round 1 done
        _arg(AgentID.CON, 2),
        _routing(AgentID.PRO),  # round 2 done
        _verdict(),
    ]
    result, _ = _run(rounds=2, receive_sequence=seq)
    assert result.rounds_completed == 2
    assert result.reprimand_count == 1


def test_reprimand_increments_reprimand_count():
    seq = [
        _arg(AgentID.PRO, 1),
        _reprimand(AgentID.PRO),
        _arg(AgentID.PRO, 1),
        _routing(AgentID.CON),
        _arg(AgentID.CON, 2),
        _routing(AgentID.PRO),
        _verdict(),
    ]
    result, _ = _run(rounds=2, receive_sequence=seq)
    assert result.reprimand_count == 1


def test_multiple_reprimands_counted():
    seq = [
        _arg(AgentID.PRO, 1),
        _reprimand(AgentID.PRO),
        _arg(AgentID.PRO, 1),
        _reprimand(AgentID.PRO),
        _arg(AgentID.PRO, 1),
        _routing(AgentID.CON),
        _arg(AgentID.CON, 2),
        _routing(AgentID.PRO),
        _verdict(),
    ]
    result, _ = _run(rounds=2, receive_sequence=seq)
    assert result.reprimand_count == 2


# ---------------------------------------------------------------------------
# Process lifecycle
# ---------------------------------------------------------------------------

def test_all_processes_terminated_after_run():
    pro, con, judge = _proc(), _proc(), _proc()
    channel = _make_channel([_arg(), _routing(), _arg(AgentID.CON), _routing(AgentID.PRO), _verdict()])
    orch = DebateOrchestrator(channel=channel)
    orch.run("AI and jobs", 2, pro, con, judge)
    pro.terminate.assert_called()
    con.terminate.assert_called()
    judge.terminate.assert_called()


def test_verdict_request_sent_to_judge_after_loop():
    channel = _make_channel([_arg(), _routing(), _arg(AgentID.CON), _routing(AgentID.PRO), _verdict()])
    judge = _proc()
    orch = DebateOrchestrator(channel=channel)
    orch.run("AI and jobs", 2, _proc(), _proc(), judge)
    sent_messages = [c.args[1] for c in channel.send.call_args_list]
    types = [m.get("message_type") for m in sent_messages]
    assert "verdict_request" in types


def test_opening_message_sent_to_pro():
    channel = _make_channel([_arg(), _routing(), _arg(AgentID.CON), _routing(AgentID.PRO), _verdict()])
    pro = _proc()
    orch = DebateOrchestrator(channel=channel)
    orch.run("AI and jobs", 2, pro, _proc(), _proc())
    first_send = channel.send.call_args_list[0]
    assert first_send.args[0] is pro
