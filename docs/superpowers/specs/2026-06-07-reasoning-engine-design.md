# Reasoning Engine Design
**Date:** 2026-06-07
**Branch:** TheHypoKosh
**Status:** Approved for implementation

---

## 1. Problem Statement

Current LLM memory and retrieval systems have three foundational failures:

1. **Cosine similarity is the wrong metric.** It finds the closest correlation and locks in — "darkness under the lamp." Semantically similar facts that are causally irrelevant rank above causally critical facts that don't resemble the query.

2. **Temporal provenance is collapsed.** When a fact was ingested and when it was originally true are the same timestamp in every existing system. This destroys temporal inference chains — you cannot detect when new facts supersede old ones, or reason about what was known at a given moment in time.

3. **Retrieval produces a single path.** All alternatives are collapsed into one ranked list. There is no mechanism for an agent to see that multiple valid causal interpretations exist, or to escape a coherent-but-wrong narrative.

The result: agents get fast wrong answers at scale.

The answer is not more compute. It is a different memory architecture — one that preserves causal structure, temporal provenance, and multiple valid paths simultaneously.

---

## 2. What We Are Building

A new subpackage `llm_kosh/engine/reasoning/` — an intelligence layer that sits above the existing llm-kosh data layer. It is an extension, not a replacement. The existing FTS, vector index, and tensor_fusion pipeline are unchanged and continue serving existing functionality.

This layer implements a **Temporal Causal Hypergraph** — a new class of memory structure with five algorithmic components:

1. **CausalDAG** — the hypergraph manager
2. **CausalRetrieval** — resonance-based retrieval replacing cosine similarity
3. **FiberBundle** — path preservation replacing single ranked lists
4. **LyapunovCritic** — stability checker for reasoning trajectories
5. **EscapeMechanism** — coherence-break for locked reasoning paths

Exposed via Python library (`ReasoningEngine`) and four new MCP tools on the existing MCP server.

**Target scale:** Agent-level. A single or small multi-agent system with a bounded memory cartridge. Architecture is designed so the path to distributed/AGI-scale is evolutionary, not a rewrite.

---

## 3. Mathematical Foundations

### 3.1 Temporal Memory Element
Every fact is:
```
M = (v, t_ingested, t_documented, [t_valid_from, t_valid_until], confidence)
```
Not a vector in ℝⁿ. A node in a temporally-ordered causal graph.

### 3.2 Causal Structure
Retrieval is over a DAG with do-calculus semantics, not correlation:
```
P(F_j | do(F_i))   not   P(F_j | F_i observed)
```
Edges carry: type, confidence, and their own validity interval.

### 3.3 Resonance Retrieval
Query decomposed into frequency components via Discrete Cosine Transform (DCT) applied to the TF-IDF term weight vector. Each fact stores a DCT-based resonance profile built at ingestion time using the same IDF vocabulary as the existing llm-kosh TF-IDF index. Matching computes dot product between query DCT coefficients and fact DCT coefficients — separately per frequency band (low, mid, high). A fact that resonates across multiple frequency bands ranks higher than a fact that scores high at only one band. This is what replaces cosine similarity: multi-scale frequency agreement, not single-scale magnitude proximity.

### 3.4 Fiber Bundle
For a concept C:
```
π: P(C) → C
```
Multiple causal paths mapped to the same concept are preserved as a fiber. Never collapsed.

### 3.5 Lyapunov Stability
```
V(bundle) = w1·temporal_consistency + w2·path_diversity + w3·degeneracy - w4·contradiction_count
```
If V < threshold → instability flagged → Escape triggered.

### 3.6 Escape Distribution
```
P_eff(token_i) = α·P_greedy + (1-α)·P_exploratory
```
Applied to causal edge traversal: deliberately traverse low-confidence edges when critic flags instability.

---

## 4. Data Model

### 4.1 TemporalFact (Node)
| Field | Type | Description |
|---|---|---|
| `id` | string | Unique identifier |
| `content` | string | Raw text/knowledge |
| `ingested_at` | datetime | When it entered this system |
| `documented_at` | datetime | When it was originally true/written |
| `valid_from` | datetime | Start of validity window |
| `valid_until` | datetime \| None | End of validity window (None = still valid) |
| `confidence` | float 0–1 | Confidence in this fact |
| `resonance_profile` | dict | Frequency decomposition of content |
| `source` | string | receipt \| agent \| user \| inference |

