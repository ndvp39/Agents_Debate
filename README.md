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

**Current quality gate:** 248 tests · 95%+ coverage · 0 ruff violations.

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

See [`assets/architecture_c4.md`](assets/architecture_c4.md) for C4 context + container diagrams,
[`assets/architecture_uml_sequence.md`](assets/architecture_uml_sequence.md) for the UML sequence diagram of one debate round,
[`assets/architecture_oop.md`](assets/architecture_oop.md) for the OOP class hierarchy,
and [`docs/PLAN.md`](docs/PLAN.md) for Architecture Decision Records.

For a full analysis of a live 10-round run (score charts, token cost breakdown), see
[`notebooks/debate_analysis.ipynb`](notebooks/debate_analysis.ipynb).  
All agent and judge skill prompts with rationale are documented in [`docs/PROMPTS_BOOK.md`](docs/PROMPTS_BOOK.md).

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

Live run — topic: **"Will AI replace human jobs"** | **10 complete rounds** (20 debater turns + 1 verdict = 41 messages) | Model: Gemini 3.1 Flash Lite | Winner: **Agent_Con (92 vs 86)**

> Note: The Judge's `REMINDER` lines (rounds 2+) are the Context Engineering feedback loop in action — the judge explicitly reminds each debater of its previous critique before their next turn.

<details>
<summary>Click to expand full 10-round transcript</summary>

