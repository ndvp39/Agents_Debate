"""Deterministic debate-mechanics gate: returns a ReprimandMessage or None."""

from debate.ipc.schemas import ArgumentMessage, ReprimandMessage

_AGREEMENT_PHRASES = (
    "i agree", "you make a good point", "that's correct",
    "you're right", "well said", "i concede", "you are correct",
)


def run(
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
