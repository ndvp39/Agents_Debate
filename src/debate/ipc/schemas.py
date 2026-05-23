"""IPC message schemas — dataclasses with validation for all 4 message types."""

from dataclasses import dataclass, field

from debate.shared.constants import MIN_JUSTIFICATION_LENGTH, MessageType
from debate.shared.exceptions import IPCSchemaError


@dataclass
class RoutingMessage:
    """Judge → next debater: valid argument accepted, turn advanced."""

    target_agent: str
    judge_feedback: str
    prompt_for_next: str
    message_type: str = field(default=MessageType.ROUTING)

    def __post_init__(self) -> None:
        if self.message_type != MessageType.ROUTING:
            raise IPCSchemaError(f"Expected routing, got {self.message_type!r}")
        if not self.target_agent:
            raise IPCSchemaError("target_agent must not be empty")
        if not self.prompt_for_next:
            raise IPCSchemaError("prompt_for_next must not be empty")

    @classmethod
    def from_dict(cls, data: dict) -> "RoutingMessage":
        """Construct from a raw dict; raise IPCSchemaError on missing fields."""
        try:
            return cls(
                target_agent=data["target_agent"],
                judge_feedback=data.get("judge_feedback", ""),
                prompt_for_next=data["prompt_for_next"],
                message_type=data.get("message_type", MessageType.ROUTING),
            )
        except KeyError as exc:
            raise IPCSchemaError(f"Missing field: {exc}") from exc

    def to_dict(self) -> dict:
        return {
            "message_type": self.message_type,
            "target_agent": self.target_agent,
            "judge_feedback": self.judge_feedback,
            "prompt_for_next": self.prompt_for_next,
        }


@dataclass
class ReprimandMessage:
    """Judge → same debater: argument rejected, must rewrite."""

    target_agent: str
    prompt_for_next: str
    reprimand_issued: bool = True
    message_type: str = field(default=MessageType.REPRIMAND)

    def __post_init__(self) -> None:
        if self.message_type != MessageType.REPRIMAND:
            raise IPCSchemaError(f"Expected reprimand, got {self.message_type!r}")
        if not self.reprimand_issued:
            raise IPCSchemaError("reprimand_issued must be True")
        if not self.target_agent:
            raise IPCSchemaError("target_agent must not be empty")

    @classmethod
    def from_dict(cls, data: dict) -> "ReprimandMessage":
        try:
            return cls(
                target_agent=data["target_agent"],
                prompt_for_next=data["prompt_for_next"],
                reprimand_issued=data.get("reprimand_issued", True),
                message_type=data.get("message_type", MessageType.REPRIMAND),
            )
        except KeyError as exc:
            raise IPCSchemaError(f"Missing field: {exc}") from exc

    def to_dict(self) -> dict:
        return {
            "message_type": self.message_type,
            "target_agent": self.target_agent,
            "reprimand_issued": self.reprimand_issued,
            "prompt_for_next": self.prompt_for_next,
        }


@dataclass
class VerdictMessage:
    """Judge → orchestrator: final debate verdict. Ties are forbidden."""

    winner: str
    scores: dict
    justification: str
    message_type: str = field(default=MessageType.VERDICT)

    def __post_init__(self) -> None:
        if self.message_type != MessageType.VERDICT:
            raise IPCSchemaError(f"Expected verdict, got {self.message_type!r}")
        if len(self.scores) != 2:
            raise IPCSchemaError("scores must have exactly 2 entries")
        vals = list(self.scores.values())
        if vals[0] == vals[1]:
            raise IPCSchemaError("Scores must differ — ties are forbidden")
        if self.winner not in self.scores:
            raise IPCSchemaError(f"winner {self.winner!r} not in scores")
        if len(self.justification) < MIN_JUSTIFICATION_LENGTH:
            raise IPCSchemaError(f"justification must be >= {MIN_JUSTIFICATION_LENGTH} chars")

    @classmethod
    def from_dict(cls, data: dict) -> "VerdictMessage":
        try:
            return cls(
                winner=data["winner"],
                scores=data["scores"],
                justification=data["justification"],
                message_type=data.get("message_type", MessageType.VERDICT),
            )
        except KeyError as exc:
            raise IPCSchemaError(f"Missing field: {exc}") from exc

    def to_dict(self) -> dict:
        return {
            "message_type": self.message_type,
            "winner": self.winner,
            "scores": self.scores,
            "justification": self.justification,
        }


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


_SCHEMA_MAP: dict = {
    MessageType.ROUTING: RoutingMessage,
    MessageType.REPRIMAND: ReprimandMessage,
    MessageType.VERDICT: VerdictMessage,
    MessageType.ARGUMENT: ArgumentMessage,
}


def message_from_dict(data: dict):
    """Parse a dict into the correct message dataclass; raise IPCSchemaError if unknown."""
    msg_type = data.get("message_type")
    cls = _SCHEMA_MAP.get(msg_type)
    if cls is None:
        raise IPCSchemaError(f"Unknown message_type: {msg_type!r}")
    return cls.from_dict(data)
