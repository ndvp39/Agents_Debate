"""IPC channel — JSON communication over subprocess stdin/stdout pipes."""

import json
import subprocess
import threading
from typing import Any

from debate.ipc.schemas import message_from_dict
from debate.shared.exceptions import IPCParseError, IPCTimeoutError


class IPCChannel:
    """Serializes and deserializes JSON messages over subprocess stdin/stdout.

    Every message is a single newline-terminated JSON line.
    Agent processes MUST write only valid JSON to stdout; debug output
    goes to stderr.
    """

    def send(self, process: subprocess.Popen, message: dict) -> None:
        """Serialize message dict to JSON and write to process stdin."""
        try:
            line = json.dumps(message) + "\n"
            process.stdin.write(line.encode("utf-8"))
            process.stdin.flush()
        except OSError as exc:
            raise IPCParseError(f"Failed to send message: {exc}") from exc

    def receive(self, process: subprocess.Popen, timeout: float = 30.0) -> dict:
        """Read one JSON line from process stdout.

        Raises:
            IPCTimeoutError: if no response arrives within `timeout` seconds.
            IPCParseError: if the line is not valid JSON or is empty.
            IPCSchemaError: if the JSON does not match a known schema.
        """
        result: list[bytes] = []
        exc_holder: list[Exception] = []

        def _read() -> None:
            try:
                result.append(process.stdout.readline())
            except Exception as exc:
                exc_holder.append(exc)

        thread = threading.Thread(target=_read, daemon=True)
        thread.start()
        thread.join(timeout=timeout)

        if thread.is_alive():
            raise IPCTimeoutError(f"No response within {timeout}s")
        if exc_holder:
            raise IPCParseError(str(exc_holder[0]))
        if not result or not result[0]:
            raise IPCParseError("Empty response from process")

        raw = result[0].decode("utf-8").strip()
        try:
            data: dict[str, Any] = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise IPCParseError(f"Invalid JSON: {exc}") from exc

        self.validate(data)
        return data

    def validate(self, message: dict) -> None:
        """Validate message against known schemas; raise IPCSchemaError if invalid."""
        message_from_dict(message)
