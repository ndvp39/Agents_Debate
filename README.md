# AI Agent Debate Orchestration System
**Version:** 1.00 | **Course:** AI Agents MSC — Exercise 02

A fully autonomous debate system orchestrated by three AI agents.
Two debating agents (Pro and Con) argue opposing sides of a topic
while a Judge agent manages the debate, enforces rules, and declares
a definitive winner.

> **Debate rounds:** 10 ping-pongs per side.
> *(Reduced to 5 if budget constraints apply — see Configuration section.)*

---

## System Requirements

- Python 3.10+
- [`uv`](https://docs.astral.sh/uv/) package manager

---

## Installation

```bash
# 1. Clone the repository
git clone https://github.com/ndvp39/Agents_Debate.git
cd Agents_Debate

# 2. Copy environment variables file and fill in your API keys
cp .env-example .env

# 3. Install dependencies
uv sync
```

---

## Configuration

Edit `config/setup.json` to change debate settings (rounds, models, timeouts).
Edit `config/rate_limits.json` to adjust API rate limits.
Edit `config/logging_config.json` to configure log rotation.

All API keys go in `.env` — never in source code.

---

## Usage

```bash
# Run a real debate (spawns Pro, Con, and Judge subprocesses with live Claude API calls)
uv run python src/main.py

# Run tests (220 tests, ≥85% coverage)
uv run pytest tests/

# Run linter
uv run ruff check src/
```

> Each agent runs in its own subprocess communicating over JSON stdin/stdout pipes.
> The Judge scores arguments via the Claude API; debaters build 7-skill pipelines per turn.
> Expect each round to take 15–60 seconds depending on API latency.

---

## Architecture

See [`docs/PLAN.md`](docs/PLAN.md) for full C4 diagrams, UML, and ADRs.

```
CLI → SDK → Orchestrator → [ Judge | Pro | Con ] (separate processes, JSON IPC)
```

---

## Agent Prompts

*(To be documented in [`docs/PROMPTS_BOOK.md`](docs/PROMPTS_BOOK.md) after Phase 5–6.)*

---

## Example Debate Transcript

*(To be added after a full live run — Task 10.5.)*

---

## Screenshots

*(To be added after Phase 8 — CLI implemented.)*

---

## License & Credits

MSC Exercise 02 — Dr. Yoram Segal.
Built with [Claude](https://claude.ai) and [Anthropic API](https://docs.anthropic.com).
