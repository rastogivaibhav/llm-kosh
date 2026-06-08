# TheHypoKosh Research-Grade Evaluation Pack v1

## What was added

- Larger held-out multidomain benchmark: 60 tasks across incidents, policy, medical guidelines, science, software architecture, education, finance/regulatory, legal/compliance, and out-of-corpus probes.
- Blind question file and private ground-truth file with SHA-256 hashes.
- Published-baseline-inspired deterministic proxy baselines: KeywordRAG, TemporalRAG, AgentMemory, GraphRAG, Self-RAG, and ReAct.
- Ablation variants removing temporal filtering, path bundles, provenance, hyperedge semantics, no-evidence abstention, and contradiction edges.

## Headline benchmark result

| System | Average score |
|---|---:|
| TheHypoKosh | 0.9610 |
| AgentMemory_proxy | 0.7600 |
| SelfRAG_proxy | 0.7600 |
| TemporalRAG_proxy | 0.7600 |
| GraphRAG_proxy | 0.7281 |
| KeywordRAG_proxy | 0.7267 |
| ReAct_proxy | 0.7017 |

## Headline ablation result

| Variant | Average score |
|---|---:|
| full_system | 0.9610 |
| no_provenance | 0.9173 |
| no_no_evidence_abstention | 0.8944 |
| no_hyperedge_semantics | 0.8855 |
| no_contradiction_edges | 0.8710 |
| no_temporal_filter | 0.8610 |
| no_path_bundle | 0.6808 |

## Claim supported by this evaluation

This pack supports a controlled claim: on this held-out temporal-causal-provenance benchmark, TheHypoKosh preserves temporal truth, causal chains, contradiction, inference/discovery provenance, joint-causality hyperedges, and no-evidence abstention better than deterministic proxy baselines.

## Claim not yet supported

This does not prove AGI and does not prove universal superiority over every official implementation of GraphRAG, Self-RAG, ReAct, or commercial agent-memory systems. To make that claim, run the adapter interface against official implementations and publish environment, prompts, model IDs, latency, cost, and full output logs.