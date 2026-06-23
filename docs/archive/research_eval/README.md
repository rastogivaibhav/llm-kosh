# TheHypoKosh Research Evaluation Pack v1

This pack converts the earlier proof-of-concept benchmark into a stronger internal evaluation harness.

It includes:

- larger held-out multidomain benchmark data;
- blind questions and private ground truth;
- deterministic proxy baselines inspired by published RAG, GraphRAG, Self-RAG, ReAct, and agent-memory patterns;
- ablation variants for temporal filtering, path bundles, provenance, hyperedges, abstention, and contradiction edges;
- machine-readable JSON reports and markdown summaries.

## Run

```bash
python3 research_eval/scripts/run_multidomain_evaluation.py
```

Outputs are written to:

```text
reports/research_eval/
research_eval/data/
```

## Important limitation

The baseline runners are deterministic proxy baselines, not the official authors' implementations. They are useful for internal proof discipline and ablation reasoning. A publishable external claim requires running official or well-recognised implementations under the same dataset, model, prompt, and budget constraints.
