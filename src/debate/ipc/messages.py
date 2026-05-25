"""ArgumentMessage — debater argument schema for IPC communication."""

from dataclasses import dataclass, field

from debate.shared.constants import MessageType
from debate.shared.exceptions import IPCSchemaError


@dataclass
class ArgumentMessage:
    """Debater → judge: argument with mandatory citations."""

    agent_id: str
    round: int
    argument: str
    citations: list
    message_type: str = field(default=MessageType.ARGUMENT)

    def __post_init__(self) -> None:
        if self.message_type != MessageType.ARGUMENT:
            raise IPCSchemaError(f"Expected argument, got {self.message_type!r}")
        if not self.citations:
            raise IPCSchemaError("citations must not be empty")
        if self.round < 1:
            raise IPCSchemaError("round must be >= 1")

    @classmethod
    def from_dict(cls, data: dict) -> "ArgumentMessage":
        try:
            return cls(
                agent_id=data["agent_id"],
                round=data["round"],
                argument=data["argument"],
                citations=data["citations"],
                message_type=data.get("message_type", MessageType.ARGUMENT),
            )
        except KeyError as exc:
            raise IPCSchemaError(f"Missing field: {exc}") from exc

    def to_dict(self) -> dict:
        return {
            "message_type": self.message_type,
            "agent_id": self.agent_id,
            "round": self.round,
            "argument": self.argument,
            "citations": self.citations,
        }
