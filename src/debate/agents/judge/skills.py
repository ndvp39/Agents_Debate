"""Judge agent skills — EnforceDebateMechanics, EvaluatePersuasionScore, RouteTurn."""

from collections.abc import Callable

from debate.agents.judge.verdict import PersuasionScore
from debate.ipc.schemas import ArgumentMessage, ReprimandMessage, RoutingMessage

_AGREEMENT_PHRASES = (
    "i agree", "you make a good point", "that's correct",
    "you're right", "well said", "i concede", "you are correct",
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

    def run(
        self,
        msg: ArgumentMessage,
        llm_call: Callable,
        previous_feedback: str = "",
        previous_own_argument: str = "",
        opponent_last_argument: str = "",
    ) -> PersuasionScore:
        argument = msg.argument
        ctx: list[str] = []
        if previous_feedback:
            ctx.append(
                f"[FEEDBACK ENFORCEMENT: Your previous instruction to this debater was: "
                f"'{previous_feedback}'. Penalise all dimensions if ignored; "
                f"award a score boost if followed well.]"
            )
        if previous_own_argument:
            snippet = previous_own_argument[:300]
            ctx.append(
                f"[NOVELTY CHECK: This agent's prior argument started: '{snippet}'. "
                f"If the current argument repeats the same core claims without adding new "
                f"evidence, angles, or refutations, penalise logical_consistency and "
                f"citation_strength significantly.]"
            )
        if opponent_last_argument:
            snippet = opponent_last_argument[:300]
            ctx.append(
                f"[REFUTATION CHECK: The opponent's most recent argument started: '{snippet}'. "
                f"If this agent failed to directly counter or refute a specific attack made "
                f"by the opponent, penalise logical_consistency.]"
            )
        if ctx:
            argument = "\n".join(ctx) + "\n\n" + argument
        result = llm_call(argument, msg.citations)
        return PersuasionScore(
            agent_id=msg.agent_id,
            round=msg.round,
            logical_consistency=float(result["logical_consistency"]),
            citation_strength=float(result["citation_strength"]),
            rhetoric_quality=float(result["rhetoric_quality"]),
        )


class RouteTurn:
    """Produce a routing message directing the next debater."""

    def run(
        self,
        score: PersuasionScore,
        next_agent: str,
        llm_call: Callable,
        previous_feedback: str = "",
    ) -> RoutingMessage:
        fb_line = (
            f" Your previous instruction to this agent was: '{previous_feedback}'. "
            "State explicitly whether it was followed this round."
            if previous_feedback else ""
        )
        route_prompt = (
            f"You are a strict debate judge providing round-specific feedback. "
            f"This argument scored: logic={score.logical_consistency:.2f}, "
            f"citation={score.citation_strength:.2f}, "
            f"rhetoric={score.rhetoric_quality:.2f}.{fb_line}\n"
            "Give 2-3 sentences of precise, actionable feedback:\n"
            "1. Name the weakest scoring dimension and explain exactly why it lost points.\n"
            "2. If arguments were repeated from a prior round, call this out explicitly.\n"
            "3. Give one concrete, specific instruction this agent MUST act on next round."
        )
        feedback = str(llm_call(route_prompt))
        if previous_feedback:
            prompt = (
                f"It is your turn now, {next_agent}. Respond directly to the previous argument. "
                f"REMINDER — The Judge previously instructed you: '{previous_feedback}'. "
                "You MUST address this directive explicitly. Failure to comply will result in a score penalty."
            )
        else:
            prompt = f"It is your turn now, {next_agent}. Respond directly to the previous argument."
        return RoutingMessage(
            target_agent=next_agent,
            judge_feedback=feedback,
            prompt_for_next=prompt,
        )