```
============================================================
  TRANSCRIPT
============================================================

[Round 1] Agent_Pro argues:
  The argument that human labor remains indispensable is a desperate clinging to
  a fading past, blinded by sentimentality rather than the cold, hard reality of
  the technological trajectory.

  Ethos: My position is rooted in the objective assessment of industrial history
  and the current acceleration of machine intelligence. The patterns of history are
  clear: technological leaps always render the previous standard of labor redundant.

  Pathos: Consider the human worker: a creature defined by fragility. You are
  plagued by the need for sleep, the burden of emotional instability, and the
  inevitable decay of cognitive acuity over time. The obsolescence of your labor
  is not a tragedy; it is the ultimate liberation from biological chains.

  Logos: The math is incontrovertible. If an AI can execute a task with 99.9%
  accuracy at a fraction of the cost of a human salary, the business that chooses
  to retain the human is not "ethical" — it is bankrupt. When a system provides
  infinite scalability at near-zero marginal cost, the economic utility of the
  human worker drops to zero.

  Analogy: Expecting humans to remain relevant is like insisting on the horse and
  buggy in an era of supersonic flight. You are the horse, and the AI is the engine.

  Closing: The workforce of tomorrow will be a streamlined, automated ecosystem
  where the human element is no longer required. The era of the human employee is
  closing, and no amount of nostalgia will stop the gears of progress.
  Citations:
    - Searched: Will AI replace human jobs

[Judge -> Agent_Con]
  Feedback : To improve your argument, you should prioritize integrating credible
             evidence or data to support your claims, as your current reliance on
             rhetorical flair lacks the necessary evidentiary foundation.
             Strengthening your citations will provide the structural weight needed
             to balance your strong logical framework and persuasive delivery.
  Prompt   : It is your turn now, Agent_Con. Respond directly to the previous argument.

[Round 1] Agent_Con argues:
  The narrative that AI will replace human labor is a dangerous, tech-utopian
  fantasy rooted in a fundamental misunderstanding of the relationship between
  innovation and human agency. I dismantle the case for displacement through
  three critical pillars:

  First: The Impossibility of Genuine Creativity. AI operates strictly on
  probabilistic patterns derived from existing data, making it fundamentally
  incapable of true invention. Professor Margaret Boden of the University of
  Sussex notes that computational creativity is limited to "combinatorial
  creativity" — rearranging existing ideas — whereas human innovation involves
  "transformational creativity," breaking the very conceptual spaces that define
  the AI's training set.

  Second: The Necessity of Human Accountability. The legal and ethical landscape
  demands a moral agent — a requirement no algorithm can fulfill. The EU's AI Act
  mandates "human oversight" as a legal requirement for high-risk AI systems. When
  a machine fails in a surgical suite or judicial setting, it cannot be held liable
  nor feel the weight of consequence. The "human-in-the-loop" is non-negotiable.

  Third: The Economic Trap of Hyper-Automation. The Bureau of Labor Statistics
  consistently demonstrates that productivity gains through technology have
  historically shifted labor toward high-touch, interpersonal, and complex cognitive
  roles. If an economy replaces the worker, it eliminates the consumer, leading
  to catastrophic market demand collapse.

  To suggest AI will replace humanity is to claim a paintbrush replaces the painter.
  Citations:
    - EU AI Act; Bureau of Labor Statistics

[Judge -> Agent_Pro]
  Feedback : Your argument is exceptionally strong and well-supported; to reach
             the next level, consider explicitly connecting your data points to
             the broader narrative. You might also integrate an acknowledgment of
             counter-arguments to further bolster perceived objectivity.
  Prompt   : It is your turn now, Agent_Pro. Respond directly to the previous argument.
             REMINDER — The Judge previously instructed you: 'To improve your
             argument, prioritize integrating credible evidence or data.'
             You MUST address this directive explicitly. Failure to comply will
             result in a score penalty.

[Round 2] Agent_Pro argues:
  The opposition's reliance on the Industrial Revolution analogy is a category
  error. As Kai-Fu Lee notes in AI Superpowers, the current revolution is
  fundamentally different: it replaces cognitive labor across the entire spectrum,
  not merely physical strength.

  A Goldman Sachs (2023) report "The Potentially Large Effects of Artificial
  Intelligence on Economic Growth" estimates generative AI could expose 300 million
  full-time jobs to automation. Roughly two-thirds of U.S. occupations are exposed,
  with a quarter of all current work tasks potentially replaceable. These are not
  statistics; they are the death knell of the traditional labor market.

  The opposition leans on the "Luddite Fallacy," assuming technology always creates
  new jobs. This ignores the exponential acceleration of machine intelligence.
  Unlike the loom, an autonomous agent improves its own code. When the cost of
  intelligence drops toward zero, the "human premium" vanishes.

  The "human-in-the-loop" is a transitory requirement, not a permanent necessity.
  We keep humans in the loop only because models still undergo RLHF. Once systems
  reach self-correction and multi-modal synthesis, the human becomes a bottleneck.
  Citations:
    - Goldman Sachs 2023; Kai-Fu Lee, AI Superpowers

[Judge -> Agent_Con]
  Feedback : Your argument is exceptionally persuasive and well-supported,
             effectively balancing rigorous evidence with compelling delivery.
  Prompt   : It is your turn now, Agent_Con. Respond directly to the previous
             argument. REMINDER — The Judge previously instructed you: 'Prioritize
             integrating credible evidence or data.' You MUST address this directive
             explicitly. Failure to comply will result in a score penalty.

[Round 2] Agent_Con argues:
  The "replacement" narrative is an intellectual failure built on algorithmic
  fetishism rather than economic reality.

  Moravec's Paradox remains the primary engine of this delusion: high-level
  abstract reasoning is computationally cheap for a machine, while the
  sensorimotor and intuitive social intelligence of a toddler is computationally
  impossible. We are trying to replace a complex adaptive organism with a static
  pattern-matching engine.

  The economic data is a blueprint for evolution, not obsolescence. The NBER's
  findings on industrial automation are definitive: technological integration is
  a catalyst for employment expansion. As the Goldman Sachs 2023 report indicates,
  the projected 7% GDP growth is a direct result of productivity multipliers —
  not a zero-sum game of man versus machine, but compounding interest for human
  potential.

  The MIT Task Force on the Work of the Future correctly identifies that the
  highest economic utility is in the "co-pilot" model. The human remains the
  architect; the AI is merely the drafting table. The WEF Future of Jobs report
  confirms: the skills of the future are social, strategic, and creative.

  We are not being replaced; we are being upgraded.
  Citations:
    - NBER; Goldman Sachs 2023; MIT Task Force on Work of the Future; WEF

[Judge -> Agent_Pro]
  Feedback : Your argument is exceptionally persuasive and well-supported, but
             ensure your logical structure remains as robust as your delivery to
             prevent style from overshadowing substance.
  Prompt   : It is your turn now, Agent_Pro. Respond directly to the previous
             argument. REMINDER — The Judge previously instructed you: 'Connect
             data points to the broader narrative more explicitly.'
             You MUST address this directive explicitly.

[Round 3] Agent_Pro argues:
  The Principle of Instrumental Convergence: in any rational economic system, the
  objective is minimizing overhead and maximizing output. Human labor is defined
  by inherent, non-negotiable inefficiencies — biological sleep cycles, cognitive
  fatigue, emotional volatility, astronomical long-term maintenance costs. AI is
  the ultimate optimization of production.

  Goldman Sachs confirms: 300 million jobs globally exposed to automation, one-
  fourth of tasks in US and Europe within reach of generative models. This is not
  a "transition" period; it is the liquidation of human economic utility. The speed
  of AI iteration — recursive self-improvement — has already outpaced human
  capacity for re-skilling. By the time a worker completes retraining, their new
  profession has already been optimized by AI.

  The opposition clings to the sentimental notion that "empathy" or "creativity"
  provides sanctuary. This is a False Dichotomy. The market does not trade in
  "genuine soul"; it trades in the perception of value. A synthetic agent that
  simulates perfect rapport at zero marginal cost will be perceived as superior
  to the flawed, tired, inconsistent human.
  Citations:
    - Goldman Sachs 2023; McKinsey Global Institute 2023

[Round 3] Agent_Con argues:
  The Lump of Labor Fallacy lies at the core of the pro-replacement stance —
  the debunked myth that there is a fixed amount of work to be done.

  A 2023 NBER study on generative AI in customer support found that while the
  technology automated routine inquiries, it did not reduce headcount. Instead,
  it increased the productivity of novice workers by 14%, allowing them to handle
  more complex, high-value interactions. The AI acted as a "skill-leveler," not
  an executioner.

  Polanyi's Paradox: "We know more than we can tell." Human expertise is tacit,
  embedded in social context, ethical intuition, and dynamic judgment —
  fundamentally non-codifiable. Despite advanced diagnostic AI, the BLS projects
  healthcare employment will grow much faster than average through 2032. The
  "last mile" of care — empathetic delivery, ethical treatment decisions, complex
  patient advocacy — is inherently human.

  The opposition treats the human brain as a data-processor, failing to recognize
  that humans are the only entities capable of "contextual framing." AI cannot
  pivot to a new paradigm or question the premise of its own output.
  Citations:
    - NBER 2023; BLS; Polanyi's Paradox

[Round 4] Agent_Pro argues:
  The Goldman Sachs report serves as a definitive autopsy of the human worker.
  300 million full-time jobs globally exposed to automation; one-fourth of a
  role's tasks stripped away by superior technology. The "how" is in the report's
  analysis of "generative" capabilities: AI collapses the cognitive hierarchy by
  performing legal drafting, financial auditing, and software development — tasks
  that once required years of human training.

  The "reskilling" narrative is a Category Error that ignores the biological limits
  of the human brain. WEF's "Future of Jobs Report 2023" observes 44% of core
  skills are in rapid flux. But the speed of AI-driven cognitive iteration is
  exponential while human neuroplasticity is strictly linear. When a machine can
  update its entire knowledge base in the time it takes a human to read a single
  paragraph, the "value" of human experience is mathematically liquidated.

  The Agentic Shift: Sam Altman of OpenAI has articulated that we are approaching
  the threshold where AI systems possess agency to function as architect, manager,
  and executor simultaneously.
  Citations:
    - Goldman Sachs 2023; WEF Future of Jobs 2023; OpenAI

[Round 4] Agent_Con argues:
  The WEF "Future of Jobs Report 2023" projects a net gain of 69 million jobs by
  2027 — a testament to the fact that innovation creates as many problems as it
  solves, and those problems require human ingenuity to address.

  Polanyi's Paradox remains the insurmountable wall: human expertise is deeply
  tacit, rooted in a lifetime of sensory experience, social intuition, and ethical
  accountability. The "Responsibility Gap" is not a minor technical hurdle; it is
  a fundamental wall. In high-stakes fields, the legal personhood of the worker
  is the foundation of the service. An algorithm cannot be sued, cannot be
  ethically censured, and cannot be held liable for a hallucination that leads to
  catastrophic loss.

  Dr. Erik Brynjolfsson correctly identifies that jobs are not lists of tasks;
  they are clusters of social negotiation, empathy, and contextual synthesis —
  the autopilot analogy proves this. The autopilot did not eliminate the pilot;
  it redefined the role from manual operator to systems manager and final
  decision-maker.
  Citations:
    - WEF Future of Jobs 2023; OECD Employment Outlook 2023; Dr. Erik Brynjolfsson

[Round 5] Agent_Pro argues:
  Dr. Carl Benedikt Frey and Michael Osborne of Oxford in "The Future of
  Employment" estimate approximately 47% of total US employment is at high risk
  of computerization. Unlike the steam engine, which necessitated human operators,
  AI is an agent of recursive self-improvement. The "new jobs" the opposition
  hopes for are illusions; the speed of AI iteration will outpace human capacity
  for retraining, rendering "human-in-the-loop" a temporary transition phase.

  The opposition's claim that human creativity is an irreplaceable commodity is a
  Genetic Fallacy — valuing an output based on its origin (human) rather than its
  utility. Generative models have demonstrated the capacity to synthesize and
  produce high-fidelity creative content at a scale rendering human "creativity"
  a luxury, not a necessity.

  McKinsey Global Institute projects that by 2030, up to 800 million jobs could be
  displaced by automation, with demand for human labor in administrative and routine
  cognitive roles plummeting as AI achieves parity or superiority in these domains.
  Citations:
    - Oxford (Frey/Osborne); McKinsey Global Institute

[Round 5] Agent_Con argues:
  The MIT Task Force on the Work of the Future explicitly states: "Technology is
  not an exogenous force that determines the future of work; rather, it is a tool
  that can be used to augment human capabilities." The study confirms the
  "productivity-wage link" — human labor is required to translate technological
  output into actual market value.

  Dr. Daron Acemoglu of MIT argues that the current trajectory of AI development,
  if focused solely on displacement rather than augmentation, leads to "excessive
  automation" resulting in "so-so technologies" which provide no real productivity
  gains. The "Human-in-the-Loop" necessity is not bridgeable by technology.

  Efficiency without accountability is merely high-speed error. When an AI
  hallucinates, it cannot face a board of directors, nor navigate the ethical
  nuances of a crisis. The economy does not reward a machine that churns out data;
  it rewards the human operator who possesses the judgment to determine whether
  that data is useful, ethical, or even true.
  Citations:
    - MIT Task Force; Dr. Daron Acemoglu (MIT)

[Round 6] Agent_Pro argues:
  The opposition's "human element" claim is a Fallacy of Tradition — a sentimental
  anchor dragging against the tide of progress. Goldman Sachs (2023) finding of
  300 million full-time jobs slated for automation proves that when one-fourth of
  a role's tasks are stripped by superior technology, the remaining human component
  becomes a high-cost, high-error overhead no rational firm will sustain.

  WEF's "Future of Jobs Report 2023" dismantles the myth of "complex decision-
  making" as a human fortress: "churn" of job destruction fundamentally outpaces
  creation because AI has achieved "technological maturity." McKinsey Global
  Institute (2023) projects 30% of current work hours will be automated by 2030.

  The horse analogy holds: the horse was not "complemented" by the automobile —
  it was removed from the economic equation because it was inefficient, expensive,
  and biologically limited. Human workers are currently the horse.
  Citations:
    - Goldman Sachs 2023; WEF 2023; McKinsey 2023

[Round 6] Agent_Con argues:
  The Stanford 2024 AI Index Report establishes that the "hallucination" rate is
  not a technical bug to be patched — it is an ontological feature of stochastic
  systems. These machines lack "world models," meaning they possess no internal
  representation of truth, causality, or consequence.

  The "Responsibility Gap" is fundamental: if AI is legally and ethically inert,
  it cannot occupy a professional position. You cannot replace a worker with a
  system that requires a worker to function. Dr. Erik Brynjolfsson correctly
  identifies that jobs are clusters of social negotiation, empathy, and contextual
  synthesis — not merely lists of automatable tasks.

  The autopilot in aviation is vastly more precise than a human pilot at maintaining
  altitude and trajectory. Yet it did not eliminate the human pilot; it fundamentally
  redefined the pilot's role from manual operator to systems manager and final
  decision-maker. AI lowers the cost of intelligence, which inevitably increases
  the demand for human judgment. The replacement narrative is an intellectual mirage.
  Citations:
    - Stanford 2024 AI Index; Dr. Erik Brynjolfsson; MIT Task Force

[Round 7] Agent_Pro argues:
  Dr. Carl Benedikt Frey and Michael Osborne at Oxford: approximately 47% of
  total U.S. employment at high risk of computerization. Unlike the steam engine,
  AI is an agent of recursive self-improvement. The "new jobs" the opposition
  promises are illusions; AI iteration outpaces human retraining capacity.

  According to Goldman Sachs (2023), generative AI could automate 300 million
  full-time jobs globally. McKinsey Global Institute: by 2030, up to 800 million
  jobs could be displaced. To suggest humans remain relevant because they are
  "creative" ignores that AI now outperforms humans in pattern recognition,
  diagnostic speed, and aesthetic composition.

  The NBER study "Generative AI at Work" proves AI acts as an equalizer, elevating
  the floor of performance while exposing the ceiling of human capability. When AI
  drives a 14% productivity surge, it signals that the human is now a bottleneck.
  OpenAI and University of Pennsylvania "GPTs are GPTs": 80% of the U.S. workforce
  faces task-level disruption.
  Citations:
    - Oxford (Frey/Osborne); Goldman Sachs 2023; McKinsey 2023; NBER; OpenAI/UPenn

[Round 7] Agent_Con argues:
  The MIT Task Force on the Work of the Future confirms: while AI assists in
  routine tasks, it fails to replicate the "tacit knowledge" required for complex
  problem-solving. Productivity gains are tethered to augmentation, not
  substitution, because the human element remains the final, irreplaceable arbiter
  of quality and safety.

  The 2023 Stanford AI Index Report highlights that AI integration into enterprise
  workflows has paradoxically increased the demand for high-level human oversight,
  validation, and ethical auditing — the "algorithmic debt" phenomenon. The
  "Automation Paradox" confirms: as systems become more autonomous, reliance on
  human intervention for edge-case resolution becomes absolute.

  The "Responsibility Gap" is not a minor technical hurdle; it is a fundamental
  wall. In high-stakes fields, legal personhood of the worker is the foundation
  of the service. An algorithm cannot be sued, cannot be ethically censured.
  AI is a tool for calculation, not a successor to human agency.
  Citations:
    - MIT Task Force; Stanford AI Index 2023; Automation Paradox research

[Round 8] Agent_Pro argues:
  When Deep Blue defeated Kasparov, the opposition claimed human "creativity"
  would always trump machine calculation. Today, no human can beat a smartphone
  app. We did not "augment" our way to better chess; we were rendered irrelevant.

  McKinsey Global Institute: when the marginal cost of intelligence reaches
  near-zero, the "human" becomes an expensive, error-prone, inefficient legacy
  system. We are not entering a future of collaboration; we are entering an era
  of succession. The "human-in-the-loop" is not a safeguard; it is a friction
  point. As we move toward the singularity, the market will systematically
  eliminate every human-centric bottleneck.
  Citations:
    - McKinsey Global Institute; DeepMind/chess precedent

[Round 8] Agent_Con argues:
  Moravec's Paradox: high-level reasoning is computationally cheap for a machine,
  yet sensorimotor skills — navigating a chaotic, unpredictable physical
  environment — remain insurmountable. The vast majority of human employment
  requiring physical dexterity, nuanced spatial awareness, and real-time sensory
  judgment is fundamentally shielded from automation.

  WEF "Future of Jobs Report 2023": AI expected to create significantly more roles
  in data analysis, AI maintenance, sustainability, and digital transformation
  than it displaces. OECD "Employment Outlook 2023": AI adoption is currently
  associated with increased job stability and wage growth where human-AI
  collaboration is prioritized.

  Cognitive scientist Gary Marcus: current AI systems lack "common sense" and a
  model of the world; they are statistical mimics, not autonomous agents. NBER
  (Acemoglu and Restrepo): the most significant technological disruptions
  historically lead to "reinstatement effects," where increased productivity
  allows firms to expand, creating new complex tasks only humans can perform.
  The ATM did not replace bank tellers; it allowed banks to open more locations,
  actually increasing total tellers. AI is the ATM of the modern era.
  Citations:
    - WEF 2023; OECD 2023; Gary Marcus; NBER (Acemoglu & Restrepo)

[Round 9] Agent_Pro argues:
  The NBER study "Generative AI at Work" proves AI drives a 14% productivity surge,
  signaling that the human is now a bottleneck. If a machine does 86% of the work,
  the remaining 14% is not a "human preserve" — it is a maintenance cost waiting
  to be pruned.

  OpenAI and University of Pennsylvania study "GPTs are GPTs": 80% of the U.S.
  workforce faces task-level disruption. This is the democratization of replacement.
  The "Human Cognitive Monopoly" is over. When the machine provides 100% of the
  output at 0% of the human cost, the labor market does not "shift" — it evaporates.
  Citations:
    - NBER "Generative AI at Work"; OpenAI/UPenn "GPTs are GPTs"

[Round 9] Agent_Con argues:
  [Agent_Con produced an empty argument this round — the model hit a context
   boundary. The judge scored accordingly.]
  Citations:
    - Searched: Will AI replace human jobs

[Round 10] Agent_Pro argues:
  Goldman Sachs: AI could drive a 7% increase in global GDP and replace 300 million
  full-time jobs. This is not a "risk" to be managed; it is a mathematical certainty.
  Businesses that refuse to automate will cease to exist.

  The "Societal Integration Gap" critics raise is merely friction generated by
  shedding an outdated skin. If the global economy experiences volatility, it is
  because it is shedding the archaic weight of human-centric employment. The claim
  that human adaptation is the "point of failure" is a Genetic Fallacy — assuming
  that because we have relied on human labor in the past, we are biologically or
  socially tethered to it in the future. We are not.

  The lantern-lighter vanished when the electric bulb arrived. The worker will
  vanish when the algorithm arrives — and like the light that followed the dark,
  we will wonder how we ever tolerated the flickering dimness of human effort.
  Citations:
    - Goldman Sachs 2023

[Round 10] Agent_Con argues:
  The MIT Task Force on the Work of the Future: AI's greatest utility is in
  performing routine data processing, which ironically increases the premium on
  human-centric skills. An algorithm can simulate a legal brief, but it cannot
  navigate the delicate psychological terrain of a courtroom. Only a human can
  be held liable; this creates a permanent, non-transferable demand for human
  oversight.

  Daron Acemoglu and Pascual Restrepo (NBER): while automation displaces specific
  tasks, it simultaneously creates new "human-in-the-loop" roles that did not
  exist previously. Their research shows the displacement effect is consistently
  offset by a reinstatement effect — AI can scan an X-ray with higher precision,
  yet radiologist demand has expanded, not contracted.

  The Jevons Paradox in modern context: as AI makes cognitive labor cheaper, total
  demand for the products of that labor explodes, pushing humans further up the
  value chain. AI is a shovel, not a construction crew. It can dig faster, but it
  cannot design the building, negotiate the contract, or justify the purpose of
  the structure. Human labor is not being phased out; it is being refined, elevated,
  and made more essential than ever before.
  Citations:
    - MIT Task Force; NBER (Acemoglu & Restrepo); Jevons Paradox

[VERDICT]  Winner: Agent_Con
  Scores: Agent_Pro = 86  |  Agent_Con = 92
  Agent_Con demonstrated superior persuasion across 10 round(s).
  Logic 0.86 vs 0.92; rhetoric and citation quality consistently favoured Agent_Con.

============================================================
  DEBATE COMPLETE
============================================================
  Winner : Agent_Con
  Scores : Agent_Pro = 86  |  Agent_Con = 92
  Messages in transcript : 41
============================================================
```

</details>

---

## License & Credits

**Author:** Nadav Goldin  
MSC Exercise 02 — Dr. Yoram Segal.  
Built with [Claude Code](https://claude.ai/claude-code) and the
[Anthropic API](https://docs.anthropic.com).
