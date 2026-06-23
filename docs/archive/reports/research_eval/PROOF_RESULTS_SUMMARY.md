# Proof Results Summary

## Test run

- Reasoning/provenance/research-eval tests: `77 passed in 6.18s`.
- Core non-MCP tests: `44 passed in 2.17s`.
- Multidomain held-out benchmark: 60 tasks across 9 domains.

## Headline comparative result

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

## Narrow claim supported

On this held-out synthetic benchmark, TheHypoKosh outperforms deterministic proxy baselines on temporal-causal-provenance reasoning and its own ablation study shows that path bundles, provenance, temporal filtering, hyperedge semantics, contradiction handling, and no-evidence abstention contribute measurable value.

## Claim not supported yet

This does not prove AGI and does not prove universal superiority over official published implementations. The next research step is to run the external baseline adapter plan.