### 4.2 CausalEdge (Binary Relationship)
| Field | Type | Description |
|---|---|---|
| `id` | string | Unique identifier |
| `source_id` | string | Fact that causes/enables |
| `target_id` | string | Fact that is caused/enabled |
| `edge_type` | enum | ENABLES \| CAUSES \| CONTRADICTS \| SUPERSEDES \| INFERS |
| `confidence` | float 0–1 | Confidence in this causal claim |
| `valid_from` | datetime | |
| `valid_until` | datetime \| None | |
| `established_by` | string | Agent/session that created this edge |

### 4.3 HyperEdge (N-ary Relationship)
| Field | Type | Description |
|---|---|---|
| `id` | string | |
| `source_ids` | set[string] | Facts that jointly cause/enable (A ∧ B ∧ C) |
| `target_id` | string | Resulting fact |
| `edge_type` | enum | Same as CausalEdge |
| `confidence` | float 0–1 | |
| `valid_from` | datetime | |
| `valid_until` | datetime \| None | |

### 4.4 TrajectoryState (Ephemeral — Session Only)
| Field | Type | Description |
|---|---|---|
| `session_id` | string | |
| `steps` | list | Ordered list of (facts_accessed, path_taken, critic_score) |
| `current_bundle` | FiberBundle | Active path bundle |
| `stability` | float | Current Lyapunov score V |
| `escape_count` | int | Times escape triggered this session |

TrajectoryState is never written to the log. A `trajectory.completed` summary event is optionally written at session end.

---

## 5. Storage Architecture

### 5.1 Three Tiers

**Hot (in-memory):** The live Temporal Causal Hypergraph. Built from the log on startup. All queries run against this. Lives in RAM for session duration.

**Warm (JSONL event log):** Append-only source of truth. Every mutation is an immutable event. Human-readable. Git-friendly.

**Cold (snapshots):** Periodic serialized snapshots of the hot layer. Avoids full log replay on startup. Treated as a cache — discarded and rebuilt from log if corrupt.

### 5.2 Event Log Location
```
<cartridge_root>/
  ledger/
    events.jsonl        ← existing llm-kosh ledger, unchanged
  reasoning/
    events.jsonl        ← reasoning layer event log (NEW)
    snapshot.json       ← hot layer snapshot (NEW)
```

### 5.3 Event Types Written to Log
```
fact.added            content, ingested_at, documented_at, valid_from, valid_until, confidence, source
causal_edge.added     source_id, target_id, edge_type, confidence, valid_from, valid_until, established_by
hyperedge.added       source_ids, target_id, edge_type, confidence, valid_from, valid_until
fact.superseded       old_id, new_id
validity.updated      fact_id, new_valid_until
trajectory.completed  session_id, step_count, final_stability, escape_count (summary only)
```

### 5.4 Hot Layer Structure
- `nodes`: `dict[fact_id → TemporalFact]`
- `edges`: `dict[fact_id → list[CausalEdge]]` (adjacency list)
- `hyperedges`: `list[HyperEdge]`
- `interval_tree`: temporal index for fast valid-at-T queries — pure Python bisect-based implementation, zero new dependencies
- `resonance_index`: `dict[fact_id → resonance_profile]`

---

## 6. The Five Components

### 6.1 CausalDAG
**One job:** Owns the hot layer. The only component that reads/writes the log.

- Loads all events from `reasoning/events.jsonl` on init
- Imports existing llm-kosh memories from the existing SQLite index as TemporalFacts (using `created` as baseline for `ingested_at`/`documented_at`)
- Imports existing ReceiptDAG supersession chains as `SUPERSEDES` edges
- Answers graph queries: ancestors, descendants, valid-at-T, supersession chains
- All other components read through CausalDAG — none touch the log directly

### 6.2 CausalRetrieval
**One job:** Query → causally-anchored candidate set with temporal filtering.

