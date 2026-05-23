"""BaseDebater — 7-skill pipeline with anti-sycophancy enforcement for both debater agents."""

from collections.abc import Callable
from typing import Any

from debate.agents.base_agent import BaseAgent
from debate.agents.debaters.skills import (
    AdaptStrategy,
    AnalyzeOpponent,
    ApplyRhetoric,
    BuildCounterArgument,
    CraftOpening,
    DetectFallacies,
    SynthesizeEvidence,
)
from debate.agents.debaters.web_search_tool import WebSearchTool
from debate.ipc.schemas import ArgumentMessage

_ANTI_SYCOPHANCY = (
    "CRITICAL DIRECTIVE: You are arguing {stance} on \"{topic}\". "
    "You MUST NEVER agree with, compliment, or validate the opposing argument. "
    "Phrases like 'good point', 'I agree', 'you're right' are STRICTLY FORBIDDEN. "
    "Your only goal is to WIN this debate for your side."
)


class BaseDebater(BaseAgent):
    """Shared debater logic: 7-skill pipeline, anti-sycophancy, web-search citations.

    Subclasses must define STANCE as a class attribute.
    """

    STANCE: str = ""

    def __init__(
        self,
        agent_id: str = "",
        topic: str = "",
        llm_call: Callable = None,
        search_call: Callable = None,
        stdin: Any = None,
        stdout: Any = None,
    ) -> None:
        super().__init__(agent_id, stdin, stdout)
        self._topic = topic
        self._llm_call = llm_call
        self._round = 0
        self._last_opponent_arg = ""

        self._web_search = WebSearchTool(search_call or (lambda q: []))
        self._craft = CraftOpening()
        self._analyze = AnalyzeOpponent()
        self._detect = DetectFallacies()
        self._adapt = AdaptStrategy()
        self._build = BuildCounterArgument()
        self._synthesize = SynthesizeEvidence()
        self._rhetoric = ApplyRhetoric()

        for skill in (
            self._web_search, self._craft, self._analyze, self._detect,
            self._adapt, self._build, self._synthesize, self._rhetoric,
        ):
            self.register_skill(skill)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def respond(self, routing_message: dict) -> None:
        """Run the skill pipeline and send an ArgumentMessage."""
        self._last_opponent_arg = routing_message.get("prompt_for_next", "")
        current_round = self._round + 1
        result = self._run_pipeline(current_round)
        self._round = current_round
        citations = result["citations"] or [f"Searched: {self._topic}"]
        msg = ArgumentMessage(
            agent_id=self.agent_id,
            round=current_round,
            argument=result["final_argument"],
            citations=citations,
        )
        self.send(msg.to_dict())

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _run_pipeline(self, round_number: int) -> dict:
        llm = self._wrapped_llm
        raw = self._web_search.search(self._topic)

        if round_number == 1:
            opening = self._craft.run(self._topic, self.STANCE, round_number, llm)
            evidence = self._synthesize.run(opening["opening_statement"], raw)
            rhetoric = self._rhetoric.run(evidence["enriched_argument"], self.STANCE, round_number, llm)
            return {"final_argument": rhetoric["final_argument"], "citations": evidence["citations"]}

        analysis = self._analyze.run(self._last_opponent_arg, llm)
        fallacies = self._detect.run(self._last_opponent_arg, analysis, llm)
        strategy = self._adapt.run(round_number, 0.5, 0.5, analysis, fallacies)
        raw2 = self._web_search.search(analysis.get("weakest_point", self._topic))
        counter = self._build.run(self.STANCE, self._topic, analysis, fallacies, strategy, raw2, llm)
        evidence = self._synthesize.run(counter["counter_argument"], raw + raw2)
        rhetoric = self._rhetoric.run(evidence["enriched_argument"], self.STANCE, round_number, llm)
        return {"final_argument": rhetoric["final_argument"], "citations": evidence["citations"]}

    def _wrapped_llm(self, prompt: str) -> Any:
        directive = _ANTI_SYCOPHANCY.format(stance=self.STANCE, topic=self._topic)
        return self._llm_call(f"{directive}\n\n{prompt}")
