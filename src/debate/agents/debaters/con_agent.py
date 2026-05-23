"""ConAgent — debater arguing completely AGAINST the topic."""

from collections.abc import Callable
from typing import Any

from debate.agents.debaters.base_debater import BaseDebater
from debate.shared.constants import AgentID, Stance


class ConAgent(BaseDebater):
    """Argues completely AGAINST the debate topic. No logic beyond stance assignment."""

    STANCE = Stance.CON

    def __init__(
        self,
        topic: str,
        llm_call: Callable,
        search_call: Callable,
        stdin: Any = None,
        stdout: Any = None,
    ) -> None:
        super().__init__(AgentID.CON, topic, llm_call, search_call, stdin, stdout)
