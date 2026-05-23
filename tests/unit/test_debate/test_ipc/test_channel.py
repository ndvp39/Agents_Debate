"""Tests for debate.ipc.channel — written before implementation (TDD RED)."""

import json
import time
from io import BytesIO
from unittest.mock import MagicMock

import pytest

from debate.ipc.channel import IPCChannel
from debate.shared.constants import AgentID, MessageType
from debate.shared.exceptions import IPCParseError, IPCSchemaError, IPCTimeoutError


def _make_process(stdout_data: bytes = b"") -> MagicMock:
    process = MagicMock()
    process.stdin = MagicMock()
    buf = BytesIO(stdout_data)
    process.stdout.readline = buf.readline
    return process


def _routing_dict() -> dict:
    return {
        "message_type": MessageType.ROUTING,
        "target_agent": AgentID.PRO,
        "judge_feedback": "Good.",
        "prompt_for_next": "Your turn.",
    }


# ---------------------------------------------------------------------------
# send()
# ---------------------------------------------------------------------------

def test_send_writes_json_line():
    channel = IPCChannel()
    process = _make_process()
    channel.send(process, _routing_dict())
    written = process.stdin.write.call_args[0][0]
    data = json.loads(written.decode("utf-8").strip())
    assert data["message_type"] == MessageType.ROUTING


def test_send_flushes_stdin():
    channel = IPCChannel()
    process = _make_process()
    channel.send(process, _routing_dict())
    process.stdin.flush.assert_called_once()


# ---------------------------------------------------------------------------
# receive()
# ---------------------------------------------------------------------------

def test_receive_parses_valid_routing():
    line = json.dumps(_routing_dict()).encode("utf-8") + b"\n"
    process = _make_process(line)
    channel = IPCChannel()
    result = channel.receive(process, timeout=5.0)
    assert result["message_type"] == MessageType.ROUTING


def test_receive_raises_on_malformed_json():
    process = _make_process(b"not-valid-json\n")
    channel = IPCChannel()
    with pytest.raises(IPCParseError):
        channel.receive(process, timeout=5.0)


def test_receive_raises_on_empty_response():
    process = _make_process(b"")
    channel = IPCChannel()
    with pytest.raises(IPCParseError):
        channel.receive(process, timeout=5.0)


def test_receive_raises_on_timeout():
    process = MagicMock()
    process.stdout.readline = lambda: (time.sleep(10) or b"")
    channel = IPCChannel()
    with pytest.raises(IPCTimeoutError):
        channel.receive(process, timeout=0.05)


# ---------------------------------------------------------------------------
# validate()
# ---------------------------------------------------------------------------

def test_validate_passes_valid_routing():
    channel = IPCChannel()
    channel.validate(_routing_dict())  # should not raise


def test_validate_raises_on_unknown_message_type():
    channel = IPCChannel()
    with pytest.raises(IPCSchemaError):
        channel.validate({"message_type": "bogus"})


def test_validate_raises_on_equal_verdict_scores():
    channel = IPCChannel()
    with pytest.raises(IPCSchemaError):
        channel.validate({
            "message_type": MessageType.VERDICT,
            "winner": AgentID.PRO,
            "scores": {AgentID.PRO: 75, AgentID.CON: 75},
            "justification": "A" * 60,
        })


def test_validate_raises_on_empty_citations():
    channel = IPCChannel()
    with pytest.raises(IPCSchemaError):
        channel.validate({
            "message_type": MessageType.ARGUMENT,
            "agent_id": AgentID.PRO,
            "round": 1,
            "argument": "Arg.",
            "citations": [],
        })
