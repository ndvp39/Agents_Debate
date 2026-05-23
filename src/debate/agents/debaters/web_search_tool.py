"""WebSearchTool — retrieves citations via an injected search callable (ApiGatekeeper-wrapped)."""

import sys
from typing import Callable


class WebSearchTool:
    """Wraps a gatekeeper-wrapped search callable; returns up to 3 results.

    All real API calls must be made by passing a gatekeeper-wrapped callable
    at construction time. On any search failure, returns an empty list so the
    debater can still respond without crashing.
    """

    MAX_RESULTS: int = 3

    def __init__(self, search_call: Callable) -> None:
        self._search_call = search_call

    def search(self, query: str) -> list[str]:
        """Run a search and return up to MAX_RESULTS citation strings."""
        try:
            results = self._search_call(query)
            return list(results)[: self.MAX_RESULTS] if results else []
        except Exception as exc:
            print(f"WebSearchTool: search failed — {exc}", file=sys.stderr)
            return []
