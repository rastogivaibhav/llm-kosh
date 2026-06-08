# LLM-Kosh Verify Implementation Runbook: Dialectic Core and Model World

## Purpose

This runbook defines how to evolve LLM-Kosh Verify from a temporal-causal memory engine into a dialectical model-world substrate.

It covers:

1. environment validation;
2. implementation sequence;
3. code modules to add;
4. data model changes;
5. test strategy;
6. benchmark strategy;
7. release gates;
8. operational safety.

## Baseline Validation

From the repository root, run:

```bash
python -m pytest -q \
  tests/test_reasoning_causal_dag.py \
  tests/test_reasoning_retrieval.py \
  tests/test_reasoning_fiber_bundle.py \
  tests/test_reasoning_lyapunov.py \
  tests/test_reasoning_escape.py \
  tests/test_reasoning_engine.py \
  tests/test_reasoning_discourse.py \
  tests/test_reasoning_formatter.py \
  tests/test_demo_reasoning.py \
  tests/test_cli_reason.py \
  tests/test_reasoning_provenance_layers.py \
  tests/test_reasoning_no_evidence_guard.py
```

Expected current result in the verified package: 75 reasoning/provenance tests passing.

Then run:

```bash
python -m pytest -q \
  tests/test_cli_core.py \
  tests/test_cli_healing.py \
  tests/test_cli_health.py \
  tests/test_cli_intake.py \
  tests/test_cli_packs.py \
  tests/test_cli_processors.py \
  tests/test_cli_semantic.py \
  tests/test_conformance.py \
  tests/test_daemon.py \
  tests/test_daemon_reasoning_sync.py \
  tests/test_engine_direct.py \
  tests/test_imports.py \
  tests/test_orthogonal_subspaces.py \
  tests/test_receipt_trust.py \
  tests/test_workbench.py
```

Expected current result: 44 core non-MCP tests passing.

## Branching

Create a dedicated branch:

```bash
git checkout -b feature/dialectic-model-world-v0
```

Do not mix this with packaging or desktop UI work. Keep the first implementation focused on reasoning engine correctness.

## Phase 1: Add Convergent Engine

Create:

```text
llm_kosh/engine/reasoning/convergent.py
```

Class:

```python
class ConvergentEngine:
    def converge(self, bundle, mode="balanced") -> ConvergedAnswer:
        ...
```

Data structure:

```python
@dataclass
class ConvergedAnswer:
    primary_fact_id: str | None
    primary_path: list[str]
    compressed_edges: list[str]
    evidence_refs: list[EvidenceRef]
    confidence: float
    convergence_reason: str
    discarded_paths: list[DiscardedPath]
    residual_uncertainty: list[str]
    false_promotion_risk: float
```

Rules:

- Never mutate the original FiberBundle.
- Never promote inferred edges to discovered.
- Always preserve discarded paths as metadata.
- Convergent output is a decision view, not a truth rewrite.

Tests:

```text
tests/test_reasoning_convergent.py
```

Required cases:

- chooses strongest mechanistic path;
- preserves inferred shortcut as compressed, not discovered;
- keeps discarded alternatives;
- returns abstain when no evidence;
- does not alter edge provenance.

## Phase 2: Add Opposition Engine

Create:

```text
llm_kosh/engine/reasoning/opposition.py
```

Class:

```python
class OppositionEngine:
    def oppose(self, converged_answer, original_bundle) -> OppositionReport:
        ...
```

Data structure:

```python
@dataclass
class OppositionReport:
    challenged_claims: list[str]
    discarded_path_alerts: list[str]
    hidden_contradictions: list[str]
    shortcut_risks: list[str]
    falsification_questions: list[str]
    reopen_queries: list[str]
    opposition_score: float
```

Rules:

- Attack the converged answer, not the whole memory graph.
- Focus on what convergence discarded or compressed.
- Label speculative challenges clearly.
- Generate reopen queries for the non-convergent engine.

Tests:

```text
tests/test_reasoning_opposition.py
```

Required cases:

- detects hidden contradiction;
- flags over-compressed A -> C shortcut;
- surfaces discarded minority path;
- generates falsification question;
- produces low opposition score when convergence is well supported.

## Phase 3: Add Dialectic Controller

Create:

```text
llm_kosh/engine/reasoning/dialectic.py
```

Class:

```python
class DialecticController:
    def run(self, query, temporal_context=None, mode="balanced", max_rounds=2) -> DialecticResult:
        ...
```

Loop:

