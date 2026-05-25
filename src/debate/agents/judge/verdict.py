"""Verdict computation — PersuasionScore dataclass and DeclareVerdict skill."""

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

_WT = {
    "improved": "{w}'s scores rose ({e:.2f}->{l:.2f}), reflecting strong integration of the Judge's directives.",
    "declined": "{w}'s scores dipped ({e:.2f}->{l:.2f}); nonetheless the early lead secured overall victory.",
    "held steady": "{w} maintained steady performance ({e:.2f}->{l:.2f}), never deviating from its strongest line.",
}
_LT = {
    "improved": "{l} showed responsiveness ({e:.2f}->{la:.2f}), but adaptation came too late to close the gap.",
    "declined": "{l}'s performance deteriorated ({e:.2f}->{la:.2f}), showing difficulty incorporating judicial feedback.",
    "held steady": "{l} performed consistently but uncompetitively ({e:.2f}->{la:.2f}), with insufficient responsiveness.",
}


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


def _trend(early: float, late: float) -> str:
    if late > early + 0.02:
        return "improved"
    if late < early - 0.02:
        return "declined"
    return "held steady"


def _build_verdict_justification(
    winner: str, loser: str, w_scores: list, l_scores: list, winner_pct: int, loser_pct: int,
) -> str:
    rounds = max(len(w_scores), len(l_scores))
    _avg = lambda s, a: sum(getattr(x, a) for x in s) / len(s)  # noqa: E731
    wl = _avg(w_scores, "logical_consistency")
    wc = _avg(w_scores, "citation_strength")
    wr = _avg(w_scores, "rhetoric_quality")
    ll = _avg(l_scores, "logical_consistency")
    lc = _avg(l_scores, "citation_strength")
    lr = _avg(l_scores, "rhetoric_quality")

    paired = list(zip(w_scores, l_scores, strict=False))
    if paired:
        best = max(paired, key=lambda p: p[0].weighted - p[1].weighted)
        worst = min(paired, key=lambda p: p[0].weighted - p[1].weighted)
        margin = best[0].weighted - best[1].weighted
        clash = (f"Round {best[0].round} was the most decisive exchange: {winner} scored "
                 f"{best[0].weighted:.2f} versus {loser}'s {best[1].weighted:.2f} (margin: {margin:+.2f}). ")
        if len(paired) > 1 and worst[0].round != best[0].round:
            wm = worst[0].weighted - worst[1].weighted
            clash += (
                f"Even {winner}'s narrowest margin (round {worst[0].round}: "
                f"{worst[0].weighted:.2f} vs {worst[1].weighted:.2f}) confirmed consistent superiority."
                if wm > 0 else
                f"{loser}'s strongest counter (round {worst[0].round}: "
                f"{worst[1].weighted:.2f} vs {worst[0].weighted:.2f}) could not overturn the scoring deficit."
            )
    else:
        clash = f"{winner} held a consistent advantage across all {rounds} round(s)."

    mid = max(1, len(w_scores) // 2)
    w_late = w_scores[mid:] or w_scores
    l_late = l_scores[mid:] or l_scores
    we = sum(s.weighted for s in w_scores[:mid]) / mid
    wla = sum(s.weighted for s in w_late) / len(w_late)
    le = sum(s.weighted for s in l_scores[:mid]) / mid
    lla = sum(s.weighted for s in l_late) / len(l_late)
    w_fb = _WT[_trend(we, wla)].format(w=winner, e=we, l=wla)
    l_fb = _LT[_trend(le, lla)].format(l=loser, e=le, la=lla)
    primary = max(
        [("logical consistency (weight 0.50)", wl - ll),
         ("citation strength (weight 0.30)", wc - lc),
         ("rhetoric quality (weight 0.20)", wr - lr)],
        key=lambda x: x[1],
    )[0]

    return "\n\n".join([
        (f"KEY CLASHES — {clash} Across all {rounds} round(s), {winner} consistently "
         f"delivered arguments with greater causal precision, stronger evidential grounding, "
         f"and more effective rhetorical execution than {loser}."),
        f"FEEDBACK ADHERENCE — {w_fb} {l_fb}",
        (f"SCORING BREAKDOWN —\n"
         f"  Logical Consistency (weight 0.50):  {winner} {wl:.2f}  |  {loser} {ll:.2f}\n"
         f"  Citation Strength   (weight 0.30):  {winner} {wc:.2f}  |  {loser} {lc:.2f}\n"
         f"  Rhetoric Quality    (weight 0.20):  {winner} {wr:.2f}  |  {loser} {lr:.2f}\n"
         f"  Final Score:                        {winner} {winner_pct}%  |  {loser} {loser_pct}%"),
        (f"FINAL CONCLUSION — {winner} wins this debate with a final score of "
         f"{winner_pct}% versus {loser_pct}% for {loser} across {rounds} round(s). "
         f"The verdict rests primarily on superior {primary}, where {winner} held a "
         f"clear and sustained advantage. Under the cumulative weighted formula "
         f"(logic=0.50, citation=0.30, rhetoric=0.20), this dimension proved "
         f"determinative. The outcome reflects {winner}'s superior ability to construct, "
         f"sustain, and deliver a persuasive case — consistently outperforming {loser} "
         f"on the dimensions that matter most in structured intellectual discourse."),
    ])


class DeclareVerdict:
    """Compute final cumulative scores and produce a comprehensive verdict message (no ties)."""

    def run(self, scores_pro: list[PersuasionScore], scores_con: list[PersuasionScore]) -> VerdictMessage:
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
        justification = _build_verdict_justification(winner, loser, w_scores, l_scores, winner_pct, loser_pct)
        if len(justification) < MIN_JUSTIFICATION_LENGTH:
            justification += " " * (MIN_JUSTIFICATION_LENGTH - len(justification))
        return VerdictMessage(
            winner=winner, scores={AgentID.PRO: pro_pct, AgentID.CON: con_pct}, justification=justification,
        )
