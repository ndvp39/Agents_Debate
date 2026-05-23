"""Tests for debate.sdk.factory — subprocess_factory spawns the three agent processes."""

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest

from debate.sdk.factory import subprocess_factory, _SRC_DIR


# ---------------------------------------------------------------------------
# _SRC_DIR sanity check
# ---------------------------------------------------------------------------

def test_src_dir_points_to_src():
    assert _SRC_DIR.name == "src"
    assert _SRC_DIR.is_dir()


# ---------------------------------------------------------------------------
# subprocess_factory()
# ---------------------------------------------------------------------------

def _make_popen_mock():
    mock = MagicMock()
    mock.stdin = MagicMock()
    mock.stdout = MagicMock()
    return mock


def test_factory_returns_three_processes():
    with patch("debate.sdk.factory.subprocess.Popen") as mock_popen:
        procs = [_make_popen_mock() for _ in range(3)]
        mock_popen.side_effect = procs

        pro, con, judge = subprocess_factory("AI ethics", 2)

        assert pro is procs[0]
        assert con is procs[1]
        assert judge is procs[2]


def test_factory_spawns_three_popen_calls():
    with patch("debate.sdk.factory.subprocess.Popen") as mock_popen:
        mock_popen.return_value = _make_popen_mock()
        subprocess_factory("AI ethics", 2)
        assert mock_popen.call_count == 3


def test_factory_passes_stdin_stdout_pipe():
    with patch("debate.sdk.factory.subprocess.Popen") as mock_popen:
        mock_popen.return_value = _make_popen_mock()
        subprocess_factory("Topic", 3)

        for c in mock_popen.call_args_list:
            kwargs = c.kwargs
            assert kwargs["stdin"] == subprocess.PIPE
            assert kwargs["stdout"] == subprocess.PIPE


def test_factory_passes_topic_to_debaters():
    topic = "Climate change policy"
    with patch("debate.sdk.factory.subprocess.Popen") as mock_popen:
        mock_popen.return_value = _make_popen_mock()
        subprocess_factory(topic, 2)

        pro_args = mock_popen.call_args_list[0].args[0]
        con_args = mock_popen.call_args_list[1].args[0]

        assert topic in pro_args
        assert topic in con_args


def test_factory_uses_unbuffered_flag():
    with patch("debate.sdk.factory.subprocess.Popen") as mock_popen:
        mock_popen.return_value = _make_popen_mock()
        subprocess_factory("Topic", 2)

        for c in mock_popen.call_args_list:
            cmd = c.args[0]
            assert "-u" in cmd


def test_factory_uses_correct_runner_scripts():
    with patch("debate.sdk.factory.subprocess.Popen") as mock_popen:
        mock_popen.return_value = _make_popen_mock()
        subprocess_factory("Topic", 2)

        pro_cmd = mock_popen.call_args_list[0].args[0]
        con_cmd = mock_popen.call_args_list[1].args[0]
        judge_cmd = mock_popen.call_args_list[2].args[0]

        assert any("pro_runner" in str(a) for a in pro_cmd)
        assert any("con_runner" in str(a) for a in con_cmd)
        assert any("judge_runner" in str(a) for a in judge_cmd)
