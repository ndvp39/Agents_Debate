"""BaseAgent — shared agent infrastructure running inside each subprocess."""

import json
import sys
from typing import Any

from debate.shared.exceptions import IPCParseError
from debate.skills.loader import SkillLoader


class BaseAgent:
    """Base class for all agent subprocesses.

    Provides JSON send/receive over binary stdin/stdout, a project-local
    SkillLoader so subclasses can `self._skills.load("name")`, and a simple
    running-state lifecycle. stdin and stdout default to sys.stdin.buffer /
    sys.stdout.buffer so the real subprocess wires up automatically; tests
    pass BytesIO objects instead.
    """

    def __init__(
        self,
        agent_id: str,
        stdin: Any = None,
        stdout: Any = None,
        skills: SkillLoader | None = None,
    ) -> None:
        self._agent_id = agent_id
        self._skills = skills
        self._running = False
        self._stdin = stdin if stdin is not None else sys.stdin.buffer
        self._stdout = stdout if stdout is not None else sys.stdout.buffer

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def agent_id(self) -> str:
        return self._agent_id

    @property
    def is_running(self) -> bool:
        return self._running

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Mark the agent as running. Subclasses call super().start()."""
        self._running = True

    def stop(self) -> None:
        """Signal the agent to stop."""
        self._running = False

    # ------------------------------------------------------------------
    # IPC
    # ------------------------------------------------------------------

    def send(self, message: dict) -> None:
        """Serialize message to a JSON line and write to stdout."""
        try:
            line = json.dumps(message) + "\n"
            self._stdout.write(line.encode("utf-8"))
            self._stdout.flush()
        except OSError as exc:
            raise IPCParseError(f"Failed to send message: {exc}") from exc

    def receive(self) -> dict:
        """Read one JSON line from stdin and return parsed dict."""
        try:
            line = self._stdin.readline()
        except OSError as exc:
            raise IPCParseError(f"Failed to read from stdin: {exc}") from exc

        if not line:
            raise IPCParseError("Empty response from stdin")

        raw = line.decode("utf-8").strip()
        try:
            return json.loads(raw)
        except json.JSONDecodeError as exc:
            raise IPCParseError(f"Invalid JSON: {exc}") from exc
