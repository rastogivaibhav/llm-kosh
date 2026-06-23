# Kosh Verify 100-User Framework-Agent Stress Test Report

Generated at: `2026-06-09T22:12:34.112163+00:00`

## Scenario

This sustained test simulates 100 independent users/transactions interacting with three framework-style Kosh agents:

- LangGraph-style workflow/state agent
- CrewAI-style RCA/role agent
- Salesforce-style customer/case agent

Each user has local agent cartridges, a transaction-scoped shared memory pool, and a user-scoped shared memory pool.
The test validates local work, publish-to-pool, pull-from-pool, provenance-marked shared memory, and scoped user memory.

## Summary

- Users simulated: **100**
- Users completed: **100**
- Users passed all validations: **100**
- Users failed: **0**
- Rounds per user: **3**
- Agent work actions: **300**
- Publish/pull receipts: **1100**
- Verify reports observed: **1000**
- Total wall time: **14.572s**
- Throughput: **6.86 users/s**

## Latency per user

- p50: **1.438s**
- p90: **1.538s**
- p95: **1.550s**
- max: **1.601s**

## Validation checks

- `local_agents_non_abstain`: 100/100 users
- `no_abstain_after_memory_share`: 100/100 users
- `publish_pull_receipts_created`: 100/100 users
- `salesforce_pulled_other_agents_memory`: 100/100 users
- `transaction_pool_has_all_frameworks`: 100/100 users
- `transaction_pool_has_business_ids`: 100/100 users
- `user_pool_is_scoped`: 100/100 users

## Interpretation

This test does not prove production-scale readiness. It proves the current Python prototype can sustain a 100-user, multi-agent memory-sharing simulation without an LLM dependency, while preserving transaction/user scoped memory behaviour.

The next level of stress testing should add real concurrent service processes, durable locking, ACLs, PII redaction, queue-based ingestion, and external framework adapters.
