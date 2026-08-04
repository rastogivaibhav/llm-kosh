# TheHypoKosh Ablation Study v1

Tasks: **60**

## Average score

| Variant | Score |
|---|---:|
| full_system | 0.9610 |
| no_provenance | 0.9173 |
| no_no_evidence_abstention | 0.8944 |
| no_hyperedge_semantics | 0.8855 |
| no_contradiction_edges | 0.8710 |
| no_temporal_filter | 0.8610 |
| no_path_bundle | 0.6808 |

## By capability

### temporal_supersession
| Variant | Score |
|---|---:|
| full_system | 0.8750 |
| no_path_bundle | 0.8750 |
| no_provenance | 0.8750 |
| no_hyperedge_semantics | 0.8750 |
| no_no_evidence_abstention | 0.8750 |
| no_contradiction_edges | 0.8750 |
| no_temporal_filter | 0.5000 |

### causal_chain
| Variant | Score |
|---|---:|
| full_system | 1.0000 |
| no_temporal_filter | 1.0000 |
| no_provenance | 1.0000 |
| no_hyperedge_semantics | 1.0000 |
| no_no_evidence_abstention | 1.0000 |
| no_contradiction_edges | 1.0000 |
| no_path_bundle | 0.7188 |

### contradiction_preservation
| Variant | Score |
|---|---:|
| full_system | 1.0000 |
| no_temporal_filter | 1.0000 |
| no_provenance | 1.0000 |
| no_hyperedge_semantics | 1.0000 |
| no_no_evidence_abstention | 1.0000 |
| no_path_bundle | 0.6094 |
| no_contradiction_edges | 0.3250 |

### alternative_hypothesis
| Variant | Score |
|---|---:|
| full_system | 1.0000 |
| no_temporal_filter | 1.0000 |
| no_provenance | 1.0000 |
| no_hyperedge_semantics | 1.0000 |
| no_no_evidence_abstention | 1.0000 |
| no_contradiction_edges | 1.0000 |
| no_path_bundle | 0.9375 |

### inferred_vs_discovered
| Variant | Score |
|---|---:|
| full_system | 0.9578 |
| no_temporal_filter | 0.9578 |
| no_hyperedge_semantics | 0.9578 |
| no_no_evidence_abstention | 0.9578 |
| no_contradiction_edges | 0.9578 |
| no_provenance | 0.6297 |
| no_path_bundle | 0.4672 |

### joint_causality_hyperedge
| Variant | Score |
|---|---:|
| full_system | 1.0000 |
| no_temporal_filter | 1.0000 |
| no_provenance | 1.0000 |
| no_no_evidence_abstention | 1.0000 |
| no_contradiction_edges | 1.0000 |
| no_path_bundle | 0.6229 |
| no_hyperedge_semantics | 0.4333 |

### no_evidence_abstention
| Variant | Score |
|---|---:|
| full_system | 1.0000 |
| no_temporal_filter | 1.0000 |
| no_provenance | 1.0000 |
| no_hyperedge_semantics | 1.0000 |
| no_contradiction_edges | 1.0000 |
| no_path_bundle | 0.0000 |
| no_no_evidence_abstention | 0.0000 |
