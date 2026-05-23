"""Tests for debate.shared.config — written before implementation (TDD RED)."""

import json
import pytest
from debate.shared.config import ConfigError, ConfigManager


@pytest.fixture
def valid_config_dir(tmp_path):
    """Create a temp directory with valid config files."""
    (tmp_path / "setup.json").write_text(json.dumps({
        "version": "1.00",
        "debate": {"default_rounds": 10, "timeout_seconds": 120},
        "agents": {"judge_model": "test-model", "temperature": 0.7},
    }))
    (tmp_path / "rate_limits.json").write_text(json.dumps({
        "version": "1.00",
        "services": {"default": {
            "requests_per_minute": 30, "requests_per_hour": 500,
            "concurrent_max": 5, "retry_after_seconds": 30,
            "max_retries": 3, "queue_max_depth": 50,
        }},
    }))
    (tmp_path / "logging_config.json").write_text(json.dumps({
        "version": "1.00",
        "logging": {
            "max_files": 20, "max_lines_per_file": 500,
            "log_dir": "logs/", "level": "INFO",
        },
    }))
    return tmp_path


def test_loads_setup(valid_config_dir):
    cfg = ConfigManager(config_dir=str(valid_config_dir))
    assert cfg.get_setup()["version"] == "1.00"


def test_loads_rate_limits(valid_config_dir):
    cfg = ConfigManager(config_dir=str(valid_config_dir))
    assert "services" in cfg.get_rate_limits()


def test_loads_logging_config(valid_config_dir):
    cfg = ConfigManager(config_dir=str(valid_config_dir))
    assert cfg.get_logging_config()["version"] == "1.00"


def test_missing_version_raises(valid_config_dir):
    (valid_config_dir / "setup.json").write_text(json.dumps({"debate": {}}))
    with pytest.raises(ConfigError, match="version"):
        ConfigManager(config_dir=str(valid_config_dir))


def test_wrong_version_raises(valid_config_dir):
    (valid_config_dir / "setup.json").write_text(json.dumps({"version": "9.99"}))
    with pytest.raises(ConfigError):
        ConfigManager(config_dir=str(valid_config_dir))


def test_missing_file_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        ConfigManager(config_dir=str(tmp_path))


def test_get_setup_returns_dict(valid_config_dir):
    cfg = ConfigManager(config_dir=str(valid_config_dir))
    assert isinstance(cfg.get_setup(), dict)


def test_get_rate_limits_returns_dict(valid_config_dir):
    cfg = ConfigManager(config_dir=str(valid_config_dir))
    assert isinstance(cfg.get_rate_limits(), dict)
