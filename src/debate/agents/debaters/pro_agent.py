"""ProAgent — debater arguing completely FOR the topic."""

from typing import Any, Callable

from debate.agents.debaters.base_debater import BaseDebater
from debate.shared.constants import AgentID, Stance


class ProAgent(BaseDebater):
    """Argues completely FOR the debate topic. No logic beyond stance assignment."""

    STANCE = Stance.PRO

    def __init__(
        self,
        topic: str,
        llm_call: Callable,
        search_call: Callable,
        stdin: Any = None,
        stdout: Any = None,
    ) -> None:
        super().__init__(AgentID.PRO, topic, llm_call, search_call, stdin, stdout)
