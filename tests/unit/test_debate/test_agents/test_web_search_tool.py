"""Tests for debate.agents.debaters.web_search_tool — TDD RED phase."""

from unittest.mock import MagicMock

import pytest

from debate.agents.debaters.web_search_tool import WebSearchTool


def _tool(results=None, raises=False):
    if raises:
        search_call = MagicMock(side_effect=RuntimeError("API error"))
    else:
        search_call = MagicMock(return_value=results or [])
    return WebSearchTool(search_call), search_call


# ---------------------------------------------------------------------------
# search()
# ---------------------------------------------------------------------------

def test_search_calls_api_with_query():
    tool, mock = _tool(["Result 1"])
    tool.search("AI job creation")
    mock.assert_called_once_with("AI job creation")


def test_search_returns_results():
    tool, _ = _tool(["Result 1", "Result 2"])
    results = tool.search("AI jobs")
    assert results == ["Result 1", "Result 2"]


def test_search_caps_at_three_results():
    tool, _ = _tool(["R1", "R2", "R3", "R4", "R5"])
    results = tool.search("query")
    assert len(results) == 3


def test_search_returns_empty_on_api_failure():
    tool, _ = _tool(raises=True)
    results = tool.search("query")
    assert results == []


def test_search_returns_empty_when_api_returns_nothing():
    tool, _ = _tool([])
    results = tool.search("query")
    assert results == []


def test_search_does_not_raise_on_exception():
    tool, _ = _tool(raises=True)
    try:
        tool.search("query")
    except Exception:
        pytest.fail("WebSearchTool.search() should not raise on API failure")
