"""Shared exception hierarchy for the debate system."""


class DebateError(Exception):
    """Base exception for all debate system errors."""


class ConfigError(DebateError):
    """Raised when configuration is missing, invalid, or version-incompatible."""


class IPCParseError(DebateError):
    """Raised when a received message cannot be parsed as JSON."""


class IPCSchemaError(DebateError):
    """Raised when a parsed message fails schema validation."""


class IPCTimeoutError(DebateError):
    """Raised when an agent does not respond within the configured timeout."""


class BackpressureError(DebateError):
    """Raised when the gatekeeper queue is at maximum capacity."""


class GatekeeperMaxRetriesError(DebateError):
    """Raised when all retry attempts for an API call are exhausted."""


class WatchdogRestartError(DebateError):
    """Raised when the Watchdog fails to restart an agent process."""


class ToolNotAvailableError(DebateError):
    """Raised when an agent attempts to use an unregistered skill/tool."""


class InsufficientDataError(DebateError):
    """Raised when an operation requires data that has not been collected yet."""
