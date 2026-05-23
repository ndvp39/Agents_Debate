# UML Sequence Diagram — One Debate Round

**Author:** Nadav Goldin — MSC AI Agents Exercise 02
**Date:** 2026-05-23

This diagram traces the message flow through one complete debate round and the final verdict phase.
Each agent subprocess communicates with the Orchestrator exclusively through `IPCChannel`
(JSON-lines over stdin/stdout pipes). All LLM calls are serialised through `ApiGatekeeper`
to enforce the rate-limit FIFO queue before being forwarded to `LLMProvider`.

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
        Note over ProAgent,LLMProvider: Pro 7-skill pipeline
        ProAgent->>ApiGatekeeper: call(AnalyzeOpponentSkill, opponent_arg)
        ApiGatekeeper->>LLMProvider: enqueue → forward(prompt)
        LLMProvider-->>ApiGatekeeper: analysis_result
        ApiGatekeeper-->>ProAgent: analysis_result

        ProAgent->>ApiGatekeeper: call(BuildCounterArgumentSkill, analysis)
        ApiGatekeeper->>LLMProvider: enqueue → forward(prompt)
        LLMProvider-->>ApiGatekeeper: counter_argument
        ApiGatekeeper-->>ProAgent: counter_argument

        ProAgent->>ApiGatekeeper: call(ApplyRhetoricSkill, counter_argument)
        ApiGatekeeper->>LLMProvider: enqueue → forward(prompt)
        LLMProvider-->>ApiGatekeeper: polished_argument
        ApiGatekeeper-->>ProAgent: polished_argument
    end

    ProAgent-->>Orchestrator: ArgumentMessage {stance: "FOR", content: polished_argument}

    Note over Orchestrator,JudgeAgent: Judge evaluates Pro's argument
    Orchestrator->>JudgeAgent: ArgumentMessage {from: "pro", content}

    rect rgb(220, 255, 230)
        Note over JudgeAgent,LLMProvider: Judge evaluation pipeline
        JudgeAgent->>ApiGatekeeper: call(EvaluateArgumentSkill, argument)
        ApiGatekeeper->>LLMProvider: enqueue → forward(prompt)
        LLMProvider-->>ApiGatekeeper: score + feedback
        ApiGatekeeper-->>JudgeAgent: score + feedback

        JudgeAgent->>ApiGatekeeper: call(RouteNextSpeakerSkill, context)
        ApiGatekeeper->>LLMProvider: enqueue → forward(prompt)
        LLMProvider-->>ApiGatekeeper: routing_decision
        ApiGatekeeper-->>JudgeAgent: routing_decision
    end

    JudgeAgent-->>Orchestrator: RoutingMessage {next: "con", feedback}
    Orchestrator->>ConAgent: RoutingMessage {turn: "con", judge_feedback}

    rect rgb(255, 235, 220)
        Note over ConAgent,LLMProvider: Con 7-skill pipeline
        ConAgent->>ApiGatekeeper: call(AnalyzeOpponentSkill, pro_argument)
        ApiGatekeeper->>LLMProvider: enqueue → forward(prompt)
        LLMProvider-->>ApiGatekeeper: analysis_result
        ApiGatekeeper-->>ConAgent: analysis_result

        ConAgent->>ApiGatekeeper: call(BuildCounterArgumentSkill, analysis)
        ApiGatekeeper->>LLMProvider: enqueue → forward(prompt)
        LLMProvider-->>ApiGatekeeper: counter_argument
        ApiGatekeeper-->>ConAgent: counter_argument

        ConAgent->>ApiGatekeeper: call(ApplyRhetoricSkill, counter_argument)
        ApiGatekeeper->>LLMProvider: enqueue → forward(prompt)
        LLMProvider-->>ApiGatekeeper: polished_argument
        ApiGatekeeper-->>ConAgent: polished_argument
    end

    ConAgent-->>Orchestrator: ArgumentMessage {stance: "AGAINST", content: polished_argument}

    Note over Orchestrator: round_counter += 1
    Orchestrator->>JudgeAgent: ArgumentMessage {from: "con", content}

    rect rgb(220, 255, 230)
        JudgeAgent->>ApiGatekeeper: call(EvaluateArgumentSkill, argument)
        ApiGatekeeper->>LLMProvider: enqueue → forward(prompt)
        LLMProvider-->>ApiGatekeeper: score + feedback
        ApiGatekeeper-->>JudgeAgent: score + feedback
    end

    JudgeAgent-->>Orchestrator: RoutingMessage {next: "pro", feedback}

    Note over Orchestrator,JudgeAgent: All rounds complete — verdict phase
    Orchestrator->>JudgeAgent: VerdictRequestMessage {transcript}

    rect rgb(255, 255, 210)
        Note over JudgeAgent,LLMProvider: Verdict pipeline
        JudgeAgent->>ApiGatekeeper: call(DeclareVerdictSkill, scores, transcript)
        ApiGatekeeper->>LLMProvider: enqueue → forward(prompt)
        LLMProvider-->>ApiGatekeeper: verdict + rationale
        ApiGatekeeper-->>JudgeAgent: verdict + rationale
    end

    JudgeAgent-->>Orchestrator: VerdictMessage {winner, rationale, scores}
    Orchestrator-->>User: transcript + verdict + cost_summary
```
