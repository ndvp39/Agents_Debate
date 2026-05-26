"""Verdict computation — PersuasionScore dataclass and DeclareVerdict skill."""

from collections.abc import Callable
from dataclasses import dataclass

from debate.ipc.schemas import VerdictMessage
from debate.shared.constants import (
    MIN_JUSTIFICATION_LENGTH,
    SCORE_WEIGHT_CITATION,
    SCORE_WEIGHT_LOGIC,
    SCORE_WEIGHT_RHETORIC,
    AgentID,
)
from debate.shared.exceptions import InsufficientDataError


@dataclass
class PersuasionScore:
    """Round-level persuasion score for one debater."""

    agent_id: str
    round: int
    logical_consistency: float
    citation_strength: float
    rhetoric_quality: float

    @property
    def weighted(self) -> float:
        return (SCORE_WEIGHT_LOGIC * self.logical_consistency
                + SCORE_WEIGHT_CITATION * self.citation_strength
                + SCORE_WEIGHT_RHETORIC * self.rhetoric_quality)


def _build_verdict_context(
    winner: str, loser: str,
    w_scores: list, l_scores: list,
    winner_pct: int, loser_pct: int,
) -> str:
    """Format round-by-round score data into a structured text block."""
    rounds = max(len(w_scores), len(l_scores))
    _avg = lambda s, a: sum(getattr(x, a) for x in s) / len(s)  # noqa: E731
    wl, wc, wr = _avg(w_scores, "logical_consistency"), _avg(w_scores, "citation_strength"), _avg(w_scores, "rhetoric_quality")
    ll, lc, lr = _avg(l_scores, "logical_consistency"), _avg(l_scores, "citation_strength"), _avg(l_scores, "rhetoric_quality")

    rows = [f"RESULT: {winner} {winner_pct}% vs {loser} {loser_pct}% over {rounds} rounds\n"]
    rows.append("ROUND-BY-ROUND (logic / citation / rhetoric [weighted]):")
    for ws, ls in zip(w_scores, l_scores, strict=False):
        rows.append(
            f"  R{ws.round}: {winner} {ws.logical_consistency:.2f}/{ws.citation_strength:.2f}/"
            f"{ws.rhetoric_quality:.2f} [{ws.weighted:.2f}]"
            f" | {loser} {ls.logical_consistency:.2f}/{ls.citation_strength:.2f}/"
            f"{ls.rhetoric_quality:.2f} [{ls.weighted:.2f}]"
        )
    rows.append("\nDIMENSION AVERAGES (Logic×0.50 + Citation×0.30 + Rhetoric×0.20):")
    rows.append(f"  Logical Consistency : {winner} {wl:.2f}  |  {loser} {ll:.2f}")
    rows.append(f"  Citation Strength   : {winner} {wc:.2f}  |  {loser} {lc:.2f}")
    rows.append(f"  Rhetoric Quality    : {winner} {wr:.2f}  |  {loser} {lr:.2f}")
    return "\n".join(rows)


def _build_verdict_prompt(context: str, winner: str, loser: str) -> str:
    """Wrap the score context in instructions for the LLM judge."""
    return (
        "You are a senior debate judge delivering a final verdict. "
        "Write an authoritative, analytical verdict based on the scoring data below.\n\n"
        f"{context}\n\n"
        "Write EXACTLY these four labelled sections — no other text:\n"
        "KEY CLASHES — identify the 2-3 most pivotal rounds; name them by number and explain "
        "what made each decisive (a devastating counter, a citation gap, superior logic).\n"
        "FEEDBACK ADHERENCE — which debater adapted better to round-by-round instructions "
        "and what evidence in the scores supports this.\n"
        "SCORING BREAKDOWN — interpret the dimension averages; what do they reveal about "
        "each side's strategic strengths and weaknesses.\n"
        f"FINAL CONCLUSION — deliver a decisive verdict explaining WHY {winner} won and "
        f"what ultimately separated {winner} from {loser}.\n\n"
        "Be specific and analytical. Reference round numbers and scores."
    )


class DeclareVerdict:
    """Compute final cumulative scores and produce a comprehensive verdict (no ties)."""

    def run(
        self,
        scores_pro: list[PersuasionScore],
        scores_con: list[PersuasionScore],
        llm_call: Callable | None = None,
    ) -> VerdictMessage:
        if not scores_pro or not scores_con:
            raise InsufficientDataError("No scores recorded — cannot declare verdict.")
        pro_avg = sum(s.weighted for s in scores_pro) / len(scores_pro)
        con_avg = sum(s.weighted for s in scores_con) / len(scores_con)
        if abs(pro_avg - con_avg) < 1e-9:
            pro_cite = sum(s.citation_strength for s in scores_pro) / len(scores_pro)
            con_cite = sum(s.citation_strength for s in scores_con) / len(scores_con)
            if pro_cite >= con_cite:
                pro_avg += 0.01
            else:
                con_avg += 0.01
        winner = AgentID.PRO if pro_avg > con_avg else AgentID.CON
        loser = AgentID.CON if winner == AgentID.PRO else AgentID.PRO
        pro_pct = round(pro_avg * 100)
        con_pct = round(con_avg * 100)
        if pro_pct == con_pct:
            if pro_avg > con_avg:
                pro_pct += 1
            else:
                con_pct += 1
        winner_pct = pro_pct if winner == AgentID.PRO else con_pct
        loser_pct = con_pct if winner == AgentID.PRO else pro_pct
        w_scores = scores_pro if winner == AgentID.PRO else scores_con
        l_scores = scores_con if winner == AgentID.PRO else scores_pro

        context = _build_verdict_context(winner, loser, w_scores, l_scores, winner_pct, loser_pct)
        if llm_call is not None:
            justification = llm_call(_build_verdict_prompt(context, winner, loser))
        else:
            justification = context
        if len(justification) < MIN_JUSTIFICATION_LENGTH:
            justification += " " * (MIN_JUSTIFICATION_LENGTH - len(justification))
        return VerdictMessage(
            winner=winner,
            scores={AgentID.PRO: pro_pct, AgentID.CON: con_pct},
            justification=justification,
        )
