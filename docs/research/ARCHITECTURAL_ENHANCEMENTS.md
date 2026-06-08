# Architectural Enhancements Backlog for LLM-Kosh Verify

## Enhancement E1: Convergent Reasoning Substrate

Goal: Add a deliberate compression and decision layer opposite to the current non-convergent reasoning substrate.

Files:

```text
llm_kosh/engine/reasoning/convergent.py
tests/test_reasoning_convergent.py
```

Acceptance criteria:

- selects a primary path;
- preserves provenance;
- does not mutate FiberBundle;
- records discarded alternatives;
- marks compressed shortcuts as compressed/inferred unless evidence supports discovery.

## Enhancement E2: Opposition Engine

Goal: Deliberately attack converged answers.

Files:

```text
llm_kosh/engine/reasoning/opposition.py
tests/test_reasoning_opposition.py
```

Acceptance criteria:

- surfaces hidden contradiction;
- flags false compression;
- produces falsification questions;
- generates reopen queries;
- scores opposition strength.

## Enhancement E3: Dialectic Controller

Goal: Orchestrate divergence, convergence, opposition, and synthesis.

Files:

```text
llm_kosh/engine/reasoning/dialectic.py
tests/test_reasoning_dialectic.py
```

Output:

```json
{
  "initial_bundle": {},
  "converged_answer": {},
  "opposition_report": {},
  "reopened_bundle": {},
  "final_answer": {},
  "epistemic_status": "survived_opposition"
}
```

## Enhancement E4: Reasoning Tooling

Add MCP/CLI exposure:

```text
reasoning_dialectic_query
reasoning_converge
reasoning_oppose
reasoning_model_world_tick
```

CLI examples:

```bash
llm-kosh reason-dialectic "Why did service X fail?" --time 2026-06-08T10:00:00Z
llm-kosh reason-converge --bundle bundle.json
llm-kosh reason-oppose --answer answer.json --bundle bundle.json
```

## Enhancement E5: Model World Node Schema

Add typed node structures for long-running model-world state:

```text
Fact
Concept
Hypothesis
Contradiction
Abstraction
Decision
Experiment
Implementation
Outcome
Failure
Model
```

## Enhancement E6: Model World Scheduler

Purpose: bounded recurring loops.

Tasks:

- daily contradiction audit;
- weekly abstraction compression;
- benchmark drift detection;
- model-world health report;
- unresolved hypothesis review.

## Enhancement E7: Compression Governance

Problem: A million-node world will become noise without compression.

Controls:

- abstraction nodes must link to supporting paths;
- compression must preserve minority paths;
- compression cannot delete raw evidence;
- compression has confidence and validity window;
- compression can be opposed.

## Enhancement E8: Implementation Feedback Loop

Add implementation nodes and outcome nodes. The system should be able to propose a code/test/documentation change, then ingest the result as an outcome.

Initial safe actions:

- generate test case;
- run benchmark;
- produce patch proposal;
- compare outputs;
- create review report.

## Enhancement E9: Kosh-Aware Training Trace Export

Add command:

```bash
llm-kosh export-traces --format kosh-sft --out training_traces/kosh_reasoning_traces_v0.jsonl
```

Purpose: create training data for models that understand path bundles, provenance, opposition, missing evidence, and abstention.

## Enhancement E10: External Baseline Adapter Harness

Add a stable interface for official baseline runs:

```text
external_baselines/rag_adapter.py
external_baselines/graphrag_adapter.py
external_baselines/selfrag_adapter.py
external_baselines/react_adapter.py
```

Purpose: move from proxy benchmark claims to publishable external comparisons.

## Enhancement E11: Rust Kernel Path

Long-term: move hot graph traversal, path bundle enumeration, and model-world scheduling into Rust for deterministic performance and scale.

Suggested boundary:

```text
Python = product/API/CLI/MCP/orchestration
Rust = reasoning kernel, event log, graph traversal, snapshots
```

## Enhancement E12: AGI-Relevant Safety Controls

Add:

- source trust registry;
- evidence promotion policy;
- speculative artifact limits;
- dialectic loop budget;
- human-review gates;
- domain safety profiles;
- audit log exporter.
