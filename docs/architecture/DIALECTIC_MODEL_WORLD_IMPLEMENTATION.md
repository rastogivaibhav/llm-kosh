# LLM-Kosh Verify: Dialectic Model World Implementation

This work package turns the white-paper/runbook concept into executable scaffolding inside the LLM-Kosh/TheHypoKosh reasoning engine.

## Added runtime layers

- `llm_kosh/engine/reasoning/convergent.py`
  - Cognitive substrate for convergent reasoning.
  - Selects the strongest provisional answer from a `FiberBundle`.
  - Produces compression candidates such as `A -> C` from `A -> B -> C` while preserving that the shortcut is inferred/compressed, not discovered truth.

- `llm_kosh/engine/reasoning/opposition.py`
  - Cognitive substrate for opposition reasoning.
  - Attacks the converged answer by surfacing discarded alternatives, hidden assumptions, unproven selected edges, contradiction survival, and falsification questions.

- `llm_kosh/engine/reasoning/dialectic.py`
  - Orchestrates the loop: non-convergent query -> convergence -> opposition -> theoretical re-open -> synthesis.
  - Exposed through `ReasoningEngine.dialectic_query(...)`.

- `llm_kosh/engine/reasoning/model_world.py`
  - Adds a finite, inspectable model-world schema for typed cognitive objects.
  - Supports nodes such as TemporalFact, Concept, Hypothesis, Contradiction, Abstraction, Experiment, Implementation, Outcome, Failure, Decision, Model, Opposition, and Reinforcement.
  - Includes a partition plan for million-node model worlds.

## Why this matters

The previous engine was primarily non-convergent: preserve alternatives, avoid premature certainty, and escape pattern lock. This package adds its deliberate opposite: convergent compression and decision. It then adds an opposition layer that attacks convergence before synthesis.

The cognitive rhythm becomes:

```text
Diverge -> Converge -> Oppose -> Re-open -> Synthesize -> Record in model world
```

This is intended to avoid two failure modes:

1. Pure convergence: confident but premature answers.
2. Pure non-convergence: endless alternatives without decision.

## AGI-relevant direction

This is not an AGI claim. The package is a step toward a memory architecture for agentic systems that can inspect, adapt, compress, oppose, and revise over a finite model world. The next major step is to connect dialectic traces to Kosh-aware model training data.
