# UML Sequence Diagram — One Debate Round

**Author:** Nadav Goldin — MSC AI Agents Exercise 02
**Date:** 2026-05-23

This diagram traces the message flow through one complete debate round and the final verdict phase.
Each agent subprocess communicates with the Orchestrator exclusively through `IPCChannel`
(JSON-lines over stdin/stdout pipes). All LLM and Tavily calls are routed through `ApiGatekeeper.execute()`
which enforces the rate-limit FIFO queue and records cost before forwarding to the provider client.

> The "skill" steps shown below (analyze_opponent, build_counter_argument, evaluate_persuasion_score,
> generate_judge_feedback, etc.) are SKILL.md files loaded at runtime by `SkillLoader` — they are
> templates the agent renders with `{{ var }}` placeholders and then passes to the LLM closure.
> Deterministic skills (`adapt_strategy`, `synthesize_evidence`, `compose_next_turn_prompt`,
> `enforce_debate_mechanics`) execute in-process without an LLM call.
>
> RoutingMessage from Judge to next debater carries `previous_argument` (the just-evaluated
> argument) and `round_number` (the round the next speaker should use) — so a watchdog-respawned
> debater resumes with the real opponent text on the correct round.
>
> Not depicted for clarity: the Watchdog arms a `start_timer` around every `receive()` call;
> on hang, it kills + respawns the subprocess via the registered `restart_fn` closure and the
> orchestrator transparently re-sends the in-flight message (see `PRD_debate_orchestrator §6.2`).

```mermaid
sequenceDiagram
    autonumber
    participant User
    participant Orchestrator
    participant ProAgent
    participant JudgeAgent
    participant ConAgent
    participant ApiGatekeeper
    participant LLMProvider

    Note over User,Orchestrator: Debate initialisation
    User->>Orchestrator: start_debate(topic, rounds, model_cfg)
    Orchestrator->>ProAgent: RoutingMessage {role: "pro", topic, round_n}
    Orchestrator->>ConAgent: RoutingMessage {role: "con", topic, round_n}
    Orchestrator->>JudgeAgent: RoutingMessage {role: "judge", topic, round_n}

    Note over Orchestrator,ProAgent: Round N — Pro speaks first
    Orchestrator->>ProAgent: RoutingMessage {turn: "pro"}

    rect rgb(220, 235, 255)
        Note over ProAgent,LLMProvider: Pro pipeline (analyze→detect→adapt→build→synth→rhetoric)
        ProAgent->>ApiGatekeeper: execute(analyze_opponent rendered prompt)
        ApiGatekeeper->>LLMProvider: rate-limit gate → forward(prompt)
        LLMProvider-->>ApiGatekeeper: analysis_result (+ response.usage)
        ApiGatekeeper-->>ProAgent: analysis_result

        ProAgent->>ApiGatekeeper: execute(build_counter_argument rendered prompt)
        ApiGatekeeper->>LLMProvider: rate-limit gate → forward(prompt)
        LLMProvider-->>ApiGatekeeper: counter_argument
        ApiGatekeeper-->>ProAgent: counter_argument

        ProAgent->>ApiGatekeeper: execute(apply_rhetoric rendered prompt)
        ApiGatekeeper->>LLMProvider: rate-limit gate → forward(prompt)
        LLMProvider-->>ApiGatekeeper: polished_argument
        ApiGatekeeper-->>ProAgent: polished_argument
    end

    ProAgent-->>Orchestrator: ArgumentMessage {stance: "FOR", content: polished_argument}

    Note over Orchestrator,JudgeAgent: Judge evaluates Pro's argument
    Orchestrator->>JudgeAgent: ArgumentMessage {from: "pro", content}

    rect rgb(220, 255, 230)
        Note over JudgeAgent,LLMProvider: Judge pipeline (enforce → evaluate → feedback → compose)
        JudgeAgent->>ApiGatekeeper: execute(evaluate_persuasion_score rendered prompt)
        ApiGatekeeper->>LLMProvider: rate-limit gate → forward(prompt)
        LLMProvider-->>ApiGatekeeper: PersuasionScore JSON
        ApiGatekeeper-->>JudgeAgent: score

        JudgeAgent->>ApiGatekeeper: execute(generate_judge_feedback rendered prompt)
        ApiGatekeeper->>LLMProvider: rate-limit gate → forward(prompt)
        LLMProvider-->>ApiGatekeeper: 2-3 sentences of feedback
        ApiGatekeeper-->>JudgeAgent: feedback

        Note over JudgeAgent: compose_next_turn_prompt (deterministic — no LLM)
        Note over JudgeAgent: persist checkpoint (atomic JSON write)
    end

    JudgeAgent-->>Orchestrator: RoutingMessage {target_agent: "con", judge_feedback, previous_argument, round_number}
    Orchestrator->>ConAgent: RoutingMessage {turn: "con", judge_feedback}

    rect rgb(255, 235, 220)
        Note over ConAgent,LLMProvider: Con pipeline (analyze on previous_argument, then full chain)
        ConAgent->>ApiGatekeeper: execute(analyze_opponent rendered prompt)
        ApiGatekeeper->>LLMProvider: rate-limit gate → forward(prompt)
        LLMProvider-->>ApiGatekeeper: analysis_result
        ApiGatekeeper-->>ConAgent: analysis_result

        ConAgent->>ApiGatekeeper: execute(build_counter_argument rendered prompt)
        ApiGatekeeper->>LLMProvider: rate-limit gate → forward(prompt)
        LLMProvider-->>ApiGatekeeper: counter_argument
        ApiGatekeeper-->>ConAgent: counter_argument

        ConAgent->>ApiGatekeeper: execute(apply_rhetoric rendered prompt)
        ApiGatekeeper->>LLMProvider: rate-limit gate → forward(prompt)
        LLMProvider-->>ApiGatekeeper: polished_argument
        ApiGatekeeper-->>ConAgent: polished_argument
    end

    ConAgent-->>Orchestrator: ArgumentMessage {stance: "AGAINST", content: polished_argument}

    Note over Orchestrator: round_counter += 1
    Orchestrator->>JudgeAgent: ArgumentMessage {from: "con", content}

    rect rgb(220, 255, 230)
        JudgeAgent->>ApiGatekeeper: execute(evaluate_persuasion_score rendered prompt)
        ApiGatekeeper->>LLMProvider: rate-limit gate → forward(prompt)
        LLMProvider-->>ApiGatekeeper: PersuasionScore JSON
        ApiGatekeeper-->>JudgeAgent: score
    end

    JudgeAgent-->>Orchestrator: RoutingMessage {next: "pro", feedback}

    Note over Orchestrator,JudgeAgent: All rounds complete — verdict phase
    Orchestrator->>JudgeAgent: VerdictRequestMessage {transcript}

    rect rgb(255, 255, 210)
        Note over JudgeAgent,LLMProvider: Verdict pipeline (DeclareVerdict — Python skill, not SKILL.md)
        JudgeAgent->>ApiGatekeeper: execute(verdict prompt built from score context)
        ApiGatekeeper->>LLMProvider: rate-limit gate → forward(prompt)
        LLMProvider-->>ApiGatekeeper: 4-section justification (KEY CLASHES / FEEDBACK / SCORING / FINAL)
        ApiGatekeeper-->>JudgeAgent: justification
    end

    JudgeAgent-->>Orchestrator: VerdictMessage {winner, rationale, scores}
    Orchestrator-->>User: transcript + verdict + cost_summary
```
