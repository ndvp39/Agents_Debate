"""Tests for debate.shared.web_search — Tavily provider, no real network."""

import sys
from unittest.mock import MagicMock, patch

import pytest

from debate.shared.web_search import _format_results, make_tavily_search


def _stub_tavily_module(client_factory: MagicMock) -> MagicMock:
    """Build a fake `tavily` module exposing TavilyClient = client_factory."""
    mod = MagicMock()
    mod.TavilyClient = client_factory
    return mod


# ---------------------------------------------------------------------------
# make_tavily_search — construction
# ---------------------------------------------------------------------------

def test_make_tavily_search_returns_callable():
    factory = MagicMock(return_value=MagicMock())
    with patch.dict(sys.modules, {"tavily": _stub_tavily_module(factory)}):
        search = make_tavily_search("test-key")
    assert callable(search)
    factory.assert_called_once_with(api_key="test-key")


def test_make_tavily_search_rejects_empty_key():
    with pytest.raises(ValueError, match="non-empty"):
        make_tavily_search("")


# ---------------------------------------------------------------------------
# search() runtime behavior
# ---------------------------------------------------------------------------

def _build_search(client_search_return):
    client = MagicMock()
    client.search.return_value = client_search_return
    factory = MagicMock(return_value=client)
    with patch.dict(sys.modules, {"tavily": _stub_tavily_module(factory)}):
        return make_tavily_search("test-key"), client


def test_search_returns_title_url_strings():
    response = {"results": [
        {"title": "AI Job Impact Study", "url": "https://example.org/study"},
        {"title": "Bureau of Labor 2024", "url": "https://bls.gov/report"},
    ]}
    search, client = _build_search(response)
    out = search("AI and jobs")
    assert out == [
        "AI Job Impact Study — https://example.org/study",
        "Bureau of Labor 2024 — https://bls.gov/report",
    ]
    client.search.assert_called_once_with(
        query="AI and jobs",
        max_results=3,
        search_depth="advanced",
        exclude_domains=["facebook.com", "quora.com", "reddit.com", "pinterest.com"],
    )


def test_search_excludes_social_media_domains():
    """The exclude_domains list filters Quora, Facebook, Reddit, Pinterest."""
    search, client = _build_search({"results": []})
    search("any query")
    call_kwargs = client.search.call_args.kwargs
    excluded = call_kwargs["exclude_domains"]
    assert "facebook.com" in excluded
    assert "quora.com" in excluded
    assert "reddit.com" in excluded
    assert "pinterest.com" in excluded


def test_search_uses_advanced_depth():
    """Advanced depth surfaces more authoritative content than the basic tier."""
    search, client = _build_search({"results": []})
    search("any query")
    assert client.search.call_args.kwargs["search_depth"] == "advanced"


def test_search_routes_through_gatekeeper_when_provided():
    """When a gatekeeper is supplied, Tavily's network call goes through `gatekeeper.execute(...)`."""
    client = MagicMock()
    client.search.return_value = {"results": [{"title": "T", "url": "https://u"}]}
    gk = MagicMock()
    # Pass-through executor so the real client.search() runs and we can assert the gate was used.
    gk.execute.side_effect = lambda fn: fn()
    factory = MagicMock(return_value=client)
    with patch.dict(sys.modules, {"tavily": _stub_tavily_module(factory)}):
        search = make_tavily_search("test-key", gatekeeper=gk)
    out = search("ai jobs")
    assert out == ["T — https://u"]
    gk.execute.assert_called_once()
    client.search.assert_called_once()


def test_search_does_not_call_gatekeeper_on_empty_query():
    """Empty queries short-circuit BEFORE the gate — saves a slot for real work."""
    client = MagicMock()
    gk = MagicMock()
    factory = MagicMock(return_value=client)
    with patch.dict(sys.modules, {"tavily": _stub_tavily_module(factory)}):
        search = make_tavily_search("test-key", gatekeeper=gk)
    assert search("") == []
    gk.execute.assert_not_called()
    client.search.assert_not_called()


def test_search_caps_at_three_results():
    response = {"results": [
        {"title": f"T{i}", "url": f"https://e/{i}"} for i in range(10)
    ]}
    search, _ = _build_search(response)
    out = search("query")
    assert len(out) == 3


def test_search_falls_back_to_url_only_when_title_missing():
    response = {"results": [{"title": "", "url": "https://example.org/page"}]}
    search, _ = _build_search(response)
    assert search("query") == ["https://example.org/page"]


def test_search_falls_back_to_title_only_when_url_missing():
    response = {"results": [{"title": "Untitled-URL Result", "url": ""}]}
    search, _ = _build_search(response)
    assert search("query") == ["Untitled-URL Result"]


def test_search_skips_results_with_neither_title_nor_url():
    response = {"results": [
        {"title": "", "url": ""},
        {"title": "Good", "url": "https://good"},
    ]}
    search, _ = _build_search(response)
    assert search("query") == ["Good — https://good"]


def test_search_empty_query_short_circuits():
    search, client = _build_search({"results": [{"title": "x", "url": "y"}]})
    assert search("") == []
    assert search("   ") == []
    client.search.assert_not_called()


def test_search_handles_missing_results_key():
    search, _ = _build_search({})
    assert search("query") == []


def test_search_handles_non_dict_response():
    search, _ = _build_search("oops not a dict")
    assert search("query") == []


# ---------------------------------------------------------------------------
# _format_results edge cases (unit-level on the pure helper)
# ---------------------------------------------------------------------------

def test_format_results_handles_none():
    assert _format_results(None) == []


def test_format_results_handles_list_response():
    assert _format_results([{"title": "x", "url": "y"}]) == []
