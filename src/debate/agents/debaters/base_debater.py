"""BaseDebater — runs the debater skill pipeline through a project-local SkillLoader."""

from collections.abc import Callable
from typing import Any

from debate.agents.base_agent import BaseAgent
from debate.agents.debaters.web_search_tool import WebSearchTool
from debate.ipc.schemas import ArgumentMessage
from debate.skills.loader import SkillLoader

_ANTI_SYCOPHANCY = (
    "CRITICAL DIRECTIVE: You are arguing {stance} on \"{topic}\". "
    "You MUST NEVER agree with, compliment, or validate the opposing argument. "
    "Phrases like 'good point', 'I agree', 'you're right' are STRICTLY FORBIDDEN. "
    "Your only goal is to WIN this debate for your side."
)

# Honest marker used when web search returned nothing — never reads as a real
# source. ArgumentMessage requires a non-empty citations list, so we emit this
# in lieu of fabricating a citation string.
_NO_SOURCES_MARKER = "[no web sources retrieved]"


class BaseDebater(BaseAgent):
    """Shared debater logic: drives the SKILL.md pipeline via SkillLoader.

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
        skills: SkillLoader | None = None,
    ) -> None:
        super().__init__(agent_id, stdin, stdout, skills=skills)
        self._topic = topic
        self._llm_call = llm_call
        self._round = 0
        self._last_opponent_arg = ""
        self._web_search = WebSearchTool(search_call or (lambda q: []))

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def respond(self, routing_message: dict) -> None:
        """Run the skill pipeline and send an ArgumentMessage."""
        judge_feedback = routing_message.get("judge_feedback", "")
        # The routing message now carries the opponent's actual argument in
        # `previous_argument` (added to RoutingMessage). Empty on the
        # orchestrator's initial round-1 routing — round-1 takes the
        # craft_opening branch and never reads this value.
        self._last_opponent_arg = routing_message.get("previous_argument", "")
        # Sync round counter from the routing message when present so a
        # watchdog-restarted debater resumes on the correct round instead of
        # restarting at round 1 (which would mis-fire craft_opening mid-debate).
        rn = int(routing_message.get("round_number", 0) or 0)
        current_round = rn if rn > 0 else self._round + 1
        result = self._run_pipeline(current_round, judge_feedback)
        self._round = current_round
        # ArgumentMessage rejects empty citations lists, so we still need at
        # least one entry. When the search returned nothing, emit an honest,
        # clearly-not-a-citation marker rather than a fabricated source string.
        citations = result["citations"] or [_NO_SOURCES_MARKER]
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

    def _run_pipeline(self, round_number: int, judge_feedback: str = "") -> dict:
        llm = self._wrapped_llm
        raw = self._web_search.search(self._topic)

        if round_number == 1:
            opening_prompt = self._skills.load("craft_opening").render(
                topic=self._topic,
                stance=self.STANCE,
            )
            opening = str(llm(opening_prompt))
            evidence = self._skills.load("synthesize_evidence").run(opening, raw)
            rhetoric_prompt = self._skills.load("apply_rhetoric").render(
                round_number=round_number,
                stance=self.STANCE,
                enriched_argument=evidence["enriched_argument"],
                judge_mandate_block=self._mandate_block(judge_feedback),
            )
            final = str(llm(rhetoric_prompt))
            return {"final_argument": final, "citations": evidence["citations"]}

        analyze_prompt = self._skills.load("analyze_opponent").render(
            opponent_argument=self._last_opponent_arg,
        )
        analysis = self._coerce_analysis(llm(analyze_prompt))

        fallacies_prompt = self._skills.load("detect_fallacies").render(
            opponent_argument=self._last_opponent_arg,
            analysis=analysis,
        )
        fallacies = self._coerce_fallacies(llm(fallacies_prompt))

        strategy = self._skills.load("adapt_strategy").run(
            round_number, 0.5, 0.5, analysis, fallacies,
        )

        # Build a targeted search query from the opponent's weakest claim, tethered to the debate topic
        # so Tavily stays on-subject. weakest_point can be multi-sentence prose; the helper truncates
        # to keep the final query under Tavily's 400-char limit.
        weakest = analysis.get("weakest_point", "") or analysis.get("main_claim", "")
        search_query = self._build_search_query(self._topic, weakest) or self._topic
        raw2 = self._web_search.search(search_query)

        counter_prompt = self._skills.load("build_counter_argument").render(
            stance=self.STANCE,
            topic=self._topic,
            target=strategy.get("target", "opponent's claim"),
            judge_feedback_block=self._feedback_block(judge_feedback),
        )
        counter = str(llm(counter_prompt))

        # Targeted results first so round-specific sources win the MAX_CITATIONS slots;
        # the generic topic results (raw) act as a fallback if the targeted search returned fewer than 3.
        evidence = self._skills.load("synthesize_evidence").run(counter, raw2 + raw)
        rhetoric_prompt = self._skills.load("apply_rhetoric").render(
            round_number=round_number,
            stance=self.STANCE,
            enriched_argument=evidence["enriched_argument"],
            judge_mandate_block=self._mandate_block(judge_feedback),
        )
        final = str(llm(rhetoric_prompt))
        return {"final_argument": final, "citations": evidence["citations"]}

    def _wrapped_llm(self, prompt: str) -> Any:
        directive = _ANTI_SYCOPHANCY.format(stance=self.STANCE, topic=self._topic)
        return self._llm_call(f"{directive}\n\n{prompt}")

    @staticmethod
    def _build_search_query(topic: str, weakest_point: str) -> str:
        """Build a Tavily-safe targeted query that stays tethered to the debate topic.

        Tavily rejects queries over 400 characters. The LLM's `weakest_point`
        output is often a full paragraph, so we take its first sentence and cap
        at 250 chars; the debate topic leads the query so search results stay
        on-subject rather than drifting toward generic keyword matches. Returns
        "" only when BOTH inputs are empty.
        """
        text = (weakest_point or "").strip()
        for terminator in (". ", "! ", "? ", "\n"):
            idx = text.find(terminator)
            if idx > 0:
                text = text[:idx]
                break
        text = text.strip()[:250].strip()
        topic = (topic or "").strip()
        if not topic and not text:
            return ""
        if not text:
            return topic
        if not topic:
            return text
        return f"{topic} {text}"

    @staticmethod
    def _coerce_analysis(response: Any) -> dict:
        if isinstance(response, dict):
            return response
        text = str(response)
        return {"main_claim": text, "supporting_points": [], "assumptions": [], "weakest_point": text}

    @staticmethod
    def _coerce_fallacies(response: Any) -> dict:
        if isinstance(response, dict):
            return response
        return {"fallacies_found": [], "fallacy_descriptions": [str(response)]}

    @staticmethod
    def _feedback_block(judge_feedback: str) -> str:
        if not judge_feedback:
            return ""
        return (
            f"\n\nJUDGE'S FEEDBACK (MANDATORY): {judge_feedback}\n"
            "You MUST directly adapt your argument to address this feedback. "
            "If the Judge asked for specific data, statistics, or citations, you MUST provide them NOW."
        )

    @staticmethod
    def _mandate_block(judge_feedback: str) -> str:
        if not judge_feedback:
            return ""
        return f"\nJUDGE'S MANDATE: {judge_feedback}  Ensure the final argument honors this."
