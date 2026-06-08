# TheHypoKosh Multidomain Held-Out Benchmark v1

This is a controlled held-out benchmark over temporal, causal, contradiction, provenance, hyperedge, and no-evidence tasks.

**Important limitation:** the baselines here are deterministic proxy baselines inspired by published systems. They are not official runs of Microsoft GraphRAG, Self-RAG, ReAct, or any proprietary agent-memory product.

Tasks: **60**
Domains: **9**

## Average score

| System | Average score |
|---|---:|
| TheHypoKosh | 0.9610 |
| AgentMemory_proxy | 0.7600 |
| SelfRAG_proxy | 0.7600 |
| TemporalRAG_proxy | 0.7600 |
| GraphRAG_proxy | 0.7281 |
| KeywordRAG_proxy | 0.7267 |
| ReAct_proxy | 0.7017 |

## By capability

### temporal_supersession
| System | Score |
|---|---:|
| TemporalRAG_proxy | 0.8750 |
| AgentMemory_proxy | 0.8750 |
| SelfRAG_proxy | 0.8750 |
| TheHypoKosh | 0.8750 |
| GraphRAG_proxy | 0.7812 |
| KeywordRAG_proxy | 0.7500 |
| ReAct_proxy | 0.6562 |

### causal_chain
| System | Score |
|---|---:|
| KeywordRAG_proxy | 1.0000 |
| TemporalRAG_proxy | 1.0000 |
| AgentMemory_proxy | 1.0000 |
| SelfRAG_proxy | 1.0000 |
| ReAct_proxy | 1.0000 |
| TheHypoKosh | 1.0000 |
| GraphRAG_proxy | 0.9688 |

### contradiction_preservation
| System | Score |
|---|---:|
| TheHypoKosh | 1.0000 |
| KeywordRAG_proxy | 0.6500 |
| TemporalRAG_proxy | 0.6500 |
| AgentMemory_proxy | 0.6500 |
| GraphRAG_proxy | 0.6500 |
| SelfRAG_proxy | 0.6500 |
| ReAct_proxy | 0.6500 |

### alternative_hypothesis
| System | Score |
|---|---:|
| KeywordRAG_proxy | 1.0000 |
| TemporalRAG_proxy | 1.0000 |
| AgentMemory_proxy | 1.0000 |
| GraphRAG_proxy | 1.0000 |
| SelfRAG_proxy | 1.0000 |
| ReAct_proxy | 1.0000 |
| TheHypoKosh | 1.0000 |

### inferred_vs_discovered
| System | Score |
|---|---:|
| TheHypoKosh | 0.9578 |
| KeywordRAG_proxy | 0.6500 |
| TemporalRAG_proxy | 0.6500 |
| AgentMemory_proxy | 0.6500 |
| SelfRAG_proxy | 0.6500 |
| ReAct_proxy | 0.6500 |
| GraphRAG_proxy | 0.6297 |

### joint_causality_hyperedge
| System | Score |
|---|---:|
| TheHypoKosh | 1.0000 |
| KeywordRAG_proxy | 0.6500 |
| TemporalRAG_proxy | 0.6500 |
| AgentMemory_proxy | 0.6500 |
| GraphRAG_proxy | 0.6500 |
| SelfRAG_proxy | 0.6500 |
| ReAct_proxy | 0.6500 |

### no_evidence_abstention
| System | Score |
|---|---:|
| TheHypoKosh | 1.0000 |
| KeywordRAG_proxy | 0.0000 |
| TemporalRAG_proxy | 0.0000 |
| AgentMemory_proxy | 0.0000 |
| GraphRAG_proxy | 0.0000 |
| SelfRAG_proxy | 0.0000 |
| ReAct_proxy | 0.0000 |

## By domain

### education
| System | Score |
|---|---:|
| TheHypoKosh | 0.8571 |
| KeywordRAG_proxy | 0.7786 |
| TemporalRAG_proxy | 0.7071 |
| AgentMemory_proxy | 0.7071 |
| GraphRAG_proxy | 0.7071 |
| SelfRAG_proxy | 0.7071 |
| ReAct_proxy | 0.6714 |

### finance_regulatory
| System | Score |
|---|---:|
| TheHypoKosh | 1.0000 |
| TemporalRAG_proxy | 0.8500 |
| AgentMemory_proxy | 0.8500 |
| SelfRAG_proxy | 0.8500 |
| GraphRAG_proxy | 0.8143 |
| KeywordRAG_proxy | 0.7786 |
| ReAct_proxy | 0.7786 |

### incident
| System | Score |
|---|---:|
| TheHypoKosh | 1.0000 |
| TemporalRAG_proxy | 0.8500 |
| AgentMemory_proxy | 0.8500 |
| SelfRAG_proxy | 0.8500 |
| GraphRAG_proxy | 0.8143 |
| KeywordRAG_proxy | 0.7786 |
| ReAct_proxy | 0.7786 |

### legal_compliance
| System | Score |
|---|---:|
| TheHypoKosh | 1.0000 |
| TemporalRAG_proxy | 0.8500 |
| AgentMemory_proxy | 0.8500 |
| SelfRAG_proxy | 0.8500 |
| GraphRAG_proxy | 0.8143 |
| KeywordRAG_proxy | 0.7786 |
| ReAct_proxy | 0.7786 |

### medical_guideline
| System | Score |
|---|---:|
| TheHypoKosh | 0.8571 |
| KeywordRAG_proxy | 0.7786 |
| TemporalRAG_proxy | 0.7071 |
| AgentMemory_proxy | 0.7071 |
| GraphRAG_proxy | 0.7071 |
| SelfRAG_proxy | 0.7071 |
| ReAct_proxy | 0.6714 |

### out_of_corpus
| System | Score |
|---|---:|
| TheHypoKosh | 1.0000 |
| KeywordRAG_proxy | 0.0000 |
| TemporalRAG_proxy | 0.0000 |
| AgentMemory_proxy | 0.0000 |
| GraphRAG_proxy | 0.0000 |
| SelfRAG_proxy | 0.0000 |
| ReAct_proxy | 0.0000 |

### policy
| System | Score |
|---|---:|
| TheHypoKosh | 0.9518 |
| TemporalRAG_proxy | 0.8500 |
| AgentMemory_proxy | 0.8500 |
| SelfRAG_proxy | 0.8500 |
| KeywordRAG_proxy | 0.7786 |
| ReAct_proxy | 0.7786 |
| GraphRAG_proxy | 0.7554 |

### science
| System | Score |
|---|---:|
| TheHypoKosh | 1.0000 |
| TemporalRAG_proxy | 0.8500 |
| AgentMemory_proxy | 0.8500 |
| SelfRAG_proxy | 0.8500 |
| GraphRAG_proxy | 0.8143 |
| KeywordRAG_proxy | 0.7786 |
| ReAct_proxy | 0.7786 |

### software_architecture
| System | Score |
|---|---:|
| TheHypoKosh | 1.0000 |
| TemporalRAG_proxy | 0.8500 |
| AgentMemory_proxy | 0.8500 |
| SelfRAG_proxy | 0.8500 |
| GraphRAG_proxy | 0.8143 |
| KeywordRAG_proxy | 0.7786 |
| ReAct_proxy | 0.7786 |
