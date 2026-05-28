"""Self-repair proof: a hung debater subprocess is killed and respawned by the
watchdog mid-debate, the orchestrator transparently re-sends the in-flight
message, and the debate completes against the fresh process.

These tests spawn real OS subprocesses (tiny `python -c` one-liners) so the
watchdog's `kill()` and the restart-spawn-and-resend flow exercise the actual
OS process lifecycle, not mocks.
"""

import json
import subprocess
import sys
import tempfile
import textwrap
from pathlib import Path

from debate.agents.watchdog import Watchdog
from debate.sdk.factory import Spawners
from debate.services.orchestrator import DebateOrchestrator

# ---------------------------------------------------------------------------
# Subprocess scripts — each is sent verbatim to `python -u -c`.
# ---------------------------------------------------------------------------

HUNG_SCRIPT = "import sys; sys.stdin.read()"  # blocks forever, never replies

RESPONSIVE_PRO_SCRIPT = textwrap.dedent("""
    import sys, json
    while True:
        line = sys.stdin.readline()
        if not line:
            break
        msg = json.loads(line)
        rn = msg.get('round_number') or 1
        out = {'message_type': 'argument', 'agent_id': 'Agent_Pro', 'round': rn,
               'argument': 'Restarted-Pro argument round ' + str(rn) + '.',
               'citations': ['src1']}
        sys.stdout.write(json.dumps(out) + '\\n')
        sys.stdout.flush()
""")

RESPONSIVE_CON_SCRIPT = textwrap.dedent("""
    import sys, json
    while True:
        line = sys.stdin.readline()
        if not line:
            break
        msg = json.loads(line)
        rn = msg.get('round_number') or 1
        out = {'message_type': 'argument', 'agent_id': 'Agent_Con', 'round': rn,
               'argument': 'Con argument round ' + str(rn) + '.',
               'citations': ['src2']}
        sys.stdout.write(json.dumps(out) + '\\n')
        sys.stdout.flush()
""")

RESPONSIVE_JUDGE_SCRIPT = textwrap.dedent("""
    import sys, json
    while True:
        line = sys.stdin.readline()
        if not line:
            break
        msg = json.loads(line)
        mt = msg.get('message_type')
        if mt == 'verdict_request':
            out = {'message_type': 'verdict', 'winner': 'Agent_Pro',
                   'scores': {'Agent_Pro': 80, 'Agent_Con': 70},
                   'justification': 'A' * 60}
        elif mt == 'argument':
            if msg['agent_id'] == 'Agent_Pro':
                target = 'Agent_Con'
                nr = msg['round']
            else:
                target = 'Agent_Pro'
                nr = msg['round'] + 1
            out = {'message_type': 'routing', 'target_agent': target,
                   'judge_feedback': 'Continue.', 'prompt_for_next': 'Your turn.',
                   'previous_argument': msg['argument'], 'round_number': nr}
        else:
            continue
        sys.stdout.write(json.dumps(out) + '\\n')
        sys.stdout.flush()
""")


def _popen(script: str) -> subprocess.Popen:
    return subprocess.Popen(
        [sys.executable, "-u", "-c", script],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
    )


# ---------------------------------------------------------------------------
# The core deliverable: a hung Pro is killed + restarted, debate finishes.
# ---------------------------------------------------------------------------

