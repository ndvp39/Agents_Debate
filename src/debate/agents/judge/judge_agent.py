"""JudgeAgent — moderates the debate, scores arguments, declares the verdict."""

import contextlib
import json
import logging
import os
import tempfile
from collections.abc import Callable
from dataclasses import asdict
from pathlib import Path

from debate.agents.base_agent import BaseAgent
from debate.agents.judge.verdict import DeclareVerdict, PersuasionScore
from debate.ipc.schemas import ArgumentMessage, RoutingMessage
from debate.shared.constants import AgentID
from debate.skills.loader import SkillLoader

_log = logging.getLogger("debate.judge")


class JudgeAgent(BaseAgent):
    """Runs inside the Judge subprocess.

    Drives the judge skill pipeline (enforce, evaluate, generate-feedback,
    compose-next-turn) through a project-local SkillLoader, then declares the
    verdict at the end of the debate.

    Optional checkpointing: when `checkpoint_path` is provided, the judge
    persists its accumulated state (scores, last arguments, last feedback,
    round counter) atomically after every successful scoring turn. A fresh
    judge process started with the same path reloads that state — so a
    watchdog-triggered restart resumes with full score history rather than
    silently producing a verdict computed from only the post-restart rounds.
    """

    def __init__(
        self,
        evaluate_llm: Callable,
        route_llm: Callable,
        verdict_llm: Callable | None = None,
        stdin=None,
        stdout=None,
        skills: SkillLoader | None = None,
        checkpoint_path: Path | None = None,
    ) -> None:
        super().__init__(AgentID.JUDGE, stdin, stdout, skills=skills)
        self._evaluate_llm = evaluate_llm
        self._route_llm = route_llm
        self._verdict_llm = verdict_llm
        self._verdict = DeclareVerdict()
        self._checkpoint_path: Path | None = (
            Path(checkpoint_path) if checkpoint_path else None
        )

        self._scores: dict[str, list[PersuasionScore]] = {
            AgentID.PRO: [],
            AgentID.CON: [],
        }
        self._last_arguments: dict[str, str] = {}
        self._last_feedback_sent: dict[str, str] = {AgentID.PRO: "", AgentID.CON: ""}
        self._round: int = 0

        self._load_checkpoint()

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
        # Round number for the NEXT speaker: same round when Pro just spoke (Con
        # answers in the same round); +1 when Con just spoke (Pro opens next round).
        next_round_number = msg.round if msg.agent_id == AgentID.PRO else msg.round + 1
        routing = self._build_routing(
            score, next_agent,
            previous_argument=msg.argument,
            round_number=next_round_number,
        )
        self._last_feedback_sent[next_agent] = routing.judge_feedback
        self._save_checkpoint()
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
        round_number: int,
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
            round_number=round_number,
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

    # ------------------------------------------------------------------
    # Checkpointing — persists accumulated state across process restarts
    # ------------------------------------------------------------------

    def _save_checkpoint(self) -> None:
        if self._checkpoint_path is None:
            return
        payload = {
            "round": self._round,
            "scores": {
                agent: [asdict(s) for s in scores]
                for agent, scores in self._scores.items()
            },
            "last_arguments": self._last_arguments,
            "last_feedback_sent": self._last_feedback_sent,
        }
        path = self._checkpoint_path
        path.parent.mkdir(parents=True, exist_ok=True)
        # Atomic write: temp-in-same-dir then rename, so a crash mid-write never
        # leaves a half-written checkpoint that would fail to reload.
        tmp_fd, tmp_name = tempfile.mkstemp(
            prefix=path.name + ".", suffix=".tmp", dir=str(path.parent),
        )
        try:
            with os.fdopen(tmp_fd, "w", encoding="utf-8") as fh:
                json.dump(payload, fh)
            os.replace(tmp_name, path)
        except Exception:
            with contextlib.suppress(OSError):
                os.unlink(tmp_name)
            raise

    def _load_checkpoint(self) -> None:
        if self._checkpoint_path is None or not self._checkpoint_path.is_file():
            return
        try:
            raw = self._checkpoint_path.read_text(encoding="utf-8").strip()
        except OSError as exc:
            _log.warning("judge: checkpoint load failed (%s) — starting fresh", exc)
            return
        # The SDK pre-allocates the checkpoint file as an empty placeholder before
        # the judge subprocess starts; treat empty/whitespace-only content as
        # "no checkpoint yet" rather than a parse failure.
        if not raw:
            return
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as exc:
            _log.warning("judge: checkpoint load failed (%s) — starting fresh", exc)
            return
        self._round = int(payload.get("round", 0))
        self._last_arguments = dict(payload.get("last_arguments", {}))
        self._last_feedback_sent = {
            AgentID.PRO: "", AgentID.CON: "",
            **dict(payload.get("last_feedback_sent", {})),
        }
        self._scores = {AgentID.PRO: [], AgentID.CON: []}
        for agent, score_dicts in (payload.get("scores", {}) or {}).items():
            self._scores[agent] = [
                PersuasionScore(**sd) for sd in score_dicts
            ]
        _log.info(
            "judge: checkpoint loaded round=%d pro_scores=%d con_scores=%d",
            self._round, len(self._scores[AgentID.PRO]), len(self._scores[AgentID.CON]),
        )

    @staticmethod
    def _reminder_block(next_agent: str, previous_feedback: str) -> str:
        if not previous_feedback:
            return ""
        return (
            f"REMINDER — The Judge previously instructed you: '{previous_feedback}'. "
            "You MUST address this directive explicitly. Failure to comply will result in a score penalty."
        )
