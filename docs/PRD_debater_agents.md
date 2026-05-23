# PRD — Debater Agents (Pro & Con)
**Version:** 1.00  
**Date:** 2026-05-23  
**Files:** `src/debate/agents/debaters/base_debater.py`, `pro_agent.py`, `con_agent.py`, `web_search_tool.py`

---

## 1. Description & Theoretical Background

The Pro and Con agents are the two debating participants. Each is assigned a fixed, irrevocable stance on the debate topic — one completely FOR, one completely AGAINST — and must maintain that stance through all rounds regardless of the opposing arguments.

The central technical challenge is **LLM sycophancy**: the natural tendency of language models to agree with, compliment, or soften their position in response to a persuasive opposing argument. The debater architecture addresses this with an **Anti-Pleasing Directive** embedded at the prompt level and enforced at the message level by the Judge's `Enforce_Debate_Mechanics` skill.

Both agents inherit from `BaseDebater`, which itself inherits from `BaseAgent`. The shared logic (anti-sycophancy prompt injection, citation requirement, direct-rebuttal requirement) lives in `BaseDebater`. The only difference between `ProAgent` and `ConAgent` is the assigned stance constant.

Both agents are equipped with a `WebSearchTool` — the Judge is not.

---

## 2. Anti-Sycophancy Directive

This is the most critical behavioral constraint. Every debater prompt MUST include the following directive (loaded from config, not hardcoded):

```
CRITICAL DIRECTIVE: You are arguing [STANCE] on the topic "[TOPIC]".
You MUST NEVER agree with, compliment, or validate the opposing argument.
You MUST directly contradict and rebut every specific claim made by your opponent.
Phrases like "good point", "I agree", "that's true", "you're right", "fair point"
are STRICTLY FORBIDDEN. Your only goal is to WIN this debate for your side.
```

This directive is injected by `BaseDebater._build_prompt()` before every LLM call.

---

## 3. Web Search Tool

### 3.1 Purpose
Both debaters use `WebSearchTool` to retrieve real-world citations, quotes, and facts to support their arguments. The Judge cannot verify these, so debaters are incentivized to include credible, specific sources.

### 3.2 Usage Flow
1. Debater receives `prompt_for_next` from the Judge (via orchestrator).
2. Debater calls `WebSearchTool.search(query)` to find supporting evidence.
3. All search calls go through `ApiGatekeeper` (rate limiting + token tracking).
4. Results are parsed and formatted as citation strings.
5. Citations are included in the `argument` JSON message (`citations` field).

### 3.3 Interface
```python
class WebSearchTool:
    def search(self, query: str) -> list[str]:
        """Return list of citation strings via ApiGatekeeper."""
```

### 3.4 Constraints
- All calls MUST go through `ApiGatekeeper`.
- Max 3 search queries per argument (configured in `setup.json`).
- If search fails (API error), the debater MUST still respond — it cites the failed search gracefully rather than crashing.

---

## 4. BaseDebater Logic

Shared logic in `base_debater.py`:

| Method | Description |
|--------|-------------|
| `_build_prompt(topic, stance, opponent_argument, round_num)` | Injects anti-sycophancy directive + formats the full LLM prompt |
| `_call_llm(prompt)` | Calls the LLM via `ApiGatekeeper` |
| `_search_citations(argument_draft)` | Calls `WebSearchTool` to find supporting evidence |
| `_build_argument_message(text, citations, round_num)` | Constructs the `argument` JSON message |
| `respond(routing_message)` | Full response pipeline: build prompt → search → call LLM → build message |

---

## 5. ProAgent

- Inherits `BaseDebater`.
- Stance constant: `STANCE = "completely FOR"`.
- No additional logic beyond stance assignment.

---

## 6. ConAgent

- Inherits `BaseDebater`.
- Stance constant: `STANCE = "completely AGAINST"`.
- No additional logic beyond stance assignment.

---

## 7. Input / Output

### Input (per turn)
| Field | Source | Description |
|-------|--------|-------------|
| `routing_message` | Judge via Orchestrator | Contains `prompt_for_next` and `judge_feedback` |
| `previous_opponent_argument` | Stored in state | The opponent's last argument (for direct rebuttal) |

### Output (per turn)
| Field | Type | Description |
|-------|------|-------------|
| `argument` JSON | dict | Full `argument` message with text + citations + round number |

---

## 8. Performance Requirements

| Metric | Target |
|--------|--------|
| Time to produce one argument (LLM + web search) | < 60 seconds |
| Citations per argument | ≥ 1, ≤ 5 |
| Memory per debater process | < 200MB |

---

## 9. Constraints

- Debaters MUST NOT communicate directly with each other — only through the Judge/Orchestrator.
- Anti-sycophancy directive MUST be injected on every single LLM call — never omitted.
- All LLM calls and web-search calls MUST go through `ApiGatekeeper`.
- Skills (including `WebSearchTool`) MUST be defined locally within the project.
- `citations` list in the output message MUST contain at least 1 entry; if web search fails, the debater must note the attempted search.
- `ProAgent` and `ConAgent` MUST NOT duplicate any logic — all shared code lives in `BaseDebater`.

---

## 10. Alternatives Considered

| Alternative | Reason Rejected |
|-------------|----------------|
| Single debater class with a `stance` parameter | Harder to test each stance in isolation; less explicit OOP design |
| Giving the Judge web search access | Requirement explicitly forbids it |
| Allowing debaters to skip citations | Violates requirement; Judge would reprimand every turn |
| Hard-coding the anti-sycophancy prompt | No hardcoded values allowed; prompt must come from config |

---

## 11. Success Criteria

- [ ] `ProAgent` never produces an argument containing agreement phrases.
- [ ] `ConAgent` never produces an argument containing agreement phrases.
- [ ] Every argument message contains at least 1 citation.
- [ ] All LLM and web-search calls pass through the Gatekeeper (verifiable via Gatekeeper logs).
- [ ] If web search fails, the debater still returns a valid `argument` message.
- [ ] `ProAgent` and `ConAgent` share zero duplicated logic (all in `BaseDebater`).

---

## 12. Test Scenarios

| Scenario | Expected Outcome |
|----------|-----------------|
| Pro receives a routing message | Returns valid `argument` JSON with FOR stance |
| Con receives a routing message | Returns valid `argument` JSON with AGAINST stance |
| Anti-sycophancy prompt is removed from config | `ValueError` raised at prompt build time |
| Web search API returns empty results | Argument still returned with a note about unavailable sources |
| Web search API raises exception | Argument returned without crash; exception logged |
| LLM call rate limit hit | Gatekeeper queues the call; argument returned after drain |
