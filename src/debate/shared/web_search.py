"""Web search providers — pluggable search callables consumed by WebSearchTool.

The consumer contract is intentionally narrow:
    search_call: Callable[[str], list[str]]
each item being a single, human-readable citation string (used verbatim by
the `synthesize_evidence` skill, which joins them with "; ").

This module currently exposes a Tavily-backed implementation. When an
`ApiGatekeeper` is supplied, the network call is routed through it so the
Tavily web-search rate limits from `config/rate_limits.json` (service
"web_search") are enforced and call counts are tracked. No token cost — Tavily
doesn't bill per token.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable

from debate.shared.gatekeeper import ApiGatekeeper

_log = logging.getLogger("debate.tavily")

# Match WebSearchTool.MAX_RESULTS — no point fetching more than the tool will keep.
_MAX_RESULTS = 3

# Social-media and forum domains that produce low-credibility citations for a
# graded debate. Tavily's `exclude_domains` filters these server-side so the
# tool surfaces news, research, institutional, and think-tank sources instead.
_EXCLUDED_DOMAINS = ["facebook.com", "quora.com", "reddit.com", "pinterest.com"]


def make_tavily_search(
    api_key: str,
    gatekeeper: ApiGatekeeper | None = None,
    label: str = "tavily",
) -> Callable[[str], list[str]]:
    """Return a search callable backed by Tavily's REST API.

    The returned function maps `query: str` → `list[str]` where each string is
    `"<title> — <url>"`. Empty queries short-circuit to `[]`. When `gatekeeper`
    is provided, the actual HTTP call goes through `gatekeeper.execute(...)`
    so web-search rate limits (rate_limits.json service "web_search") are
    enforced and call counts accumulate. Network or serialization failures
    propagate; `WebSearchTool` already isolates them.

    `label` is used in the per-call timing log line.
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
        start = time.time()
        def _do():
            return client.search(
                query=query,
                max_results=_MAX_RESULTS,
                search_depth="advanced",
                exclude_domains=_EXCLUDED_DOMAINS,
            )
        if gatekeeper is None:
            response = _do()
        else:
            response = gatekeeper.execute(_do)
        results = _format_results(response)
        _log.info(
            "[%s] query=%r took=%.2fs results=%d",
            label, (query[:80] + "…") if len(query) > 80 else query,
            time.time() - start, len(results),
        )
        return results

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
