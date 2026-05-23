"""JudgeAgent — moderates the debate, scores arguments, declares the verdict."""

from collections.abc import Callable

from debate.agents.base_agent import BaseAgent
from debate.agents.judge.skills import (
    DeclareVerdict,
    EnforceDebateMechanics,
    EvaluatePersuasionScore,
    PersuasionScore,
    RouteTurn,
)
from debate.ipc.schemas import ArgumentMessage
from debate.shared.constants import AgentID


class JudgeAgent(BaseAgent):
    """Runs inside the Judge subprocess.

    Registers exactly four skills (no WebSearchTool — no internet access).
    Processes ArgumentMessages and produces routing, reprimand, or verdict
    messages back to the orchestrator.
    """

    def __init__(
        self,
        evaluate_llm: Callable,
        route_llm: Callable,
        stdin=None,
        stdout=None,
    ) -> None:
        super().__init__(AgentID.JUDGE, stdin, stdout)
        self._evaluate_llm = evaluate_llm
        self._route_llm = route_llm

        self._enforce = EnforceDebateMechanics()
        self._evaluate = EvaluatePersuasionScore()
        self._route = RouteTurn()
        self._verdict = DeclareVerdict()

        for skill in (self._enforce, self._evaluate, self._route, self._verdict):
            self.register_skill(skill)

        self._scores: dict[str, list[PersuasionScore]] = {
            AgentID.PRO: [],
            AgentID.CON: [],
        }
        self._last_arguments: dict[str, str] = {}
        self._round: int = 0

    # ------------------------------------------------------------------
    # Public methods called by the orchestrator
    # ------------------------------------------------------------------

    def process_argument(self, msg: ArgumentMessage) -> None:
        """Enforce mechanics; if valid, evaluate and route to next agent."""
        reprimand = self._enforce.run(
            msg,
            round_number=self._round + 1,
            fallacy_ignored=False,
        )
        if reprimand:
            self.send(reprimand.to_dict())
            return

        score = self._evaluate.run(msg, self._evaluate_llm)
        self._scores[msg.agent_id].append(score)
        self._last_arguments[msg.agent_id] = msg.argument
        self._round += 1

        next_agent = AgentID.CON if msg.agent_id == AgentID.PRO else AgentID.PRO
        routing = self._route.run(score, next_agent, self._route_llm)
        self.send(routing.to_dict())

    def declare_verdict(self) -> None:
        """Compute final scores and send the verdict message."""
        verdict = self._verdict.run(
            self._scores[AgentID.PRO],
            self._scores[AgentID.CON],
        )
        self.send(verdict.to_dict())
