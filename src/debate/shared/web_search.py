"""Web search providers — pluggable search callables consumed by WebSearchTool.

The consumer contract is intentionally narrow:
    search_call: Callable[[str], list[str]]
each item being a single, human-readable citation string (used verbatim by
the `synthesize_evidence` skill, which joins them with "; ").

This module currently exposes a Tavily-backed implementation. Future providers
(or a gatekeeper wrapper) plug in by satisfying the same callable shape.
"""

from __future__ import annotations

from collections.abc import Callable

# Match WebSearchTool.MAX_RESULTS — no point fetching more than the tool will keep.
_MAX_RESULTS = 3


def make_tavily_search(api_key: str) -> Callable[[str], list[str]]:
    """Return a search callable backed by Tavily's REST API.

    The returned function maps `query: str` → `list[str]` where each string is
    `"<title> — <url>"`. Empty queries short-circuit to `[]`. Network or
    serialization failures propagate; `WebSearchTool` already isolates them.
    """
    if not api_key:
        raise ValueError("Tavily API key must be a non-empty string")

    # Import here so unit tests that don't exercise this provider don't pay
    # the import cost or need the package installed at import time.
    from tavily import TavilyClient

    client = TavilyClient(api_key=api_key)

    def search(query: str) -> list[str]:
        if not query or not query.strip():
            return []
        response = client.search(
            query=query,
            max_results=_MAX_RESULTS,
            search_depth="basic",
        )
        return _format_results(response)

    return search


def _format_results(response: object) -> list[str]:
    """Extract up to _MAX_RESULTS Tavily hits as 'Title — URL' strings."""
    if not isinstance(response, dict):
        return []
    results = response.get("results") or []
    out: list[str] = []
    for hit in results[:_MAX_RESULTS]:
        if not isinstance(hit, dict):
            continue
        title = (hit.get("title") or "").strip()
        url = (hit.get("url") or "").strip()
        if title and url:
            out.append(f"{title} — {url}")
        elif url:
            out.append(url)
        elif title:
            out.append(title)
    return out
