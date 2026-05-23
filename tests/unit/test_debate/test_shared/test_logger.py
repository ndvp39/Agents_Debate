"""Tests for debate.shared.logger — written before implementation (TDD RED)."""

import threading
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from debate.shared.logger import DebateLogger


@pytest.fixture
def mock_config(tmp_path):
    config = MagicMock()
    config.get_logging_config.return_value = {
        "version": "1.00",
        "logging": {
            "max_files": 3,
            "max_lines_per_file": 5,
            "log_dir": str(tmp_path / "logs"),
            "level": "INFO",
            "file_prefix": "test_log_",
            "file_extension": ".log",
            "sequence_max": 999,
        },
    }
    return config


def test_log_creates_file(mock_config):
    logger = DebateLogger(mock_config)
    logger.log("INFO", "test", "hello")
    assert Path(logger.get_current_file()).exists()


def test_log_entry_contains_component(mock_config):
    logger = DebateLogger(mock_config)
    logger.log("INFO", "orchestrator", "debate started")
    content = Path(logger.get_current_file()).read_text()
    assert "orchestrator" in content


def test_log_entry_contains_message(mock_config):
    logger = DebateLogger(mock_config)
    logger.log("INFO", "test", "my message")
    content = Path(logger.get_current_file()).read_text()
    assert "my message" in content


def test_log_entry_contains_extra_fields(mock_config):
    logger = DebateLogger(mock_config)
    logger.log("INFO", "test", "event", topic="AI", round=3)
    content = Path(logger.get_current_file()).read_text()
    assert "topic=AI" in content
    assert "round=3" in content


def test_rotation_on_line_limit(mock_config):
    logger = DebateLogger(mock_config)
    first = logger.get_current_file()
    for i in range(6):
        logger.log("INFO", "test", f"line {i}")
    assert logger.get_current_file() != first


def test_fifo_deletes_oldest_file(mock_config):
    logger = DebateLogger(mock_config)
    for i in range(25):
        logger.log("INFO", "test", f"line {i}")
    assert len(logger.get_all_files()) <= 3


def test_debug_filtered_when_level_is_info(mock_config):
    logger = DebateLogger(mock_config)
    logger.log("INFO", "test", "baseline")          # ensure file is created
    logger.log("DEBUG", "test", "should not appear")
    content = Path(logger.get_current_file()).read_text()
    assert "should not appear" not in content


def test_concurrent_writes_no_errors(mock_config):
    logger = DebateLogger(mock_config)
    errors: list = []

    def write():
        try:
            for i in range(3):
                logger.log("INFO", "thread", f"msg {i}")
        except Exception as exc:
            errors.append(exc)

    threads = [threading.Thread(target=write) for _ in range(3)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert not errors
