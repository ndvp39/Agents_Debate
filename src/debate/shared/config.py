"""Configuration manager — loads and validates all JSON config files."""

import json
from pathlib import Path

from debate.shared.constants import REQUIRED_CONFIG_VERSION
from debate.shared.exceptions import ConfigError


class ConfigManager:
    """Loads setup.json, rate_limits.json, and logging_config.json.

    Validates that every config file carries the expected version string
    before the rest of the system is allowed to read any values.
    """

    _FILENAMES = ("setup.json", "rate_limits.json", "logging_config.json")

    def __init__(self, config_dir: str = "config/") -> None:
        self._dir = Path(config_dir)
        self._setup = self._load("setup.json")
        self._rate_limits = self._load("rate_limits.json")
        self._logging = self._load("logging_config.json")
        self._validate_versions()

    def _load(self, filename: str) -> dict:
        path = self._dir / filename
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)

    def _validate_versions(self) -> None:
        configs = {
            "setup.json": self._setup,
            "rate_limits.json": self._rate_limits,
            "logging_config.json": self._logging,
        }
        for name, cfg in configs.items():
            version = cfg.get("version")
            if version is None:
                raise ConfigError(f"{name}: missing 'version' field")
            if version != REQUIRED_CONFIG_VERSION:
                raise ConfigError(
                    f"{name}: version {version!r} != required {REQUIRED_CONFIG_VERSION!r}"
                )

    def get_setup(self) -> dict:
        """Return the full setup.json config dict."""
        return self._setup

    def get_rate_limits(self) -> dict:
        """Return the full rate_limits.json config dict."""
        return self._rate_limits

    def get_logging_config(self) -> dict:
        """Return the full logging_config.json config dict."""
        return self._logging
