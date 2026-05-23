"""Debater skills — 7-skill pipeline for genius-level debate reasoning."""

from collections.abc import Callable

from debate.shared.exceptions import SkillNotApplicableError


class CraftOpening:
    """Round 1 only: establish the strongest initial case for the assigned stance."""

    def run(self, topic: str, stance: str, round_number: int, llm_call: Callable) -> dict:
        if round_number != 1:
            raise SkillNotApplicableError(f"CraftOpening only runs on round 1, got {round_number}")
        prompt = (
            f"Topic: {topic}\nStance: {stance}\n"
            "Deliver the strongest possible opening statement. State your position boldly, "
            "preview your three strongest arguments, and end with a memorable hook. "
            "Do NOT acknowledge the opposing side yet."
        )
        return {"opening_statement": str(llm_call(prompt))}


class AnalyzeOpponent:
    """Deconstruct the opponent's last argument to expose its structure and vulnerabilities."""

    def run(self, opponent_argument: str, llm_call: Callable) -> dict:
        prompt = (
            f"Analyze this argument:\n{opponent_argument}\n"
            "Identify: (1) main claim, (2) supporting points, (3) hidden assumptions, (4) weakest point."
        )
        response = llm_call(prompt)
        if isinstance(response, dict):
            return response
        text = str(response)
        return {"main_claim": text, "supporting_points": [], "assumptions": [], "weakest_point": text}


class DetectFallacies:
    """Explicitly name logical fallacies present in the opponent's argument."""

    def run(self, opponent_argument: str, analysis: dict, llm_call: Callable) -> dict:
        prompt = (
            f"Find logical fallacies in:\n{opponent_argument}\n"
            "Name each fallacy and explain how it appears. If none, state 'No fallacies detected.'"
        )
        response = llm_call(prompt)
        if isinstance(response, dict):
            return response
        return {"fallacies_found": [], "fallacy_descriptions": [str(response)]}


class AdaptStrategy:
    """Decide the optimal debate strategy based on score comparison (deterministic)."""

    def run(
        self,
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


class BuildCounterArgument:
    """Construct a targeted, logically airtight rebuttal."""

    def run(
        self,
        stance: str,
        topic: str,
        analysis: dict,
        fallacies: dict,
        strategy: dict,
        citations: list,
        llm_call: Callable,
        judge_feedback: str = "",
    ) -> dict:
        target = strategy.get("target", "opponent's claim")
        feedback_block = ""
        if judge_feedback:
            feedback_block = (
                f"\n\nJUDGE'S FEEDBACK (MANDATORY): {judge_feedback}\n"
                "You MUST directly adapt your argument to address this feedback. "
                "If the Judge asked for specific data, statistics, or citations, you MUST provide them NOW."
            )
        prompt = (
            f"Stance: {stance}\nTopic: {topic}\nTarget: {target}\n"
            "Construct a devastating counter-argument. Directly address the weakest point. "
            "Call out any fallacies by name. Never agree or soften your position. "
            "You MUST explicitly quote at least one specific statistic, study name, or expert opinion."
            + feedback_block
        )
        return {"counter_argument": str(llm_call(prompt))}


class SynthesizeEvidence:
    """Select and weave the strongest citations into the argument (deterministic)."""

    MAX_CITATIONS = 3

    def run(self, argument_draft: str, raw_search_results: list) -> dict:
        citations = list(raw_search_results)[: self.MAX_CITATIONS]
        if citations:
            sources_line = "\n\nSources: " + "; ".join(citations)
            enriched = argument_draft + sources_line
        else:
            enriched = argument_draft
        return {"citations": citations, "enriched_argument": enriched}


class ApplyRhetoric:
    """Final skill: elevate the argument with classical rhetorical techniques."""

    def run(
        self,
        enriched_argument: str,
        stance: str,
        round_number: int,
        llm_call: Callable,
        judge_feedback: str = "",
    ) -> dict:
        mandate = f"\nJUDGE'S MANDATE: {judge_feedback}  Ensure the final argument honors this." if judge_feedback else ""
        prompt = (
            f"Round {round_number} | Stance: {stance}\n"
            f"Refine with ethos, pathos, logos, analogy, and a memorable closing:\n{enriched_argument}\n"
            "Do NOT change factual content or citations."
            + mandate
        )
        return {"final_argument": str(llm_call(prompt))}