Pipeline:
1. Decompose query into resonance profile (frequency decomposition)
2. Harmonic match against `resonance_index` → anchor facts
3. Apply temporal filter via interval tree: exclude facts invalid at `query_time`
4. Walk causal edges outward from anchors (BFS, max `depth` hops)
5. Score each candidate: `resonance_strength + (1/causal_distance) + temporal_consistency + validity_weight`

Returns: `list[(TemporalFact, causal_distance, score)]` — not a flat ranked list, but structured with distance.

### 6.3 FiberBundle
**One job:** Candidate set → full path bundle preserving all valid derivation paths.

- Enumerate all valid causal paths from anchor facts to each candidate (up to `depth`)
- Group by target fact: each target gets a fiber = set of paths reaching it
- Per path: record edge sequence, confidence product, temporal consistency score
- Per target: compute degeneracy (count of independent paths)
- Return: `dict[fact_id → Fiber]` where `Fiber = {fact, paths, degeneracy, max_confidence}`

Never collapses. The bundle is the output.

### 6.4 LyapunovCritic
**One job:** FiberBundle → stability score + diagnosis.

Computes V across four dimensions:
- **Temporal consistency** (0–1): fraction of edges in all paths that respect causal time ordering
- **Contradiction score** (0–1, inverted): fraction of fact pairs with active CONTRADICTS edges
- **Path diversity** (0–1): normalized count of independent paths across the bundle
- **Degeneracy** (0–1): fraction of high-confidence facts reachable via 2+ independent routes

```
V = w1·temporal_consistency + w2·path_diversity + w3·degeneracy - w4·contradiction_score
```

Default weights: `w1=0.35, w2=0.25, w3=0.25, w4=0.15` — configurable via `LLM_KOSH.json` under `reasoning_weights.lyapunov` key, same pattern as existing `retrieval_weights`.

Returns: `{score: float, status: stable|marginal|unstable, dimensions: {...}, implicated_facts: [...]}`

Thresholds: stable ≥ 0.7, marginal 0.4–0.7, unstable < 0.4 — also configurable via `reasoning_weights.stability_thresholds`.

### 6.5 EscapeMechanism
**One job:** Targeted exploration based on critic diagnosis. Acts only when critic returns `unstable` or `marginal`.

- **Temporal inconsistency diagnosis:** surface facts from the correct temporal window excluded by the original temporal filter (slightly widen the validity window)
- **Contradiction diagnosis:** surface both sides of the contradiction explicitly with their validity intervals
- **Low path diversity diagnosis:** traverse low-confidence edges (confidence < 0.4) deliberately — edges excluded by normal retrieval scoring
- **Low degeneracy diagnosis:** search alternative causal routes to high-confidence target facts

Adds escaped facts and paths to the bundle. Re-runs the critic. Increments `escape_count` in TrajectoryState.

If escape_count > 3 on the same bundle: flag the bundle with `deep_instability` — signals a structural problem in the causal graph itself, not just a retrieval issue.

---

## 7. Component Composition

```
Agent query (text, temporal_context, depth)
    │
    ▼
CausalRetrieval.retrieve(query, temporal_context, depth)
    │  → candidate set with causal distances
    ▼
FiberBundle.build(candidates, anchor_facts)
    │  → full path bundle
    ▼
LyapunovCritic.evaluate(bundle)
    │  → stability score + diagnosis
    │
    ├─ stable/marginal → return bundle
    │
    └─ unstable ──────────────────────┐
                                      ▼
                         EscapeMechanism.escape(bundle, diagnosis)
                                      │  → enriched bundle
                                      ▼
                         LyapunovCritic.evaluate(enriched_bundle)
                                      │  → final stability
                                      ▼
                                 return bundle

CausalDAG underlies all components (hot layer access)
```

---

## 8. Python API

```
ReasoningEngine(root: Path)
    Initialize against cartridge root.
    Loads log, builds hot layer. Ready immediately.

engine.query(query: str, temporal_context: str | datetime | None, depth: int = 3) → QueryResult
    Full pipeline. All five components.
    Returns QueryResult with bundle, stability, and escape metadata.

engine.ingest(content: str, documented_at: datetime, valid_from: datetime,
              valid_until: datetime | None, confidence: float,
              causal_edges: list[dict]) → str
    Add a new fact. Optionally link to existing facts via causal edges.
    Returns new fact_id.

engine.critique(fact_ids: list[str]) → StabilityResult
    Run Lyapunov critic on a specific set of facts.
    Returns stability score and dimension breakdown.

engine.explore(from_fact_id: str, to_fact_id: str, max_hops: int = 5) → FiberBundle
    Enumerate all causal paths between two known facts.
```

