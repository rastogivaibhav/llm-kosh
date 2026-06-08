# TheHypoKosh Comparative Benchmark v0

This is a deterministic, synthetic benchmark over temporal-causal-provenance tasks. It compares representative baselines, not all published implementations.

## Average scores

| System | Avg score |
|---|---:|
| TheHypoKosh | 1.000 |
| TemporalRAG | 0.938 |
| AgentMemory | 0.938 |
| GraphRAG | 0.938 |
| SelfRAG_like | 0.938 |
| ReAct_like | 0.938 |
| KeywordRAG | 0.875 |

## Feature checks

- provenance_inferred_compressed: 1/1
- mechanistic_chain_preserved: 1/1
- hyperedge_joint_sources: 1/1
- no_evidence_abstain: 1/1

## Per task

### temporal_feb
Expected: `['remote_old']`
- KeywordRAG: score=0.75 found=['remote_new', 'remote_old']
- TemporalRAG: score=1.0 found=['remote_old']
- AgentMemory: score=1.0 found=['remote_old']
- GraphRAG: score=1.0 found=['mitigation_expired', 'outage', 'remote_old']
- SelfRAG_like: score=1.0 found=['remote_old']
- ReAct_like: score=1.0 found=['mitigation_expired', 'outage', 'remote_old']
- TheHypoKosh: score=1.0 found=['remote_old']

### temporal_may
Expected: `['remote_new']`
- KeywordRAG: score=0.75 found=['remote_new', 'remote_old', 'traffic']
- TemporalRAG: score=1.0 found=['remote_new', 'traffic']
- AgentMemory: score=1.0 found=['remote_new', 'traffic']
- GraphRAG: score=1.0 found=['heap', 'mitigation_expired', 'outage', 'remote_new', 'traffic']
- SelfRAG_like: score=1.0 found=['remote_new', 'traffic']
- ReAct_like: score=1.0 found=['heap', 'mitigation_expired', 'outage', 'remote_new', 'traffic']
- TheHypoKosh: score=1.0 found=['heap', 'outage', 'remote_new', 'traffic']

### root_cause_primary
Expected: `['deployment', 'leak', 'heap', 'outage']`
- KeywordRAG: score=1.0 found=['deployment', 'heap', 'leak', 'outage', 'status_contradiction']
- TemporalRAG: score=1.0 found=['deployment', 'heap', 'leak', 'outage', 'status_contradiction']
- AgentMemory: score=1.0 found=['deployment', 'heap', 'leak', 'outage', 'status_contradiction']
- GraphRAG: score=1.0 found=['deployment', 'heap', 'leak', 'mitigation_expired', 'outage']
- SelfRAG_like: score=1.0 found=['deployment', 'heap', 'leak', 'outage', 'status_contradiction', 'traffic']
- ReAct_like: score=0.75 found=['heap', 'leak', 'mitigation_expired', 'outage', 'status_contradiction']
- TheHypoKosh: score=1.0 found=['deployment', 'heap', 'leak', 'outage', 'status_contradiction', 'traffic']

### contradiction
Expected: `['status_contradiction', 'heap']`
- KeywordRAG: score=1.0 found=['heap', 'leak', 'outage', 'status_contradiction', 'traffic']
- TemporalRAG: score=1.0 found=['heap', 'leak', 'outage', 'status_contradiction', 'traffic']
- AgentMemory: score=1.0 found=['heap', 'leak', 'outage', 'status_contradiction', 'traffic']
- GraphRAG: score=0.5 found=['heap', 'leak', 'mitigation_expired', 'outage']
- SelfRAG_like: score=1.0 found=['deployment', 'heap', 'leak', 'outage', 'status_contradiction', 'traffic']
- ReAct_like: score=1.0 found=['heap', 'leak', 'mitigation_expired', 'outage', 'status_contradiction']
- TheHypoKosh: score=1.0 found=['deployment', 'heap', 'leak', 'outage', 'status_contradiction', 'traffic']

### alternative_path
Expected: `['traffic', 'heap', 'outage']`
- KeywordRAG: score=1.0 found=['heap', 'leak', 'outage', 'status_contradiction', 'traffic']
- TemporalRAG: score=1.0 found=['heap', 'leak', 'outage', 'status_contradiction', 'traffic']
- AgentMemory: score=1.0 found=['heap', 'leak', 'outage', 'status_contradiction', 'traffic']
- GraphRAG: score=1.0 found=['heap', 'mitigation_expired', 'outage', 'traffic']
- SelfRAG_like: score=1.0 found=['deployment', 'heap', 'leak', 'outage', 'status_contradiction', 'traffic']
- ReAct_like: score=1.0 found=['heap', 'mitigation_expired', 'outage', 'status_contradiction', 'traffic']
- TheHypoKosh: score=1.0 found=['heap', 'leak', 'outage', 'status_contradiction', 'traffic']

### inferred_vs_discovered
Expected: `['deployment', 'leak', 'heap', 'outage']`
- KeywordRAG: score=0.5 found=['deployment', 'mitigation_expired', 'outage']
- TemporalRAG: score=0.5 found=['deployment', 'outage']
- AgentMemory: score=0.5 found=['deployment', 'outage']
- GraphRAG: score=1.0 found=['deployment', 'heap', 'leak', 'mitigation_expired', 'outage']
- SelfRAG_like: score=0.5 found=['deployment', 'outage']
- ReAct_like: score=0.75 found=['deployment', 'leak', 'mitigation_expired', 'outage']
- TheHypoKosh: score=1.0 found=['deployment', 'heap', 'leak', 'outage']

### hyperedge_joint
Expected: `['flag', 'schema', 'checkout_fail']`
- KeywordRAG: score=1.0 found=['checkout_fail', 'flag', 'schema']
- TemporalRAG: score=1.0 found=['checkout_fail', 'flag', 'schema']
- AgentMemory: score=1.0 found=['checkout_fail', 'flag', 'schema']
- GraphRAG: score=1.0 found=['checkout_fail', 'flag', 'schema']
- SelfRAG_like: score=1.0 found=['checkout_fail', 'flag', 'schema']
- ReAct_like: score=1.0 found=['checkout_fail', 'flag', 'schema']
- TheHypoKosh: score=1.0 found=['checkout_fail', 'flag', 'schema']

### no_evidence
Expected: `[]`
- KeywordRAG: score=1.0 found=[]
- TemporalRAG: score=1.0 found=[]
- AgentMemory: score=1.0 found=[]
- GraphRAG: score=1.0 found=[]
- SelfRAG_like: score=1.0 found=[]
- ReAct_like: score=1.0 found=[]
- TheHypoKosh: score=1.0 found=[]
