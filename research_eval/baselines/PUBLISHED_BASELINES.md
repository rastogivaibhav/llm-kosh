# Published Baseline Families Used for Comparison

The internal benchmark includes deterministic proxy baselines inspired by these published baseline families:

1. **RAG** — retrieval-augmented generation with external non-parametric memory.
2. **GraphRAG** — graph-based retrieval over entity/community structures for corpus reasoning.
3. **Self-RAG** — adaptive retrieval plus self-reflection/critique.
4. **ReAct** — interleaved reasoning and acting/tool use.
5. **Agent-memory systems** — long-lived memory stores with recency/salience weighting.

## Why proxy baselines are included

The benchmark needs to be runnable without cloud APIs, external model downloads, or unpinned dependencies. Therefore, the default runners implement deterministic proxy versions of these families.

## How to make the result publishable

For external publication, replace each proxy with an adapter that runs a pinned implementation:

```text
external_baselines/
  graphrag_adapter.py
  selfrag_adapter.py
  react_adapter.py
  rag_adapter.py
```

Each adapter should emit a JSONL file with:

```json
{"id":"task_id", "answer":"...", "evidence_keys":["..."], "metadata":{}}
```

Then score using the same private ground truth.
