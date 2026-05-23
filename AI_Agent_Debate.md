AI Agent Debate Orchestration (Exercise 02) - Complete Project Requirements & Specifications
Project Objective: Develop a Python-based system that orchestrates an autonomous debate between two AI agents (one "Pro" and one "Con") under the supervision and management of a third agent acting as the "Judge/Father." The system must run completely autonomously from the moment it is executed.

Debate Language: The entire debate, including all internal routing, reasoning, and outputs, must be conducted strictly in English.

1. Agent Architecture & Role Definitions
The system consists of 3 distinct agents (running as separate processes communicating via IPC):

Agent 1: The Judge ("The Father" & Moderator)
Persona: Objective, authoritative, strictly analytical, and neutral. Acts as the strict "Father" figure who demands intellectual rigor, respectful discourse, and fierce competition.

Role: Manages the flow of the debate, maintains order, grants speaking turns ("It is your turn now"), and ensures arguments are well-reasoned.

Internet Restriction: The Judge has NO internet access. It must form its evaluations and final judgment solely based on the arguments and citations provided by the debating agents.

Enforcement: Must reprimand the debaters if they begin to agree with each other (the goal is a debate!) or if they fail to provide reasoned counter-arguments.

Final Verdict (Critical): Must declare a definitive winner at the end. Ties are strictly forbidden. The decision must be based on persuasiveness and rhetorical skill, not objective factual truth. Must assign a score/percentage to each agent (e.g., 85% vs 72%) and provide a detailed justification for the verdict.

Judge's Required Skills:

Enforce_Debate_Mechanics: Evaluates the incoming message to ensure the debater directly addressed the opponent, provided citations, and did not "please" or agree with the opponent. If it fails, the Judge bounces the turn back with a reprimand.

Route_Turn: Manages the IPC flow. Summarizes the core point just made, defines the target for the next agent, and hands over control.

Evaluate_Persuasion_Score: An internal evaluation metric updated round-by-round assessing logical consistency and citation strength.

Declare_Verdict: Executed at the final round to output the winner, scores, and detailed justification.

Agents 2 & 3: The Debaters ("Pro" and "Con")
Role: Each agent is assigned a strict stance (one completely FOR the topic, one completely AGAINST). One presents arguments, and the other analyzes and provides counter-arguments.

Anti-Pleasing Directive: The main challenge is to prevent LLM sycophancy. They must be explicitly prompted to argue, contradict, and never agree with the opposing side.

Mutual Engagement: Every response must directly address the specific claims made by the opponent in the previous turn.

Tools: Both debaters must be equipped with a web-search tool to back up their claims with real-world citations, quotes, and facts.

2. Communication Flow & IPC Protocol
Routing via the Judge: The debaters never communicate directly. The flow is always: Debater A -> Judge -> Debater B -> Judge -> Debater A.

Debate Length: The debate must consist of 10 ping-pongs (argument and counter-argument) per side. (Note: If budget/token limits are a strict constraint, this can be reduced to 5 pings, but this must be explicitly stated in the README).

IPC Format (JSON): All inter-process communication must be structured in strict JSON to save tokens and allow the Python orchestrator to parse commands.

Expected JSON Schemas for the Judge:

Routing Turn: {"message_type": "routing", "target_agent": "Agent_B", "judge_feedback": "...", "prompt_for_next": "..."}

Reprimand: {"message_type": "reprimand", "target_agent": "Agent_A", "reprimand_issued": true, "prompt_for_next": "Rewrite and provide a counter-argument."}

Final Verdict: {"message_type": "verdict", "winner": "Agent_B", "scores": {"Agent_A": 75, "Agent_B": 88}, "justification": "..."}

3. Engineering & Technical Requirements (Strict Constraints)
Execution & Language: Pure Python implementation. Executing the main Python script must trigger the entire debate automatically from start to finish without hanging.

Object-Oriented Programming (OOP): Must use classes and inheritance. Do not duplicate code (DRY). Shared agent logic must reside in a base class.

Environment Management: Use uv for project and virtual environment management (must include a pyproject.toml).

Stability (Watchdog & Timeouts): The system must be resilient. Implement a Watchdog/Keep-alive timer for every process. If an agent hangs, the system must trigger a timeout, kill the process, and restart it automatically. No manual intervention allowed mid-run.

Gatekeeper: Must implement a token-tracking/economic protection layer to limit costs.

Skill Scope: Agent Skills must be defined locally within the project, not globally.

User Interface (CLI/SDK): The project must include an SDK layer allowing operation via a basic terminal menu (keyboard inputs).

Logging: Implement structured logging (e.g., a FIFO queue configured via a config file: up to 20 files, max 500 lines per file).

Code Quality:

Must use a Linter (e.g., Ruff).

Must write Unit Tests using TDD methodologies.

Secrets Management: No hardcoded variables or API keys. Use a .env file and provide a .env.example in the repository.

4. Required Deliverables
Source Code: Hosted on a GitHub repository (Public or shared with the lecturer), structured properly according to OOP and uv standards.

Architecture Diagram: A visual mapping of the OOP class inheritance and system architecture.

Comprehensive README.md: Must include:

Screenshots of the running system.

The exact prompts used for the agents.

A full transcript/dialogue of one complete debate session.

Explicit mention if the ping limit was reduced from 10 to 5 due to budget constraints.