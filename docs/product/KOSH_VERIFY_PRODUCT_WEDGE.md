# Kosh Verify: Product Wedge for LLM-Kosh / TheHypoKosh

## One-line product claim

**Kosh Verify is the reliability memory layer for long-running AI agents.**

It helps agents verify what changed, what caused what, what contradicts what, what was inferred but not discovered, and when the safest answer is to abstain.

## Why this is based on this project

Kosh Verify is not a new speculative layer bolted on from outside. It is a productisation of the current LLM-Kosh / TheHypoKosh codebase:

- `ReasoningEngine` already stores `TemporalFact` objects.
- `CausalDAG` already stores typed edges and hyperedges.
- `FiberBundle` already preserves multiple reasoning paths.
- `LyapunovCritic` already scores stability and no-evidence conditions.
- `EscapeMechanism`, `ConvergentEngine`, `OppositionEngine`, and `DialecticController` already implement the cognitive rhythm.
- The provenance model already separates observed, discovered, inferred, reinforced, and hypothetical relationships.
- The temporal-evidence layer already handles exact, approximate, relative, versioned, inferred, and unknown time.

This work package adds a product-facing API and demo that make those capabilities easy to use.

## What it does

Given a messy corpus such as deployment notes, incidents, postmortems, changelogs, policy versions, or research notes, Kosh Verify answers questions by returning:

- primary answer;
- stability score;
- temporal context;
- supporting facts;
- causal paths;
- contradiction pairs;
- inferred-not-discovered edges;
- missing-evidence questions;
- convergent summary;
- opposition findings.

## The product workflow

```text
Upload / ingest corpus
        ↓
Store temporal facts and causal/provenance edges
        ↓
Run KoshVerify.verify(question)
        ↓
Non-convergent path bundle
        ↓
Convergent compression
        ↓
Opposition attack
        ↓
Re-opened reasoning where needed
        ↓
Verified report with provenance
```

## What it can do without an LLM

The current implementation can already do the following deterministically:

- store facts and edges;
- validate edge source/target existence;
- preserve temporal validity windows;
- traverse causal paths;
- surface contradictions;
- mark inferred/compressed shortcuts;
- abstain when no evidence exists;
- run the dialectic loop;
- export a machine-readable verification report.

## What an LLM adds later

The LLM should not be the source of truth. It should act as a worker for:

- extracting candidate facts from raw documents;
- proposing candidate edges;
- summarising path bundles;
- generating human-readable reports;
- proposing missing-evidence tasks;
- writing implementation plans.

The Kosh layer then checks, labels, stores, opposes, and verifies those proposals.

## Silicon Valley demo wedge

The clearest demo is **incident/root-cause verification**:

> “Why did checkout fail?”

Kosh Verify should return:

- primary mechanistic path: deployment → memory leak → saturation → outage;
- alternative path: traffic spike → saturation → outage;
- contradiction: status update denied memory pressure;
- inferred shortcut: deployment → outage, labelled inferred/compressed;
- missing evidence: heap profile window;
- opposition finding: do not treat shortcut as discovered truth.

This is the five-minute demo that shows why this is not ordinary RAG.

## Public API

```python
from llm_kosh.verify import KoshVerify

kv = KoshVerify("./cartridge")
report = kv.verify(
    "Why did checkout fail?",
    temporal_context="2026-05-01T13:30:00+00:00",
    dialectic=True,
)
print(report.to_json(indent=2))
```

## Next product build

1. Add visual timeline/path explorer.
2. Add importers for incident markdown, changelogs, and postmortems.
3. Add MCP tool `kosh_verify`.
4. Add LangGraph/CrewAI adapter.
5. Add hosted local demo script.
6. Add official benchmark adapters.
7. Add Rust kernel path for million-node runtime.
