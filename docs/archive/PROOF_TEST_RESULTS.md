# LLM-Kosh / TheHypoKosh Proof Test Results

Date: 2026-06-08
Package tested and patched: `llm-kosh-TheHypoKosh-provenance-layers.zip`

## What was tested

This run tested whether the patched LLM-Kosh/TheHypoKosh system demonstrates the core behaviours needed to move beyond ordinary retrieval:

1. temporal validity and supersession;
2. causal path exploration;
3. contradiction visibility;
4. inferred-vs-discovered provenance;
5. reinforcement without false discovery promotion;
6. hyperedge joint-causality traversal;
7. no-evidence abstention;
8. comparison against representative deterministic baselines:
   - KeywordRAG;
   - TemporalRAG;
   - AgentMemory;
   - GraphRAG;
   - SelfRAG-like;
   - ReAct-like.

Important limitation: these baselines are representative deterministic baselines created for a controlled benchmark. They are not claims against every published implementation of GraphRAG, Self-RAG, ReAct, or agent memory.

## Code-level tests

### Reasoning/provenance suite

Command:

```bash
python3 -m pytest -q \
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

Result:

```text
75 passed in 3.46s
```

### Core non-MCP suite

Command:

```bash
python3 -m pytest -q \
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

Result:

```text
44 passed in 1.63s
```

## Comparative benchmark

Benchmark file generated:

```text
reports/benchmarks/thehypokosh_comparative_benchmark_v0.json
reports/benchmarks/thehypokosh_comparative_benchmark_v0.md
```

Average scores:

| System | Average score |
|---|---:|
| TheHypoKosh | 1.000 |
| TemporalRAG | 0.938 |
| AgentMemory | 0.938 |
| GraphRAG | 0.938 |
| SelfRAG-like | 0.938 |
| ReAct-like | 0.938 |
| KeywordRAG | 0.875 |

Feature checks:

| Feature | Result |
|---|---:|
| inferred compressed shortcut preserved | 1/1 |
| mechanistic chain preserved | 1/1 |
| hyperedge joint sources handled | 1/1 |
| no-evidence abstention | 1/1 |

## What this proves

This proves a narrow, controlled claim:

> On a deterministic temporal-causal-provenance benchmark, the patched TheHypoKosh engine correctly handles temporal truth, causal chains, contradiction, inferred-vs-discovered provenance, hyperedge joint-causality, and no-evidence abstention, and outperforms representative retrieval/agent-memory baselines on the benchmark.

## What this does not prove

This does not prove AGI.

It also does not prove superiority over every strong production implementation of GraphRAG, Self-RAG, ReAct, or agent-memory systems.

To prove research-grade superiority, the next step is to run this benchmark pattern against:

1. a larger held-out dataset;
2. external baselines with published implementations;
3. ablation studies;
4. blind or semi-blind ground truth;
5. multiple domains, such as incidents, legal/policy changes, scientific literature, and software architecture decisions.

## Patch made during this test

The benchmark exposed one important issue:

- unrelated/no-evidence queries could still receive weak resonance anchors and then become artificially stable due to causal bonus.

Fix added:

- anchor selection now requires lexical grounding or very high resonance;
- unrelated queries now correctly produce `no_evidence` / `abstain`.

Regression test added:

```text
tests/test_reasoning_no_evidence_guard.py
```

