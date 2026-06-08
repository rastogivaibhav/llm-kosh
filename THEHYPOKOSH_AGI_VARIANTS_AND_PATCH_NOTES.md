# TheHypoKosh / LLM-Kosh Provenance Layer Patch

## Why this matters

This patch moves LLM-Kosh's Temporal Causal Reasoning Engine from a useful temporal-causal memory system toward a stronger AGI-adjacent reasoning substrate. It does **not** make the system AGI and it does **not** replace transformers. It adds epistemic discipline around memory and reasoning.

The important new principle is:

> Inference is allowed. Reinforcement is allowed. Speculation is allowed. But none of them may silently become discovered truth.

This creates the basis for multiple system variants:

- **Empirical scientist mode:** conservative, evidence-first, useful for enterprise, safety, compliance, postmortems, medicine/legal support.
- **Theoretical physicist mode:** exploratory, analogy-heavy, useful for invention, scientific ideation and non-convergent reasoning.
- **Balanced mode:** shows supported answers and speculative alternatives separately.

These variants have potential as the memory-reasoning substrate of a new class of AI systems. They are not a new foundation model by themselves, but they can support a new model family where the LLM is the generative engine and TheHypoKosh is the durable memory, provenance, doubt, discovery and self-correction substrate.

## Layers added

### 1. Edge provenance

Added to `llm_kosh/engine/reasoning/causal_dag.py`:

- `EdgeOrigin`
  - `OBSERVED`
  - `DISCOVERED`
  - `INFERRED`
  - `REINFORCED`
  - `HYPOTHETICAL`
- `EdgeRole`
  - `MECHANISTIC`
  - `COMPRESSED`
  - `ANALOGICAL`
  - `PREDICTIVE`
  - `CAUSAL`
- `EvidenceRef`
- `ReinforcementState`
- `EdgeProvenance`

Every `CausalEdge` and `HyperEdge` can now carry explicit epistemic identity.

### 2. Promotion and reinforcement rules

Added methods:

- `CausalDAG.reinforce_edge(...)`
- `CausalDAG.promote_edge_to_discovered(...)`
- `CausalDAG.demote_edge(...)`
- `ReasoningEngine.reinforce_edge(...)`
- `ReasoningEngine.promote_edge_to_discovered(...)`

Important behaviour:

- Repeated use increases salience/reinforcement state.
- Repeated use does **not** automatically increase truth confidence.
- Promotion to `DISCOVERED` requires explicit `EvidenceRef`.

### 3. No-evidence / abstain state

`LyapunovCritic` no longer treats an empty bundle as stable.

Empty evidence now returns:

```text
status = "no_evidence"
abstain = true
score = 0.0
```

This prevents the system from treating absence of retrieved memory as stable reasoning.

### 4. Pattern lock metric

`LyapunovCritic` now includes `pattern_lock_score`. Single-path reasoning is not automatically wrong, but the critic can penalise overly narrow reasoning trajectories.

### 5. Hyperedge traversal

Hyperedges now behave closer to joint causality:

```text
A ∧ B -> C
```

The synthetic traversal edge only fires when all source facts are active in the current traversal path/context.

### 6. Path deduplication

`FiberBundle` now deduplicates paths by edge identity and keeps the strongest variant. This prevents duplicate path pollution from inflating degeneracy.

### 7. Reasoning modes

Added `ReasoningMode`:

- `EMPIRICAL`
- `THEORETICAL`
- `BALANCED`

`ReasoningEngine.query(..., reasoning_mode="EMPIRICAL")` applies a conservative filter to ungrounded analogical/hypothetical paths.

## Tests added / updated

Added:

```text
tests/test_reasoning_provenance_layers.py
```

Coverage includes:

- invalid edge source/target rejection
- inferred shortcut reinforcement without discovery promotion
- promotion requiring evidence
- empty-bundle abstention
- hyperedge all-source semantics
- empirical mode filtering of ungrounded analogy

## Local test results in this environment

Targeted reasoning/provenance suite:

```text
71 passed
```

Core non-MCP suite:

```text
14 passed
```

MCP tests were not run because the sandbox does not have the optional `mcp` dependency installed.

## What this still does not solve

- It does not train a new neural foundation model.
- It does not prove AGI.
- It does not yet include external evidence adapters.
- It does not yet include full benchmark baselines against GraphRAG/Self-RAG/ReAct.
- Theoretical mode is still a policy scaffold; deeper scoring policy can be added next.

## Recommended next step

Create a canonical benchmark release with:

- ordinary retrieval baseline
- graph retrieval baseline
- TheHypoKosh balanced mode
- TheHypoKosh empirical mode
- TheHypoKosh theoretical mode
- ablation without provenance
- ablation without FiberBundle
- ablation without pattern-lock penalty
- false-promotion rate as a headline metric
