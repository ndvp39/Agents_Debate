"""Tests for debate.agents.watchdog — TDD RED phase."""

import subprocess
import time
from unittest.mock import MagicMock

import pytest

from debate.agents.watchdog import Watchdog
from debate.shared.exceptions import WatchdogRestartError


def _proc() -> MagicMock:
    return MagicMock(spec=subprocess.Popen)


# ---------------------------------------------------------------------------
# register()
# ---------------------------------------------------------------------------

def test_register_adds_agent():
    wd = Watchdog(timeout_seconds=5.0)
    wd.register(_proc(), "pro", lambda: _proc())
    assert "pro" in wd._agents


def test_register_two_agents_independently():
    wd = Watchdog(timeout_seconds=5.0)
    wd.register(_proc(), "pro", lambda: _proc())
    wd.register(_proc(), "con", lambda: _proc())
    assert "pro" in wd._agents
    assert "con" in wd._agents


# ---------------------------------------------------------------------------
# start_timer() + timeout fires
# ---------------------------------------------------------------------------

def test_timer_fires_kills_process_and_calls_restart():
    wd = Watchdog(timeout_seconds=0.05)
    process = _proc()
    new_proc = _proc()
    restart_fn = MagicMock(return_value=new_proc)

    wd.register(process, "pro", restart_fn)
    wd.start_timer("pro")
    time.sleep(0.3)

    process.kill.assert_called_once()
    restart_fn.assert_called_once()


def test_timer_updates_process_reference_after_restart():
    wd = Watchdog(timeout_seconds=0.05)
    old_proc = _proc()
    new_proc = _proc()
    wd.register(old_proc, "pro", lambda: new_proc)
    wd.start_timer("pro")
    time.sleep(0.3)

    assert wd._agents["pro"].process is new_proc


# ---------------------------------------------------------------------------
# reset_timer() — prevents kill
# ---------------------------------------------------------------------------

def test_reset_timer_prevents_kill():
    wd = Watchdog(timeout_seconds=0.15)
    process = _proc()
    restart_fn = MagicMock(return_value=_proc())

    wd.register(process, "pro", restart_fn)
    wd.start_timer("pro")
    wd.reset_timer("pro")
    time.sleep(0.4)

    process.kill.assert_not_called()
    restart_fn.assert_not_called()


def test_reset_timer_for_unregistered_agent_raises():
    wd = Watchdog(timeout_seconds=5.0)
    with pytest.raises(KeyError):
        wd.reset_timer("unknown")


# ---------------------------------------------------------------------------
# stop() — cancels all timers
# ---------------------------------------------------------------------------

def test_stop_cancels_all_timers():
    wd = Watchdog(timeout_seconds=0.15)
    p1, p2 = _proc(), _proc()
    r1 = MagicMock(return_value=_proc())
    r2 = MagicMock(return_value=_proc())

    wd.register(p1, "pro", r1)
    wd.register(p2, "con", r2)
    wd.start_timer("pro")
    wd.start_timer("con")
    wd.stop()
    time.sleep(0.4)

    p1.kill.assert_not_called()
    p2.kill.assert_not_called()


def test_stop_without_active_timers_is_safe():
    wd = Watchdog(timeout_seconds=5.0)
    wd.register(_proc(), "pro", lambda: _proc())
    wd.stop()  # no timer started — must not raise


# ---------------------------------------------------------------------------
# Two agents timeout independently
# ---------------------------------------------------------------------------

def test_two_agents_timeout_independently():
    wd = Watchdog(timeout_seconds=0.05)
    p1, p2 = _proc(), _proc()
    r1 = MagicMock(return_value=_proc())
    r2 = MagicMock(return_value=_proc())

    wd.register(p1, "pro", r1)
    wd.register(p2, "con", r2)
    wd.start_timer("pro")
    wd.start_timer("con")
    time.sleep(0.3)

    p1.kill.assert_called_once()
    p2.kill.assert_called_once()
    r1.assert_called_once()
    r2.assert_called_once()


# ---------------------------------------------------------------------------
# Restart failure — stored in last_error
# ---------------------------------------------------------------------------

def test_restart_failure_stores_watchdog_error():
    wd = Watchdog(timeout_seconds=0.05)
    process = _proc()

    def bad_restart():
        raise RuntimeError("spawn failed")

    wd.register(process, "pro", bad_restart)
    wd.start_timer("pro")
    time.sleep(0.3)

    process.kill.assert_called_once()
    assert isinstance(wd.last_error, WatchdogRestartError)


def test_last_error_none_when_restart_succeeds():
    wd = Watchdog(timeout_seconds=0.05)
    wd.register(_proc(), "pro", lambda: _proc())
    wd.start_timer("pro")
    time.sleep(0.3)

    assert wd.last_error is None
