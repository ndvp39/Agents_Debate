"""Tests for debate.agents.base_agent — TDD RED phase."""

import json
from io import BytesIO
from unittest.mock import MagicMock

import pytest

from debate.agents.base_agent import BaseAgent
from debate.shared.exceptions import IPCParseError


def _make_agent(stdin_data: bytes = b"", stdout_buf: BytesIO | None = None) -> tuple[BaseAgent, BytesIO]:
    stdin = BytesIO(stdin_data)
    buf = stdout_buf if stdout_buf is not None else BytesIO()
    return BaseAgent("Agent_Test", stdin=stdin, stdout=buf), buf


# ---------------------------------------------------------------------------
# Identity
# ---------------------------------------------------------------------------

def test_agent_id_stored():
    agent, _ = _make_agent()
    assert agent.agent_id == "Agent_Test"


# ---------------------------------------------------------------------------
# Skill loader injection
# ---------------------------------------------------------------------------

def test_skills_loader_defaults_to_none():
    agent, _ = _make_agent()
    assert agent._skills is None


def test_skills_loader_is_stored_when_provided():
    loader = MagicMock()
    agent = BaseAgent("Agent_Test", stdin=BytesIO(), stdout=BytesIO(), skills=loader)
    assert agent._skills is loader


# ---------------------------------------------------------------------------
# start / stop
# ---------------------------------------------------------------------------

def test_initial_state_is_not_running():
    agent, _ = _make_agent()
    assert not agent.is_running


def test_start_sets_running():
    agent, _ = _make_agent()
    agent.start()
    assert agent.is_running


def test_stop_clears_running():
    agent, _ = _make_agent()
    agent.start()
    agent.stop()
    assert not agent.is_running


def test_stop_without_start_is_safe():
    agent, _ = _make_agent()
    agent.stop()
    assert not agent.is_running


# ---------------------------------------------------------------------------
# send()
# ---------------------------------------------------------------------------

def test_send_writes_valid_json():
    agent, buf = _make_agent()
    agent.send({"key": "value"})
    buf.seek(0)
    data = json.loads(buf.read().decode("utf-8").strip())
    assert data["key"] == "value"


def test_send_appends_newline():
    agent, buf = _make_agent()
    agent.send({"x": 1})
    buf.seek(0)
    assert buf.read().endswith(b"\n")


def test_send_flushes_stdout():
    mock_out = MagicMock()
    agent = BaseAgent("Agent_Test", stdin=BytesIO(), stdout=mock_out)
    agent.send({"a": 1})
    mock_out.flush.assert_called_once()


def test_send_raises_on_write_error():
    mock_out = MagicMock()
    mock_out.write.side_effect = OSError("pipe broken")
    agent = BaseAgent("Agent_Test", stdin=BytesIO(), stdout=mock_out)
    with pytest.raises(IPCParseError):
        agent.send({"a": 1})


# ---------------------------------------------------------------------------
# receive()
# ---------------------------------------------------------------------------

def test_receive_parses_valid_json():
    payload = {"message_type": "routing", "target_agent": "Agent_Pro"}
    raw = json.dumps(payload).encode("utf-8") + b"\n"
    agent, _ = _make_agent(stdin_data=raw)
    result = agent.receive()
    assert result["message_type"] == "routing"
    assert result["target_agent"] == "Agent_Pro"


def test_receive_raises_on_empty_stdin():
    agent, _ = _make_agent(stdin_data=b"")
    with pytest.raises(IPCParseError, match="[Ee]mpty"):
        agent.receive()


def test_receive_raises_on_invalid_json():
    agent, _ = _make_agent(stdin_data=b"not-valid-json\n")
    with pytest.raises(IPCParseError):
        agent.receive()


def test_receive_handles_whitespace_padding():
    payload = {"k": "v"}
    raw = b"  " + json.dumps(payload).encode("utf-8") + b"  \n"
    agent, _ = _make_agent(stdin_data=raw)
    result = agent.receive()
    assert result["k"] == "v"
