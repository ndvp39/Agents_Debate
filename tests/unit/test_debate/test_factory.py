"""Tests for debate.sdk.factory — subprocess_factory builds per-agent spawners."""

import subprocess
from unittest.mock import MagicMock, patch

from debate.sdk.factory import _SRC_DIR, Spawners, subprocess_factory

# ---------------------------------------------------------------------------
# _SRC_DIR sanity check
# ---------------------------------------------------------------------------

def test_src_dir_points_to_src():
    assert _SRC_DIR.name == "src"
    assert _SRC_DIR.is_dir()


# ---------------------------------------------------------------------------
# subprocess_factory()
# ---------------------------------------------------------------------------

def _popen_mock():
    m = MagicMock()
    m.stdin = MagicMock()
    m.stdout = MagicMock()
    return m


def test_factory_returns_spawners_dataclass():
    spawners = subprocess_factory("AI ethics", 2)
    assert isinstance(spawners, Spawners)
    assert callable(spawners.spawn_pro)
    assert callable(spawners.spawn_con)
    assert callable(spawners.spawn_judge)


def test_each_spawner_spawns_one_popen():
    with patch("debate.sdk.factory.subprocess.Popen") as mock_popen:
        mock_popen.side_effect = [_popen_mock(), _popen_mock(), _popen_mock()]
        spawners = subprocess_factory("AI ethics", 2)
        # Lazy — no Popen calls until spawners are invoked.
        assert mock_popen.call_count == 0
        spawners.spawn_pro()
        spawners.spawn_con()
        spawners.spawn_judge()
        assert mock_popen.call_count == 3


def test_spawners_pass_stdin_stdout_pipe():
    with patch("debate.sdk.factory.subprocess.Popen") as mock_popen:
        mock_popen.side_effect = [_popen_mock(), _popen_mock(), _popen_mock()]
        spawners = subprocess_factory("Topic", 3)
        spawners.spawn_pro()
        spawners.spawn_con()
        spawners.spawn_judge()
        for c in mock_popen.call_args_list:
            kwargs = c.kwargs
            assert kwargs["stdin"] == subprocess.PIPE
            assert kwargs["stdout"] == subprocess.PIPE


def test_spawners_pass_topic_to_debaters():
    topic = "Climate change policy"
    with patch("debate.sdk.factory.subprocess.Popen") as mock_popen:
        mock_popen.side_effect = [_popen_mock(), _popen_mock(), _popen_mock()]
        spawners = subprocess_factory(topic, 2)
        spawners.spawn_pro()
        spawners.spawn_con()
        spawners.spawn_judge()
        pro_args = mock_popen.call_args_list[0].args[0]
        con_args = mock_popen.call_args_list[1].args[0]
        assert topic in pro_args
        assert topic in con_args


def test_spawners_use_unbuffered_flag():
    with patch("debate.sdk.factory.subprocess.Popen") as mock_popen:
        mock_popen.side_effect = [_popen_mock(), _popen_mock(), _popen_mock()]
        spawners = subprocess_factory("Topic", 2)
        spawners.spawn_pro()
        spawners.spawn_con()
        spawners.spawn_judge()
        for c in mock_popen.call_args_list:
            cmd = c.args[0]
            assert "-u" in cmd


def test_spawners_use_correct_runner_scripts():
    with patch("debate.sdk.factory.subprocess.Popen") as mock_popen:
        mock_popen.side_effect = [_popen_mock(), _popen_mock(), _popen_mock()]
        spawners = subprocess_factory("Topic", 2)
        spawners.spawn_pro()
        spawners.spawn_con()
        spawners.spawn_judge()
        pro_cmd = mock_popen.call_args_list[0].args[0]
        con_cmd = mock_popen.call_args_list[1].args[0]
        judge_cmd = mock_popen.call_args_list[2].args[0]
        assert any("pro_runner" in str(a) for a in pro_cmd)
        assert any("con_runner" in str(a) for a in con_cmd)
        assert any("judge_runner" in str(a) for a in judge_cmd)


def test_judge_spawner_threads_checkpoint_path_into_argv():
    from pathlib import Path
    cp = Path("/tmp/test_judge_checkpoint.json")
    with patch("debate.sdk.factory.subprocess.Popen") as mock_popen:
        mock_popen.side_effect = [_popen_mock(), _popen_mock(), _popen_mock()]
        spawners = subprocess_factory("Topic", 2, judge_checkpoint_path=cp)
        spawners.spawn_pro()
        spawners.spawn_con()
        spawners.spawn_judge()
        judge_cmd = mock_popen.call_args_list[2].args[0]
        assert "--checkpoint" in judge_cmd
        idx = judge_cmd.index("--checkpoint")
        assert judge_cmd[idx + 1] == str(cp)
