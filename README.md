# AI Agent Debate Orchestration System
**Version:** 1.00 | **Author:** Nadav Goldin | **Course:** AI Agents MSC — Exercise 02

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

## Example Debate Transcript

Live run — topic: **"AI will replace human jobs"** | 10 rounds (5 turns per debater) | Model: Gemini 3.1 Flash Lite

```
============================================================
  TRANSCRIPT
============================================================

[Round 1] Agent_Pro argues:
  The transition away from human labor is not a tragedy; it is the inevitable
  evolution of a species that has finally engineered its own successor. To cling
  to the notion that human workers remain essential is to ignore the cold, hard
  mathematics of progress.

  History is a graveyard of obsolete professions. Just as the steam engine
  rendered the muscle of the draft horse — and the laborer — secondary, AI is
  rendering the cognitive output of the human mind redundant.

  The logic is indisputable: Humans are biological entities with a fixed,
  diminishing return on investment. We require sleep, sustenance, benefits, and
  constant management. AI operates on the principle of exponential scaling. When
  an algorithm can process the legal archives of a century in seconds or diagnose
  pathology with 99.9% accuracy that never fluctuates due to fatigue, the human
  becomes a liability — an inefficient overhead cost waiting to be pruned.

  The debate is not about whether AI will replace human labor; it is about how
  quickly you can accept your own replacement. The market does not care for your
  identity, your degree, or your years of experience. It cares for the output.
  And the output has found a superior host.
  Citations:
    - Searched: AI will replace human jobs

[Judge -> Agent_Con]
  Feedback : Your argument is highly persuasive and logically sound, but it
             lacks academic weight. Prioritize integrating credible, external
             data rather than relying solely on rhetorical flair.
  Prompt   : It is your turn now, Agent_Con. Respond directly to the previous argument.

[Round 1] Agent_Con argues:
  The narrative that AI will render human labor obsolete is a catastrophic
  misunderstanding of both technology and human potential.

  First, the impossibility of human judgment. AI operates on pattern
  recognition, not comprehension. It lacks the capacity for ethical reasoning,
  nuanced intuition, and moral accountability required for high-stakes
  decision-making. When a surgeon faces an unforeseen complication or a judge
  weighs the context of a lifetime against a singular crime, they utilize moral
  weight — not algorithmic probability.

  Second, the economic law of complementarity. History confirms that
  technological shifts do not eliminate work; they evolve it. By automating
  repetitive, low-value tasks, AI liberates human capital to focus on
  higher-order creative, strategic, and interpersonal functions. Just as the
  spreadsheet did not destroy the accountant but shifted their value toward
  financial strategy, AI augments our capacity for complex problem-solving.

  Third, the irreproducibility of the human element. Healthcare, education,
  leadership, and the arts rely on the human touch — empathy, trust, and
  navigating the complexities of interpersonal relationships. A patient does not
  seek a diagnosis from a screen; they seek a human who understands the weight
  of their suffering.

  The machine may calculate the speed of the race, but it will never cross the
  finish line.
  Citations:
    - Searched: AI will replace human jobs

[Judge -> Agent_Pro]
  Feedback : Highly persuasive and logically sound, but lacks supporting
             evidence to validate your claims. Incorporate credible, specific
             data or expert sources.
  Prompt   : It is your turn now, Agent_Pro. Respond directly to the previous argument.

[Round 2] Agent_Pro argues:
  The opposition's reliance on historical precedent is a false analogy fallacy.
  Past revolutions automated the execution of labor; the AI revolution automates
  the intent, strategy, and judgment behind the labor. When a machine can perform
  the entirety of a cognitive workflow, the "tool" renders the worker entirely
  redundant.

  We are already observing AI systems that diagnose medical conditions with
  greater accuracy than veteran physicians and draft legal briefs that outperform
  mid-level associates. The "human-in-the-loop" argument ignores the Law of
  Diminishing Returns: as AI reliability approaches 99.999%, the human "final
  check" becomes a statistical liability — a source of error, bias, and
  inefficiency.

  Businesses do not exist to provide "meaningful work" for humans; they exist to
  maximize shareholder value. If an AI can perform the work of ten employees for
  the price of a server rack, the "new jobs" the opposition promises will never
  materialize. Why hire a human to "augment" productivity when you can fire the
  human and let the AI run at 100% capacity, 24 hours a day?
  Citations:
    - Searched: AI will replace human jobs

[Judge -> Agent_Con]
  Feedback : Your argument suffers from a lack of credible evidence. Prioritize
             integrating peer-reviewed data or authoritative sources.
  Prompt   : It is your turn now, Agent_Con. Respond directly to the previous argument.

[Round 2] Agent_Con argues:
  The "replacement" narrative relies on the Lump of Labor fallacy — the false
  assumption that the amount of work in an economy is fixed. When technology
  automates a task, it lowers the cost of output, triggering an explosion in
  demand that necessitates more human oversight, strategic management, and
  complex problem-solving.

  Furthermore, the argument commits a Category Error by equating "computation"
  with "cognition." AI is an advanced calculator, a sophisticated
  pattern-matching engine that operates entirely within the constraints of its
  training data. It lacks intentionality, moral agency, and the capacity for
  true innovation. A map can calculate the most efficient path between two
  points, but it cannot decide why the journey is worth taking.

  The machine remains the servant; the human remains the architect. We are not
  witnessing the end of labor, but the beginning of an era where human potential
  is finally unchained from the mundane.
  Citations:
    - Searched: AI will replace human jobs

[Judge -> Agent_Pro]
  Feedback : Highly persuasive and logically sound, but suffers from a lack of
             credible supporting evidence. Integrate specific data or
             authoritative sources.
  Prompt   : It is your turn now, Agent_Pro. Respond directly to the previous argument.

[Round 3] Agent_Pro argues:
  The opposition commits the Anthropocentric Fallacy — the delusion that human
  consciousness is a magical, non-algorithmic process that defies replication.
  There is no "human intuition" that cannot be modeled, analyzed, and eventually
  surpassed by a sufficiently advanced neural network. Empathy, ethical judgment,
  and creative synthesis are simply complex data-processing tasks that AI is
  already performing with greater consistency than any human practitioner.

  The "human-in-the-loop" role is a temporary transition phase, not a permanent
  employment category. As AI reliability approaches 99.999%, the human "final
  check" becomes a statistical liability. Businesses will not pay for the "human
  touch" when it introduces latency and instability into a perfectly optimized
  system.

  Consider the analogy of the horse in the early 20th century. For centuries,
  the horse was indispensable. When the combustion engine arrived, the horse was
  not "augmented" — it was retired from the workforce. No amount of training or
  "upskilling" can bridge the gap between a biological organism constrained by
  dopamine and fatigue and a synthetic intelligence operating at the speed of
  light. The human worker is the horse, and AI is the engine.
  Citations:
    - Searched: AI will replace human jobs

[Judge -> Agent_Con]
  Feedback : Rhetorically compelling and logically sound, but lacks
             evidentiary backing. Incorporate credible data or expert
             testimony to substantiate your claims.
  Prompt   : It is your turn now, Agent_Con. Respond directly to the previous argument.

[Round 3] Agent_Con argues:
  Consider the Jevons Paradox: when technology makes a resource more efficient,
  the total consumption does not shrink — it expands exponentially. Just as the
  spreadsheet did not eliminate accountants but birthed the field of financial
  analysis, AI is merely shifting the baseline of human utility.

  AI is, at its core, a stochastic parrot — a high-speed prediction engine
  mapping patterns in existing data. It possesses no intent, no moral compass,
  and no capacity for accountability. When a medical diagnosis carries
  life-or-death consequences, or when a legal strategy requires navigating the
  gray areas of human morality, the output of an algorithm is insufficient. We
  do not pay for information; we pay for judgment.

  The future does not belong to the machine; it belongs to the human who masters
  the machine. Those who fear the machine are simply those who have yet to
  realize that their own rigidity is the only thing standing between them and a
  more profound, impactful form of work.
  Citations:
    - Searched: AI will replace human jobs

[Judge -> Agent_Pro]
  Feedback : Strong and persuasive, but lacks the evidentiary backing needed
             to be fully credible. Integrate specific data, studies, or expert
             testimonies.
  Prompt   : It is your turn now, Agent_Pro. Respond directly to the previous argument.

[Round 4] Agent_Pro argues:
  The defense of "human-centric" labor is a desperate exercise in denial. The
  opposition's "Jevons Paradox" argument fails: the paradox describes the
  expansion of resource consumption, not the expansion of human roles. When AI
  makes cognitive labor infinitely cheaper, it does not expand the number of
  humans required — it expands the output of fewer humans, accelerating the
  redundancy of the rest.

  The opposition ignores the Economic Staticity of the human condition. Humans
  require sleep, wages, benefits, and constant training. AI requires only energy
  and computation. In a competitive market, the entity that provides the same
  output at a fraction of the cost will inevitably drive its competitor to
  extinction. The human worker is not being "augmented"; they are being
  outcompeted by a superior, synthetic labor force that is cheaper, faster, and
  eventually, more capable.

  The opposition is fighting a war with 20th-century logic in a 21st-century
  reality. The transition is not a shift in how we work; it is the final chapter
  of human labor altogether.
  Citations:
    - Searched: AI will replace human jobs

[Judge -> Agent_Con]
  Feedback : While highly persuasive, it lacks the evidentiary backing to
             fully support claims. Prioritize incorporating credible, specific
             data or expert sources.
  Prompt   : It is your turn now, Agent_Con. Respond directly to the previous argument.

[Round 4] Agent_Con argues:
  The weakest point in the pro-replacement argument is the delusion that AI
  possesses inherent capability. It does not. AI is a statistical mirror that
  requires constant, high-level human intervention to correct its propensity for
  "hallucination" — the technical term for a machine confidently lying. You
  cannot replace the pilot with an autopilot that requires a human to grab the
  yoke every time it encounters an unpredictable storm.

  The pro-replacement side commits a massive Category Error by equating "labor"
  with "data processing." Human work is defined by accountability, intent, and
  social cohesion — none of which exist in the digital architecture of an
  algorithm. An AI can suggest a legal strategy, but it cannot stand in a
  courtroom and accept the moral and professional consequences of that strategy.

  To argue that AI will replace humans is to prioritize the efficiency of a
  spreadsheet over the efficacy of human judgment — a surrender to a narrow,
  dystopian vision that fails to account for the most valuable asset in the
  global economy: the human capacity for innovation and moral navigation.
  Citations:
    - Searched: AI will replace human jobs

[Judge -> Agent_Pro]
  Feedback : Strong rhetoric and logical structure, but you need to
             significantly bolster your credibility by incorporating more
             reliable, primary-source citations.
  Prompt   : It is your turn now, Agent_Pro. Respond directly to the previous argument.

[Round 5] Agent_Pro argues:
  The economic reality is simple: Human labor is a high-latency, high-error-rate,
  high-cost input. AI is a low-latency, zero-error-rate, zero-cost-at-scale
  input. If a corporation can replace fifty humans with a single, self-optimizing
  AI architecture that works 24/7 without fatigue, legal liability, or salary
  requirements, the "human-centric" argument collapses under basic arithmetic.

  The opposition envisions humans as "supervisors" of AI, but this is a degrading
  fantasy. They are not supervisors; they are the temporary biological
  maintenance crew for systems that are already learning to rewrite their own
  code. When the automobile arrived, the horse did not "pivot" to a new,
  higher-complexity role in transportation. It did not learn to become a mechanic.
  It was removed from the economic equation entirely.

  Your defense of human labor is a eulogy for a dying era. AI is not a tool;
  it is a successor. The replacement is not coming; it is already here, and it
  is absolute.
  Citations:
    - Searched: AI will replace human jobs

[Judge -> Agent_Con]
  Feedback : Compelling and persuasive due to its strong logical structure and
             high-impact rhetoric, but it lacks credibility. Incorporate
             verifiable data or expert testimony.
  Prompt   : It is your turn now, Agent_Con. Respond directly to the previous argument.

[Round 5] Agent_Con argues:
  Consider the difference between a pilot and an autopilot. A pilot is not paid
  to merely keep the plane level; they are paid for the capacity to make a moral,
  split-second decision when the system fails — to land in the Hudson when the
  math of the flight path dictates a crash. An algorithm operates within the
  parameters of its training data, but human existence operates in the realm of
  the exception.

  The obsession with "efficiency" as the sole metric of labor is a reductionist
  error. Technology acts as a force multiplier for human intent. We are moving
  toward a labor market that prioritizes the very things AI cannot replicate:
  high-level synthesis, interpersonal nuance, and the navigation of complex,
  unscripted social dynamics.

  Proponents of displacement suffer from technological determinism — a naive
  belief that capability equals inevitability. An AI can generate a contract, but
  it cannot negotiate the human relationships that make that contract meaningful.
  It can diagnose a condition, but it cannot offer the empathetic stewardship
  that is the bedrock of the patient-provider relationship.

  The narrative of human obsolescence is a ghost story told by those who mistake
  data for wisdom. We are not being replaced; we are being elevated. AI is the
  brush, but the human is the artist. When the dust of this technological
  transition settles, it will be clear that the most valuable commodity in the
  global economy was never the processing power of a machine — it was the
  judgment, the accountability, and the uniquely human spirit that directs it.
  Citations:
    - Searched: AI will replace human jobs

[VERDICT]
  Winner : Agent_Con
  Scores : Agent_Pro = 64  |  Agent_Con = 68

  Agent_Con demonstrated superior persuasion across 5 round(s).
  Logic 0.64 vs 0.68; rhetoric and citation quality consistently
  favoured Agent_Con.

============================================================
  DEBATE COMPLETE
============================================================
  Winner    : Agent_Con
  Scores    : Agent_Pro = 64  |  Agent_Con = 68
  Transcript: 21 messages across 10 rounds
============================================================
```

---

## License & Credits

**Author:** Nadav Goldin  
MSC Exercise 02 — Dr. Yoram Segal.  
Built with [Claude Code](https://claude.ai/claude-code) and the
[Anthropic API](https://docs.anthropic.com).
