# External Baseline Adapter Plan

The current evaluation pack includes deterministic proxy baselines. To turn this into a publishable external-baseline study, plug in official or well-recognised implementations and write outputs to the same JSONL schema.

## Required output schema

```json
{"id":"task_id", "evidence_keys":["domain.fact_key"], "answer":"free text answer", "metadata":{"system":"GraphRAG"}}
```

## Baseline families

- RAG: dense/sparse retrieval over the same held-out corpus, followed by answer generation.
- GraphRAG: graph-based index, local/global retrieval mode, same corpus and questions.
- Self-RAG: adaptive retrieval/self-reflection model or faithful reproduction.
- ReAct: interleaved retrieval/action trajectory over the same corpus.
- Agent memory: long-term memory implementation with recency/salience scoring.

## Fairness rules

1. Same blind questions.
2. Same corpus.
3. Same model family or clearly reported model IDs.
4. Same maximum retrieved evidence budget.
5. Same scoring script.
6. Full logs retained.
7. Ground truth not exposed to baseline prompts.

## Publication rule

Do not claim superiority over official GraphRAG/Self-RAG/ReAct until these adapters have been executed. Current benchmark claims are against deterministic proxy baselines only.
