"""JudgeAgent — moderates the debate, scores arguments, declares the verdict."""

from collections.abc import Callable

from debate.agents.base_agent import BaseAgent
from debate.agents.judge.verdict import DeclareVerdict, PersuasionScore
from debate.ipc.schemas import ArgumentMessage, RoutingMessage
from debate.shared.constants import AgentID
from debate.skills.loader import SkillLoader


class JudgeAgent(BaseAgent):
    """Runs inside the Judge subprocess.

    Drives the judge skill pipeline (enforce, evaluate, generate-feedback,
    compose-next-turn) through a project-local SkillLoader, then declares the
    verdict at the end of the debate.
    """

    def __init__(
        self,
        evaluate_llm: Callable,
        route_llm: Callable,
        verdict_llm: Callable | None = None,
        stdin=None,
        stdout=None,
        skills: SkillLoader | None = None,
    ) -> None:
        super().__init__(AgentID.JUDGE, stdin, stdout, skills=skills)
        self._evaluate_llm = evaluate_llm
        self._route_llm = route_llm
        self._verdict_llm = verdict_llm
        self._verdict = DeclareVerdict()

        self._scores: dict[str, list[PersuasionScore]] = {
            AgentID.PRO: [],
            AgentID.CON: [],
        }
        self._last_arguments: dict[str, str] = {}
        self._last_feedback_sent: dict[str, str] = {AgentID.PRO: "", AgentID.CON: ""}
        self._round: int = 0

    # ------------------------------------------------------------------
    # Public methods called by the orchestrator
    # ------------------------------------------------------------------

    def process_argument(self, msg: ArgumentMessage) -> None:
        """Enforce mechanics; if valid, evaluate and route to next agent."""
        reprimand = self._skills.load("enforce_debate_mechanics").run(
            msg,
            round_number=self._round + 1,
            fallacy_ignored=False,
        )
        if reprimand:
            self.send(reprimand.to_dict())
            return

        previous_fb = self._last_feedback_sent.get(msg.agent_id, "")
        prev_own_arg = self._last_arguments.get(msg.agent_id, "")
        opponent = AgentID.CON if msg.agent_id == AgentID.PRO else AgentID.PRO
        opp_last_arg = self._last_arguments.get(opponent, "")
        score = self._evaluate(msg, previous_fb, prev_own_arg, opp_last_arg)
        self._scores[msg.agent_id].append(score)
        self._last_arguments[msg.agent_id] = msg.argument
        self._round += 1

        next_agent = AgentID.CON if msg.agent_id == AgentID.PRO else AgentID.PRO
        routing = self._build_routing(score, next_agent, previous_argument=msg.argument)
        self._last_feedback_sent[next_agent] = routing.judge_feedback
        self.send(routing.to_dict())

    def declare_verdict(self) -> None:
        """Compute final scores and send the verdict message."""
        verdict = self._verdict.run(
            self._scores[AgentID.PRO],
            self._scores[AgentID.CON],
            llm_call=self._verdict_llm,
        )
        self.send(verdict.to_dict())

    # ------------------------------------------------------------------
    # Internal: skill orchestration
    # ------------------------------------------------------------------

    def _evaluate(
        self,
        msg: ArgumentMessage,
        previous_feedback: str,
        previous_own_argument: str,
        opponent_last_argument: str,
    ) -> PersuasionScore:
        prompt = self._skills.load("evaluate_persuasion_score").render(
            argument=msg.argument,
            citations=msg.citations,
            feedback_context=self._feedback_context(previous_feedback),
            novelty_context=self._novelty_context(previous_own_argument),
            refutation_context=self._refutation_context(opponent_last_argument),
        )
        result = self._evaluate_llm(prompt)
        return PersuasionScore(
            agent_id=msg.agent_id,
            round=msg.round,
            logical_consistency=float(result["logical_consistency"]),
            citation_strength=float(result["citation_strength"]),
            rhetoric_quality=float(result["rhetoric_quality"]),
        )

    def _build_routing(
        self,
        score: PersuasionScore,
        next_agent: str,
        previous_argument: str,
    ) -> RoutingMessage:
        previous_feedback = self._last_feedback_sent.get(next_agent, "")
        feedback_prompt = self._skills.load("generate_judge_feedback").render(
            logical_consistency=f"{score.logical_consistency:.2f}",
            citation_strength=f"{score.citation_strength:.2f}",
            rhetoric_quality=f"{score.rhetoric_quality:.2f}",
            prior_feedback_followup=self._prior_feedback_followup(previous_feedback),
        )
        feedback = str(self._route_llm(feedback_prompt))
        prompt_for_next = self._skills.load("compose_next_turn_prompt").run(
            next_agent=next_agent,
            judge_feedback_reminder=self._reminder_block(next_agent, previous_feedback),
        )
        return RoutingMessage(
            target_agent=next_agent,
            judge_feedback=feedback,
            prompt_for_next=prompt_for_next,
            previous_argument=previous_argument,
        )

    # ------------------------------------------------------------------
    # Internal: context-block assembly (pre-formatted strings the skills consume)
    # ------------------------------------------------------------------

    @staticmethod
    def _feedback_context(previous_feedback: str) -> str:
        if not previous_feedback:
            return ""
        return (
            f"[FEEDBACK ENFORCEMENT: Your previous instruction to this debater was: "
            f"'{previous_feedback}'. Penalise all dimensions if ignored; "
            f"award a score boost if followed well.]"
        )

    @staticmethod
    def _novelty_context(previous_own_argument: str) -> str:
        if not previous_own_argument:
            return ""
        snippet = previous_own_argument[:300]
        return (
            f"[NOVELTY CHECK: This agent's prior argument started: '{snippet}'. "
            f"If the current argument repeats the same core claims without adding new "
            f"evidence, angles, or refutations, penalise logical_consistency and "
            f"citation_strength significantly.]"
        )

    @staticmethod
    def _refutation_context(opponent_last_argument: str) -> str:
        if not opponent_last_argument:
            return ""
        snippet = opponent_last_argument[:300]
        return (
            f"[REFUTATION CHECK: The opponent's most recent argument started: '{snippet}'. "
            f"If this agent failed to directly counter or refute a specific attack made "
            f"by the opponent, penalise logical_consistency.]"
        )

    @staticmethod
    def _prior_feedback_followup(previous_feedback: str) -> str:
        if not previous_feedback:
            return ""
        return (
            f" Your previous instruction to this agent was: '{previous_feedback}'. "
            "State explicitly whether it was followed this round."
        )

    @staticmethod
    def _reminder_block(next_agent: str, previous_feedback: str) -> str:
        if not previous_feedback:
            return ""
        return (
            f"REMINDER — The Judge previously instructed you: '{previous_feedback}'. "
            "You MUST address this directive explicitly. Failure to comply will result in a score penalty."
        )