def test_watchdog_recovers_from_hung_debater_subprocess(caplog):
    """Pro is hung on round 1. Watchdog fires, kills it, respawns a responsive Pro,
    orchestrator re-sends the routing message, debate completes against the
    fresh process. The whole sequence must appear in the logs."""
    import logging
    caplog.set_level(logging.INFO, logger="debate.watchdog")
    caplog.set_level(logging.INFO, logger="debate.orchestrator")

    pro_calls = []
    initial_hung_pid: list[int] = []

    def spawn_pro():
        if not pro_calls:
            pro_calls.append("hung")
            proc = _popen(HUNG_SCRIPT)
            initial_hung_pid.append(proc.pid)
            return proc
        pro_calls.append("responsive")
        return _popen(RESPONSIVE_PRO_SCRIPT)

    def spawn_con():
        return _popen(RESPONSIVE_CON_SCRIPT)

    def spawn_judge():
        return _popen(RESPONSIVE_JUDGE_SCRIPT)

    spawners = Spawners(
        spawn_pro=spawn_pro,
        spawn_con=spawn_con,
        spawn_judge=spawn_judge,
    )

    wd = Watchdog(timeout_seconds=2.0)
    orch = DebateOrchestrator(watchdog=wd, ipc_timeout=15.0)
    result = orch.run("Self-repair smoke topic", 1, spawners=spawners)

    # --- Restart actually happened ---
    assert pro_calls == ["hung", "responsive"], f"expected hung->responsive, got {pro_calls}"
    assert wd.last_error is None, f"watchdog reported restart error: {wd.last_error}"

    # --- Debate completed end-to-end ---
    assert result.rounds_completed == 1
    assert result.verdict.get("winner") == "Agent_Pro"
    assert result.verdict.get("scores") == {"Agent_Pro": 80, "Agent_Con": 70}

    # --- Pro's argument came from the RESTARTED process, not the hung one ---
    pro_arg_msgs = [
        m for m in result.transcript
        if m.get("message_type") == "argument" and m.get("agent_id") == "Agent_Pro"
    ]
    assert pro_arg_msgs, "expected an Agent_Pro argument in the transcript"
    assert "Restarted-Pro" in pro_arg_msgs[0]["argument"]

    # --- Observability: every stage shows up in the log ---
    log_text = caplog.text
    assert "watchdog: timer armed" in log_text
    assert "watchdog: timeout fired" in log_text
    assert f"killed_pid={initial_hung_pid[0]}" in log_text
    assert "watchdog: restart OK" in log_text
    assert "orchestrator: re-sending in-flight message" in log_text


# ---------------------------------------------------------------------------
# Negative: when restart_fn fails, the watchdog records last_error and the
# orchestrator surfaces a clean abort rather than hanging forever.
# ---------------------------------------------------------------------------

def test_watchdog_records_failure_when_restart_fn_raises(caplog):
    import logging
    caplog.set_level(logging.WARNING, logger="debate.watchdog")
    wd = Watchdog(timeout_seconds=0.5)

    hung_proc = _popen(HUNG_SCRIPT)
    spawn_count = [0]

    def bad_spawn():
        spawn_count[0] += 1
        raise RuntimeError("simulated spawn failure")

    wd.register(hung_proc, "Agent_Pro", bad_spawn)
    wd.start_timer("Agent_Pro")
    # Wait long enough for the watchdog to fire and the (failing) restart to attempt.
    assert wd.wait_for_restart("Agent_Pro", timeout=5.0)
    assert spawn_count[0] == 1
    assert wd.last_error is not None
    assert "Restart failed" in str(wd.last_error)

    # Clean up — the process is already dead.
    hung_proc.poll()


# ---------------------------------------------------------------------------
# Sanity: with a fully-responsive Pro, the watchdog DOES NOT false-positive.
# ---------------------------------------------------------------------------

def test_watchdog_does_not_kill_healthy_debater():
    spawn_counts = {"pro": 0, "con": 0, "judge": 0}

    def spawn_pro():
        spawn_counts["pro"] += 1
        return _popen(RESPONSIVE_PRO_SCRIPT)

    def spawn_con():
        spawn_counts["con"] += 1
        return _popen(RESPONSIVE_CON_SCRIPT)

    def spawn_judge():
        spawn_counts["judge"] += 1
        return _popen(RESPONSIVE_JUDGE_SCRIPT)

    spawners = Spawners(
        spawn_pro=spawn_pro,
        spawn_con=spawn_con,
        spawn_judge=spawn_judge,
    )

    wd = Watchdog(timeout_seconds=5.0)
    orch = DebateOrchestrator(watchdog=wd, ipc_timeout=15.0)
    result = orch.run("Healthy topic", 1, spawners=spawners)

    assert spawn_counts == {"pro": 1, "con": 1, "judge": 1}
    assert wd.last_error is None
    assert result.rounds_completed == 1
    assert result.verdict.get("winner") == "Agent_Pro"
