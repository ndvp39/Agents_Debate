# OOP Class Hierarchy & Relationships

**Author:** Nadav Goldin — MSC AI Agents Exercise 02
**Date:** 2026-05-23

This diagram shows the full object-oriented class hierarchy of the debate system, including
inheritance chains, composition relationships, and dependency links between components.
`BaseAgent` sits at the root of the agent hierarchy; `BaseDebater` specialises it for
argumentation, and `ProAgent` / `ConAgent` concretise the stance. `JudgeAgent` inherits
directly from `BaseAgent`. Orchestration and SDK layers are shown as separate top-level classes
with their dependency arrows.

```mermaid
classDiagram
    class BaseAgent {
        +str agent_id
        +SkillLoader _skills
        +IO _stdin
        +IO _stdout
        +send(message) None
        +receive() Message
    }

    class SkillLoader {
        +Path _root
        +dict _cache
        +load(name) Skill
    }
    class Skill {
        +str name
        +str type
        +render(**kwargs) str
        +run(*args) Any
    }

    class BaseDebater {
        +str STANCE
        +str _topic
        +callable _llm_call
        +int _round
        +str _last_opponent_arg
        +WebSearchTool _web_search
        +respond(opponent_arg) ArgumentMessage
        +_run_pipeline(context) str
        +_wrapped_llm(prompt) str
    }

    class ProAgent {
        +str STANCE = "completely FOR"
    }

    class ConAgent {
        +str STANCE = "completely AGAINST"
    }

    class JudgeAgent {
        +dict _scores
        +str _last_feedback_sent
        +process_argument(arg_msg) RoutingMessage
        +declare_verdict(transcript) VerdictMessage
    }

    class WebSearchTool {
        +str _api_key
        +search(query) list[str]
    }

    class Watchdog {
        +float _timeout
        +dict _agents
        +register(process, name, restart_fn) None
        +start_timer(name) None
        +reset_timer(name) None
        +current_process(name) Popen
        +wait_for_restart(name, timeout) bool
        +notify_external_restart(name, new_proc) None
        +stop() None
    }

    class Spawners {
        +Callable spawn_pro
        +Callable spawn_con
        +Callable spawn_judge
    }

    class DebateOrchestrator {
        +IPCChannel _channel
        +Watchdog _watchdog
        +int _rounds
        +run(topic) VerdictMessage
    }

    class DebateSDK {
        +start_debate(topic, rounds, cfg) None
        +get_transcript() list[dict]
        +get_verdict() VerdictMessage
        +get_cost_summary() dict
    }

    class IPCChannel {
        +IO _stdin
        +IO _stdout
        +send(message) None
        +receive() Message
    }

    class ApiGatekeeper {
        +int _rpm
        +int _rph
        +deque _queue
        +CostAccumulator _cost
        +Path _cost_dump_path
        +execute(api_call) Any
        +record_tokens(in, out) None
        +get_cost_summary() dict
    }

    class CostAggregator {
        +aggregate_costs(setup, pro_path, con_path, judge_path) dict
    }

    class LLMProvider {
        +str _provider
        +str _model
        +float _total_cost
        +complete(prompt) str
        +get_cost() float
    }

    class DebateLogger {
        +int _max_size
        +Queue _buffer
        +log(level, message) None
        +flush() None
    }

    %% Inheritance
    BaseAgent <|-- BaseDebater : extends
    BaseDebater <|-- ProAgent : extends
    BaseDebater <|-- ConAgent : extends
    BaseAgent <|-- JudgeAgent : extends

    %% Composition
    DebateSDK *-- Watchdog : owns
    DebateSDK *-- Spawners : builds via factory
    DebateOrchestrator *-- IPCChannel : owns
    BaseAgent *-- SkillLoader : injected
    SkillLoader o-- Skill : caches

    %% Dependencies / usage
    BaseDebater ..> WebSearchTool : uses
    BaseDebater ..> SkillLoader : loads skills
    JudgeAgent ..> SkillLoader : loads skills
    BaseDebater ..> ApiGatekeeper : calls go through
    JudgeAgent ..> ApiGatekeeper : calls go through
    WebSearchTool ..> ApiGatekeeper : Tavily go through
    ApiGatekeeper ..> LLMProvider : delegates to
    DebateSDK ..> DebateOrchestrator : creates & drives
    DebateSDK ..> CostAggregator : aggregates at end
    DebateOrchestrator ..> Watchdog : arms/resets timers
    DebateOrchestrator ..> DebateLogger : logs via
```
