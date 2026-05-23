"""Tests for debate.shared.version — written before implementation (TDD RED)."""

from debate.shared.version import VERSION


def test_version_exists():
    assert VERSION is not None


def test_version_is_string():
    assert isinstance(VERSION, str)


def test_version_value():
    assert VERSION == "1.00"


def test_version_format():
    parts = VERSION.split(".")
    assert len(parts) == 2
    assert all(part.isdigit() for part in parts)
