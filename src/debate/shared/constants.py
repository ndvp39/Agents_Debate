"""Immutable project-wide constants for the debate system."""

from enum import Enum


class MessageType(str, Enum):
    """Valid IPC message types exchanged between agents."""

    ROUTING = "routing"
    REPRIMAND = "reprimand"
    VERDICT = "verdict"
    ARGUMENT = "argument"


class AgentID:
    """Canonical agent identifiers used in IPC messages."""

    JUDGE = "Agent_Judge"
    PRO = "Agent_Pro"
    CON = "Agent_Con"


class Stance:
    """Fixed debate stances assigned to each debater."""

    PRO = "completely FOR"
    CON = "completely AGAINST"


# Persuasion score weights — 3 dimensions, must sum to 1.0
SCORE_WEIGHT_LOGIC: float = 0.5
SCORE_WEIGHT_CITATION: float = 0.3
SCORE_WEIGHT_RHETORIC: float = 0.2

# Minimum character length for a valid verdict justification
MIN_JUSTIFICATION_LENGTH: int = 50

# Config version this codebase expects
REQUIRED_CONFIG_VERSION: str = "1.00"
