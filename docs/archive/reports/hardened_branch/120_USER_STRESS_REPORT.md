# Kosh Verify 100-User Framework-Agent Stress Test Report

Generated at: `2026-06-09T22:14:36.629444+00:00`

## Scenario

This sustained test simulates 100 independent users/transactions interacting with three framework-style Kosh agents:

- LangGraph-style workflow/state agent
- CrewAI-style RCA/role agent
- Salesforce-style customer/case agent

Each user has local agent cartridges, a transaction-scoped shared memory pool, and a user-scoped shared memory pool.
The test validates local work, publish-to-pool, pull-from-pool, provenance-marked shared memory, and scoped user memory.

## Summary

- Users simulated: **120**
- Users completed: **120**
- Users passed all validations: **120**
- Users failed: **0**
- Rounds per user: **3**
- Agent work actions: **360**
- Publish/pull receipts: **1320**
- Verify reports observed: **1200**
- Total wall time: **18.276s**
- Throughput: **6.57 users/s**

## Latency per user

- p50: **1.818s**
- p90: **1.892s**
- p95: **1.926s**
- max: **1.978s**

## Validation checks

- `local_agents_non_abstain`: 120/120 users
- `no_abstain_after_memory_share`: 120/120 users
- `publish_pull_receipts_created`: 120/120 users
- `salesforce_pulled_other_agents_memory`: 120/120 users
- `transaction_pool_has_all_frameworks`: 120/120 users
- `transaction_pool_has_business_ids`: 120/120 users
- `user_pool_is_scoped`: 120/120 users

## Interpretation

This test does not prove production-scale readiness. It proves the current Python prototype can sustain a 100-user, multi-agent memory-sharing simulation without an LLM dependency, while preserving transaction/user scoped memory behaviour.

The next level of stress testing should add real concurrent service processes, durable locking, ACLs, PII redaction, queue-based ingestion, and external framework adapters.
