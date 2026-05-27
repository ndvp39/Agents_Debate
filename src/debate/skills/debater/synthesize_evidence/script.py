"""Deterministic evidence-synthesis skill: append top-N citations to the argument."""

MAX_CITATIONS = 3


def run(argument_draft: str, raw_search_results: list) -> dict:
    citations = list(raw_search_results)[:MAX_CITATIONS]
    if citations:
        sources_line = "\n\nSources: " + "; ".join(citations)
        enriched = argument_draft + sources_line
    else:
        enriched = argument_draft
    return {"citations": citations, "enriched_argument": enriched}
