"""Deterministic strategy-selection skill — picks defensive/offensive/pivot mode."""


def run(
    round_number: int,
    own_score: float,
    opp_score: float,
    analysis: dict,
    fallacies: dict,
) -> dict:
    if own_score < opp_score:
        mode = "defensive"
    elif own_score > opp_score:
        mode = "offensive"
    else:
        mode = "pivot"
    target = analysis.get("weakest_point", "opponent's main claim")
    return {
        "mode": mode,
        "target": target,
        "rationale": f"Round {round_number}: {mode} chosen (own={own_score:.2f}, opp={opp_score:.2f}).",
    }
