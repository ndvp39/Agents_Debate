"""Judge agent skills — EnforceDebateMechanics, EvaluatePersuasionScore, RouteTurn, DeclareVerdict."""

from dataclasses import dataclass
from typing import Callable

from debate.ipc.schemas import ArgumentMessage, ReprimandMessage, RoutingMessage, VerdictMessage
from debate.shared.constants import AgentID, MIN_JUSTIFICATION_LENGTH, SCORE_WEIGHT_CITATION, SCORE_WEIGHT_LOGIC, SCORE_WEIGHT_RHETORIC
from debate.shared.exceptions import InsufficientDataError

_AGREEMENT_PHRASES = (
    "i agree", "you make a good point", "that's correct",
    "you're right", "well said", "i concede", "you are correct",
)


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
        return (
            SCORE_WEIGHT_LOGIC * self.logical_consistency
            + SCORE_WEIGHT_CITATION * self.citation_strength
            + SCORE_WEIGHT_RHETORIC * self.rhetoric_quality
        )


class EnforceDebateMechanics:
    """Check an argument for rule violations; return a ReprimandMessage or None."""

    def run(
        self,
        msg: ArgumentMessage,
        *,
        round_number: int = 1,
        fallacy_ignored: bool = False,
    ) -> ReprimandMessage | None:
        if not msg.citations:
            return ReprimandMessage(
                target_agent=msg.agent_id,
                prompt_for_next="You must include at least one citation. Rewrite your argument with sources.",
            )
        arg_lower = msg.argument.lower()
        for phrase in _AGREEMENT_PHRASES:
            if phrase in arg_lower:
                return ReprimandMessage(
                    target_agent=msg.agent_id,
                    prompt_for_next="Sycophantic language detected. Maintain your position and rewrite.",
                )
        if round_number >= 2 and fallacy_ignored:
            return ReprimandMessage(
                target_agent=msg.agent_id,
                prompt_for_next="You failed to identify an obvious logical fallacy. Address it and rewrite.",
            )
        return None


class EvaluatePersuasionScore:
    """Score one argument on three dimensions via an LLM call."""

    def run(self, msg: ArgumentMessage, llm_call: Callable) -> PersuasionScore:
        result = llm_call(msg.argument, msg.citations)
        return PersuasionScore(
            agent_id=msg.agent_id,
            round=msg.round,
            logical_consistency=float(result["logical_consistency"]),
            citation_strength=float(result["citation_strength"]),
            rhetoric_quality=float(result["rhetoric_quality"]),
        )


class RouteTurn:
    """Produce a routing message directing the next debater."""

    def run(self, score: PersuasionScore, next_agent: str, llm_call: Callable) -> RoutingMessage:
        feedback = str(llm_call(score))
        return RoutingMessage(
            target_agent=next_agent,
            judge_feedback=feedback,
            prompt_for_next=f"It is your turn now, {next_agent}. Respond directly to the previous argument.",
        )


class DeclareVerdict:
    """Compute final cumulative scores and produce a verdict message (no ties)."""

    def run(
        self,
        scores_pro: list[PersuasionScore],
        scores_con: list[PersuasionScore],
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
        pro_pct = round(pro_avg * 100)
        con_pct = round(con_avg * 100)
        if pro_pct == con_pct:
            if pro_avg > con_avg:
                pro_pct += 1
            else:
                con_pct += 1

        rounds = max(len(scores_pro), len(scores_con))
        justification = (
            f"{winner} demonstrated superior persuasion across {rounds} round(s). "
            f"Logic {pro_avg:.2f} vs {con_avg:.2f}; "
            f"rhetoric and citation quality consistently favoured {winner}."
        )
        if len(justification) < MIN_JUSTIFICATION_LENGTH:
            justification += " " * (MIN_JUSTIFICATION_LENGTH - len(justification))

        return VerdictMessage(
            winner=winner,
            scores={AgentID.PRO: pro_pct, AgentID.CON: con_pct},
            justification=justification,
        )