---

## 9. MCP Tools

Four tools added to the existing `llm-kosh mcp-server`. No new server process.

### `reasoning_query`
- **Input:** `query` (string), `temporal_context` (ISO 8601 datetime string or Unix timestamp; natural language not supported in v1), `depth` (int, default 3)
- **Output:** Full QueryResult — anchors, fiber bundle, stability score, escape metadata

### `reasoning_ingest`
- **Input:** `content`, `documented_at`, `valid_from`, `valid_until`, `confidence`, `causal_edges`
- **Output:** `fact_id`, confirmation

### `reasoning_critique`
- **Input:** `fact_ids` (list of IDs the agent is currently reasoning over)
- **Output:** Stability score, dimension breakdown, implicated facts

### `reasoning_explore`
- **Input:** `from_fact_id`, `to_fact_id`, `max_hops` (default 5)
- **Output:** All valid causal paths with edge sequences and confidence products

### Output Schema for `reasoning_query`
```json
{
  "anchors": ["fact_id_1", "fact_id_2"],
  "bundle": {
    "<fact_id>": {
      "fact": { "id": "...", "content": "...", "valid_from": "...", "valid_until": "..." },
      "paths": [
        { "edges": [...], "confidence_product": 0.72, "temporal_consistency": 1.0 }
      ],
      "degeneracy": 3,
      "max_confidence": 0.87
    }
  },
  "stability": {
    "score": 0.74,
    "status": "marginal",
    "dimensions": {
      "temporal_consistency": 0.91,
      "contradiction_score": 0.05,
      "path_diversity": 0.61,
      "degeneracy": 0.58
    },
    "escape_triggered": true,
    "escape_surfaced": ["fact_id_7", "fact_id_12"]
  }
}
```

---

## 10. Integration with Existing llm-kosh

### What Changes
- New directory: `llm_kosh/engine/reasoning/`
- New directory: `<cartridge_root>/reasoning/`
- Four new MCP tools registered in the existing server
- One optional daemon background job (causal edge inference)

### What Does Not Change
- `search.py` — unchanged
- `tensor_fusion.py` — unchanged
- `receipt_dag.py` — unchanged
- `math_fallback.py` — unchanged
- `ledger/events.jsonl` — unchanged
- All existing CLI commands — unchanged
- All existing MCP tools — unchanged

### Daemon Integration
One optional background job added to the daemon loop: **causal edge inference**. Examines pairs of existing memories and infers probable causal edges based on temporal ordering, shared project, and content overlap. Inferred edges get `confidence < 0.5` and `edge_type = INFERS`. Clearly marked as machine-inferred. Agents can include or exclude `INFERS` edges per query.

---

## 11. File Structure

```
llm_kosh/
  engine/
    reasoning/
      __init__.py          ReasoningEngine, QueryResult, StabilityResult
      causal_dag.py        CausalDAG, TemporalFact, CausalEdge, HyperEdge
      causal_retrieval.py  CausalRetrieval, resonance_profile()
      fiber_bundle.py      FiberBundle, Fiber, Path
      lyapunov_critic.py   LyapunovCritic, StabilityResult
      escape.py            EscapeMechanism

<cartridge_root>/
  reasoning/
    events.jsonl
    snapshot.json
```

---

## 12. Scale Boundary

This design targets **agent scale**: single or small multi-agent systems, bounded memory cartridge, hundreds of thousands of facts.

Architectural decisions made to preserve the path to larger scale:
- Event log interface is swappable (JSONL now, distributed stream later)
- Hypergraph has explicit partition boundaries (one partition now)
- Resonance index has pluggable backend (local FFT now, distributed ANN later)
- Critic takes a scope parameter (session scope now, global scope later)

AGI-scale requires: distributed sharded hypergraph, partitioned event streams, federated multi-agent graph, continuous online graph restructuring, hierarchical abstraction layers. Out of scope for this version — but the architecture does not close those doors.
