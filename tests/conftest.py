"""Shared pytest fixtures for all test suites."""

import pytest


@pytest.fixture
def sample_topic() -> str:
    """A reusable debate topic for tests."""
    return "Artificial intelligence will replace human jobs"


@pytest.fixture
def sample_rounds() -> int:
    """Default number of rounds for test debates."""
    return 2
