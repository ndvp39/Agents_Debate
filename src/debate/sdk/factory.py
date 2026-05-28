"""Subprocess factory — returns per-agent spawn closures so each agent can be
respawned independently by the watchdog when its process hangs."""

import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

_SRC_DIR = Path(__file__).parent.parent.parent  # resolves to src/


@dataclass(frozen=True)
class Spawners:
    """Per-agent spawn callables. Each returns a fresh `subprocess.Popen`."""

    spawn_pro: Callable[[], subprocess.Popen]
    spawn_con: Callable[[], subprocess.Popen]
    spawn_judge: Callable[[], subprocess.Popen]


def subprocess_factory(
    topic: str,
    rounds: int,
    *,
    judge_checkpoint_path: Path | None = None,
) -> Spawners:
    """Build per-agent spawn closures for one debate session.

    The judge respawn closure receives the same `--checkpoint` path so a
    restarted judge reloads its accumulated state and resumes with full score
    history (debater state is replayed via the next routing message; judge
    state is not, so a file checkpoint is required for safe restart).
    """
    pipe = {"stdin": subprocess.PIPE, "stdout": subprocess.PIPE}
    pro_cmd = [sys.executable, "-u", str(_SRC_DIR / "pro_runner.py"), "--topic", topic]
    con_cmd = [sys.executable, "-u", str(_SRC_DIR / "con_runner.py"), "--topic", topic]
    judge_cmd = [sys.executable, "-u", str(_SRC_DIR / "judge_runner.py")]
    if judge_checkpoint_path is not None:
        judge_cmd.extend(["--checkpoint", str(judge_checkpoint_path)])

    return Spawners(
        spawn_pro=lambda: subprocess.Popen(pro_cmd, **pipe),
        spawn_con=lambda: subprocess.Popen(con_cmd, **pipe),
        spawn_judge=lambda: subprocess.Popen(judge_cmd, **pipe),
    )
