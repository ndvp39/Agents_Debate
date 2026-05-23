"""Real subprocess factory — spawns the three agent processes with stdin/stdout pipes."""

import subprocess
import sys
from pathlib import Path

_SRC_DIR = Path(__file__).parent.parent.parent  # resolves to src/


def subprocess_factory(topic: str, rounds: int):
    """Spawn pro, con, and judge subprocesses for a real debate session.

    Returns (pro_proc, con_proc, judge_proc) as subprocess.Popen objects.
    The -u flag forces unbuffered I/O so JSON lines arrive immediately.
    """
    pipe = {"stdin": subprocess.PIPE, "stdout": subprocess.PIPE}

    pro_proc = subprocess.Popen(
        [sys.executable, "-u", str(_SRC_DIR / "pro_runner.py"), "--topic", topic],
        **pipe,
    )
    con_proc = subprocess.Popen(
        [sys.executable, "-u", str(_SRC_DIR / "con_runner.py"), "--topic", topic],
        **pipe,
    )
    judge_proc = subprocess.Popen(
        [sys.executable, "-u", str(_SRC_DIR / "judge_runner.py")],
        **pipe,
    )
    return pro_proc, con_proc, judge_proc