```text
non-convergent query
 -> converge
 -> oppose
 -> reopen if needed
 -> reconverge
 -> final synthesis
```

Stop rules:

- opposition_score below threshold;
- no_evidence abstention;
- max_rounds reached;
- false_promotion_risk above threshold requires human review;
- contradiction unresolved but explicitly disclosed.

Tests:

```text
tests/test_reasoning_dialectic.py
```

Required cases:

- converges then reopens due to hidden contradiction;
- stops when answer survives opposition;
- preserves original and revised bundles;
- avoids infinite loops;
- marks final status as survived_opposition, unstable, or needs_evidence.

## Phase 4: Add Model World Schema

Create:

```text
llm_kosh/engine/model_world/
  __init__.py
  nodes.py
  partitions.py
  scheduler.py
  compression.py
  feedback.py
```

Node types:

```text
TemporalFact
ConceptNode
HypothesisNode
ContradictionNode
AbstractionNode
DecisionNode
ExperimentNode
ImplementationNode
OutcomeNode
FailureNode
ReinforcementNode
OppositionNode
ModelNode
```

Initial implementation can store these as typed TemporalFacts with `source="model_world"` and structured metadata. Later versions can add first-class tables or a Rust core.

## Phase 5: Add Model World Scheduler

Purpose: run loops over finite data without uncontrolled autonomy.

Scheduler cycle:

```text
select active question
 -> dialectic run
 -> create/update nodes
 -> propose implementation task
 -> wait for observed outcome
 -> ingest outcome
 -> update abstractions
```

Do not allow arbitrary external actions in v0. Implement local-only tasks first:

- benchmark run;
- code inspection;
- document comparison;
- memory consistency audit;
- provenance audit.

## Phase 6: Scale Plan Toward One Million Nodes

Do not begin by generating one million nodes. Scale progressively:

```text
1k nodes: correctness tests
10k nodes: traversal performance
100k nodes: partitioning and compression tests
1m nodes: model-world stress run
```

Required engineering controls:

- partition by domain, time, and node type;
- snapshot hot graph;
- event-log compaction;
- abstraction compression;
- path-bundle limits;
- query-time budget;
- memory budget;
- degeneracy cap;
- audit sampling.

## Phase 7: Evaluation

Run current held-out suite:

```bash
python research_eval/scripts/run_multidomain_evaluation.py
```

Expected current benchmark output location:

```text
reports/research_eval/multidomain_holdout_v1.md
reports/research_eval/ablation_v1.md
```

Add new dialectic metrics:

- convergence accuracy;
- opposition survival rate;
- path-loss rate;
- false-compression rate;
- reopened-path utility;
- final answer improvement after opposition;
- model-world compression gain;
- implementation feedback quality.

## Phase 8: External Baselines

Create:

```text
external_baselines/
  rag_adapter.py
  graphrag_adapter.py
  selfrag_adapter.py
  react_adapter.py
  agent_memory_adapter.py
```

Required adapter output schema:

```json
{"id":"task_id", "answer":"...", "evidence_keys":["..."], "metadata":{}}
```

External baseline runs must be pinned by:

- package version;
- model name/version;
- prompt template;
- retrieval settings;
- run date;
- random seed where applicable.

## Phase 9: Kosh-Aware Model Dataset

Add trace export:

```text
query
facts
initial_bundle
converged_answer
opposition_report
reopened_bundle
final_answer
ground_truth
```

Store as JSONL:

```text
training_traces/kosh_reasoning_traces_v0.jsonl
```

This becomes the basis for fine-tuning or instruction-tuning a Kosh-aware model.

## Phase 10: Release Gates

A release can be called v0.3 Dialectic Core only when:

- all existing tests pass;
- convergent/opposition/dialectic tests pass;
- no-evidence abstention remains correct;
- inferred edges are never silently promoted;
- convergence preserves discarded paths;
- opposition improves at least one benchmark family;
- reports are reproducible from command line;
- documentation is updated.

## Rollback Plan

If dialectic functionality destabilises existing reasoning:

1. keep `reasoning_query` unchanged;
2. expose dialectic as new optional command/tool only;
3. disable with config:

```json
{"reasoning": {"dialectic_enabled": false}}
```

4. retain existing TheHypoKosh balanced mode as default.

## Operational Safety

The v0 dialectic system must remain bounded:

- no autonomous external web actions by default;
- no file mutation outside project workspace;
- no silent memory promotion;
- no deletion of minority paths;
- all model-world updates go through event log;
- all speculative nodes are labelled;
- human review required for high-impact decisions.
