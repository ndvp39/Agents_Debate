# AI Agent Debate Orchestration System
**Version:** 1.00 | **Course:** AI Agents MSC — Exercise 02

A fully autonomous debate system orchestrated by three AI agents running as
separate subprocesses. Two debating agents (Pro and Con) argue opposing sides
of any topic while a Judge agent moderates, scores each argument in real time,
and declares a definitive winner with justification.

---

## Quick Start (for the Lecturer)

### 1 — Prerequisites

| Requirement | Version | Notes |
|---|---|---|
| Python | 3.10+ | [python.org](https://python.org) |
| `uv` package manager | any | `pip install uv` or [docs.astral.sh/uv](https://docs.astral.sh/uv/) |
| Google Gemini API key | — | Free — see step 3 |

### 2 — Clone and install

```bash
git clone https://github.com/ndvp39/Agents_Debate.git
cd Agents_Debate
uv sync
```

### 3 — Get a free Gemini API key

1. Go to **https://aistudio.google.com/app/apikey**
2. Sign in with a Google account and click **Create API key**
3. Copy the key (starts with `AIza...`)

### 4 — Create the `.env` file

```bash
cp .env-example .env
```

Then open `.env` and paste your key:

```dotenv
LLM_PROVIDER=gemini
GEMINI_API_KEY=AIza...your_key_here...
ANTHROPIC_API_KEY=
```

### 5 — Run a debate

```bash
uv run python src/main.py
```

You will be prompted for a topic and number of rounds (press Enter for the
default of 10; minimum 2 so both debaters get at least one turn). Each agent
runs in its own subprocess and communicates with the orchestrator over
JSON-lines stdin/stdout pipes. Expect 15–60 seconds per round depending on
API latency.

---

## LLM Provider

The system supports **Google Gemini** (default) and **Anthropic Claude**
interchangeably. The active provider is controlled by the `LLM_PROVIDER`
environment variable in `.env`.

| Provider | Key variable | Free tier |
|---|---|---|
| Google Gemini | `GEMINI_API_KEY` | Yes — [aistudio.google.com](https://aistudio.google.com/app/apikey) |
| Anthropic Claude | `ANTHROPIC_API_KEY` | No — [console.anthropic.com](https://console.anthropic.com) |

To switch to Anthropic, edit `.env`:

```dotenv
LLM_PROVIDER=anthropic
ANTHROPIC_API_KEY=sk-ant-...your_key_here...
```

Models and per-provider settings (temperature, max tokens) are in
`config/setup.json` under the `"provider"` key.

---

## Running Tests & Linter

```bash
# Full test suite with coverage report
uv run pytest tests/

# Lint check (zero violations required)
uv run ruff check src/
```

**Current quality gate:** 233 tests · 94%+ coverage · 0 ruff violations.

---

## Architecture

```
User (CLI)
  └─▶ main.py
        └─▶ DebateSDK
              └─▶ DebateOrchestrator  (Mediator pattern)
                    ├─▶ ProAgent subprocess   ──┐
                    ├─▶ ConAgent subprocess   ──┤── JSON-lines over stdin/stdout
                    └─▶ JudgeAgent subprocess ──┘
```

See [`docs/PLAN.md`](docs/PLAN.md) for full C4 diagrams, UML sequence diagrams,
and Architecture Decision Records.

### Agent pipeline per turn

| Agent | Skills per turn |
|---|---|
| Pro / Con | CraftOpening → AnalyzeOpponent → DetectFallacies → AdaptStrategy → BuildCounterArgument → SynthesizeEvidence → ApplyRhetoric |
| Judge | EnforceDebateMechanics → EvaluatePersuasionScore → RouteTurn (or DeclareVerdict) |

### Key design patterns

- **Mediator** — Orchestrator owns all routing; agents never talk directly
- **Dependency injection** — All LLM calls injected; fully mockable in tests
- **IPC via JSON-lines** — Schema-validated messages over subprocess pipes
- **Anti-sycophancy directive** — System prompt prevents debaters from agreeing

---

## Project Structure

```
src/
  main.py                     # CLI entry point
  pro_runner.py               # Subprocess entry point — Pro debater
  con_runner.py               # Subprocess entry point — Con debater
  judge_runner.py             # Subprocess entry point — Judge
  debate/
    sdk/          factory.py  sdk.py          # Public API
    services/     orchestrator.py             # Mediator / debate loop
    agents/       base_agent.py  watchdog.py
      debaters/   base_debater.py  skills.py  pro_agent.py  con_agent.py
      judge/      judge_agent.py  skills.py
    ipc/          channel.py  schemas.py      # JSON-lines IPC
    shared/       config.py  constants.py  llm_provider.py  gatekeeper.py
config/
  setup.json          # Debate params, provider config, model names
  rate_limits.json    # API rate limiting
  logging_config.json # Log rotation
docs/
  PLAN.md  PRD.md  TODO.md  PRD_*.md
tests/
  unit/        # 233 unit tests
  integration/ # Full in-process debate with mocked LLMs
```

---

## Example Debate Output

Live run on topic **"AI will replace human jobs"** (2 rounds, Gemini 2.5 Flash):

```
============================================================
  DEBATE COMPLETE
============================================================
  Winner : Agent_Con
  Scores : Agent_Pro = 36  |  Agent_Con = 48

  Justification:
  Agent_Con demonstrated superior persuasion across 1 round(s).
  Logic 0.36 vs 0.48; rhetoric and citation quality consistently
  favoured Agent_Con.

  Messages in transcript : 5
============================================================
```

---

## License & Credits

MSC Exercise 02 — Dr. Yoram Segal.
Built with [Claude Code](https://claude.ai/claude-code) and the
[Anthropic API](https://docs.anthropic.com).
