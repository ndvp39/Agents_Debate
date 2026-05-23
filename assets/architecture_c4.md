# C4 Architecture Diagrams

**Author:** Nadav Goldin — MSC AI Agents Exercise 02
**Date:** 2026-05-23

This document contains two C4-level diagrams for the multi-agent debate system: a Context diagram
showing the system's external relationships, and a Container diagram showing the major deployable
units and how they communicate.

---

## C4 Level 1 — System Context

Shows the debate system as a black box and identifies the external actors and APIs it interacts with.

```mermaid
flowchart TB
    User(["👤 User\n(CLI operator)"])

    subgraph DebateSystem["Debate System"]
        DS["Multi-Agent Debate System\n──────────────────\nOrchestrates a structured debate\nbetween Pro and Con agents,\njudged by a neutral Judge agent"]
    end

    GeminiAPI(["☁️ Google Gemini API\n(LLM provider)"])
    AnthropicAPI(["☁️ Anthropic Claude API\n(LLM provider)"])
    TavilyAPI(["🔍 Tavily Search API\n(Web search provider)"])

    User -- "debate topic, rounds,\nmodel config (CLI args)" --> DS
    DS -- "transcript, verdict,\ncost summary" --> User

    DS -- "LLM inference\n(debater & judge prompts)" --> GeminiAPI
    DS -- "LLM inference\n(debater & judge prompts)" --> AnthropicAPI
    DS -- "web search queries\n(debater research)" --> TavilyAPI
```

---

## C4 Level 2 — Container Diagram

Shows the internal containers (processes and major shared components) and their interactions.

```mermaid
flowchart LR
    User(["👤 User"])

    subgraph MainProcess["Main Process (Python)"]
        CLI["CLI / main.py\n──────────\nArgparse entry point;\nparses topic, rounds,\nmodel flags"]
        SDK["DebateSDK\nsdk/sdk.py\n──────────────\nPublic API facade;\nstarts debate,\nexposes transcript,\nverdict, cost summary"]
        Factory["subprocess_factory\nsdk/factory.py\n──────────────\nSpawns the three\nagent subprocesses\nvia Popen"]
        Orchestrator["DebateOrchestrator\nservices/orchestrator.py\n──────────────────────\nMediator pattern;\nroutes IPC messages\nbetween agents;\nowns debate-round loop"]
        IPC["IPCChannel\nipc/channel.py\n──────────────\nJSON-lines over\nstdin/stdout pipes"]
        Watchdog["Watchdog\nagents/watchdog.py\n──────────────────\nMonitors subprocesses;\nrestarts hung agents"]
        Gatekeeper["ApiGatekeeper\nshared/gatekeeper.py\n──────────────────\nFIFO rate-limit queue\nfor all LLM calls"]
        LLMProvider["LLMProvider\nshared/llm_provider.py\n──────────────────\nGemini + Anthropic\nadapter; tracks cost"]
        Logger["DebateLogger\nshared/logger.py\n──────────────\nFIFO rotating log"]
    end

    subgraph ProProcess["Subprocess — Pro"]
        ProAgent["ProAgent\nagents/debaters/pro_agent.py\n────────────────────────────\nSTANCE = FOR;\n7-skill pipeline:\nAnalyze→Counter→Rhetoric"]
        WebSearchPro["WebSearchTool\n(Tavily)"]
    end

    subgraph ConProcess["Subprocess — Con"]
        ConAgent["ConAgent\nagents/debaters/con_agent.py\n────────────────────────────\nSTANCE = AGAINST;\n7-skill pipeline:\nAnalyze→Counter→Rhetoric"]
        WebSearchCon["WebSearchTool\n(Tavily)"]
    end

    subgraph JudgeProcess["Subprocess — Judge"]
        JudgeAgent["JudgeAgent\nagents/judge/judge_agent.py\n──────────────────────────\nEvaluates arguments;\naccumulates scores;\ndeclares verdict"]
    end

    GeminiAPI(["☁️ Google Gemini API"])
    AnthropicAPI(["☁️ Anthropic Claude API"])
    TavilyAPI(["🔍 Tavily Search API"])

    User --> CLI
    CLI --> SDK
    SDK --> Factory
    SDK --> Orchestrator
    Factory -- "spawns" --> ProProcess
    Factory -- "spawns" --> ConProcess
    Factory -- "spawns" --> JudgeProcess
    Orchestrator -- "uses" --> IPC
    Orchestrator -- "uses" --> Watchdog
    IPC -- "stdin/stdout pipes" --> ProProcess
    IPC -- "stdin/stdout pipes" --> ConProcess
    IPC -- "stdin/stdout pipes" --> JudgeProcess
    ProAgent -- "LLM calls" --> Gatekeeper
    ConAgent -- "LLM calls" --> Gatekeeper
    JudgeAgent -- "LLM calls" --> Gatekeeper
    ProAgent --> WebSearchPro
    ConAgent --> WebSearchCon
    Gatekeeper --> LLMProvider
    Orchestrator --> Logger
    LLMProvider --> GeminiAPI
    LLMProvider --> AnthropicAPI
    WebSearchPro --> TavilyAPI
    WebSearchCon --> TavilyAPI
```
