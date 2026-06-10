# Kosh Verify v1.1 Hardened Branch Report

Generated: 2026-06-09T22:17:08.785310+00:00

## Executive verdict

This branch is now a **hardened v1.1 release candidate**, not merely a concept branch. The previous integration drift was fixed and the recursive self-healing loop now coexists with the product wedge, multi-agent shared memory, temporal evidence, provenance layers, and the MCP-facing tool surface.

The honest status is:

> **Ready for controlled demos, local pilots, and serious collaborator review. Not yet ready as a production SaaS or million-node runtime.**

## What was hardened — Karpathy style

The hardening work focused on removing avoidable abstraction collisions and making the smallest coherent system pass.

### 1. Stable fact ingestion API

Problem: product/verify code called `CausalDAG.add_fact(content=...)`, while the DAG implementation expected a positional `content_or_fact`. This broke Kosh Verify, multi-agent tests, temporal-evidence tests, and recursive tests.

Fix: `add_fact()` now supports both forms:

```python
dag.add_fact(TemporalFact(...))
dag.add_fact("content", ingested_at, documented_at, valid_from, ...)
dag.add_fact(content="content", ingested_at=..., documented_at=..., valid_from=...)
```

### 2. QueryTrace namespace collision removed

Problem: `llm_kosh.engine.reasoning.__init__` imported `v1_1_tracer.QueryTrace` at module level, silently replacing the production `trace.QueryTrace`. This broke `ReasoningEngine.query_with_trace()` and the recursive loop.

Fix: v1.1 experimental exports are now explicitly prefixed: `V11QueryTrace`, `V11QueryTracer`, `V11TraceCritic`, `V11DiscoveryGenerator`, `V11RecursiveLoopEngine`. The production engine keeps using the stable `trace.QueryTrace`.

### 3. v1.1 critic taxonomy simplified

Problem: an unscored trace produced `no_stability_assessment`, while the self-healing layer expected no-evidence semantics.

Fix: unscored traces now produce `no_evidence_no_stability_assessment`, preserving the evidence-seeking path instead of creating a parallel weakness taxonomy.

### 4. MCP optional dependency fallback

Problem: full pytest collection failed when `mcp` was not installed.

Fix: added a small local `FastMCP` fallback for local tests/dev environments. Real MCP still uses the official package when installed.

## Elon-style test results

### A. Targeted regression suite

```text
.............................................................            [100%]
61 passed in 1.68s
```

Coverage included recursive self-healing, v1.1 layers, Kosh Verify product wedge, multi-agent ServiceNow memory, framework-agent shared memory, temporal evidence, provenance, no-evidence guard, dialectic/model-world, research eval, MCP adapter fallback, and MCP reasoning tools.

### B. 120-user sustained framework-agent stress

```text
Users requested: 120
Users completed: 120
Users passed: 120
Users failed: 0
Rounds per user: 3
Workers: 12
Agent work actions: 360
Publish/pull receipts: 1320
Verify reports: 1200
Facts seen in reports: 4533
Wall time: 18.276s
Throughput: 6.57 users/sec
p50 user latency: 1.818s
p95 user latency: 1.926s
```

Validation checks passed for all users:

```json
{
  "local_agents_non_abstain": 120,
  "no_abstain_after_memory_share": 120,
  "publish_pull_receipts_created": 120,
  "salesforce_pulled_other_agents_memory": 120,
  "transaction_pool_has_all_frameworks": 120,
  "transaction_pool_has_business_ids": 120,
  "user_pool_is_scoped": 120
}
```

### C. Real ITSM temporal-causal/provenance dataset evaluation

The branch was tested against the two uploaded real ITSM-shaped datasets:

```text
Archive 4 incident event log rows: 141712
Archive 4 unique incidents: 24918
Archive 5 ITSM SLA rows: 100000
Kosh temporal facts ingested: 1667
Kosh binary edges ingested: 2522
Kosh hyperedges ingested: 200
Checks passed: 6 / 6
All passed: True
```

The time-ablation result is the most important product proof:

```text
Incident state exact-time accuracy: 1.0
Incident state static/collapsed-time accuracy: 0.001
SLA exact-time accuracy: 1.0
SLA static/no-time accuracy: 0.0
```

This supports the key thesis:

> Kosh Verify needs temporal evidence for operational truth. Without time, incident and SLA reasoning collapses into latest/static truth.

## Schmidt-style business framing

### Product category

**Agent reliability infrastructure** — a memory/provenance layer for long-running agents that need to reason over evolving evidence.

### Immediate buyer/use-case

Enterprise teams running AI agents over ServiceNow/Salesforce/ITSM/customer-support workflows.

### Why this matters

Agent systems fail when they forget what changed, collapse old and new truth, blur inferred claims with discovered evidence, miss contradictions across tools, answer when they should abstain, or cannot transfer reliable context between agents. Kosh Verify now demonstrates a credible local prototype for these problems.

### Demo-ready claim

> Kosh Verify lets agents preserve local memory, publish scoped evidence into a transaction/user memory pool, pull shared memory back with provenance, detect contradictions, preserve temporal-causal paths, and abstain when evidence is missing.

### What is still not done

This branch is not yet a production SaaS. Still pending: real ServiceNow connector, real Salesforce/Agentforce connector, real LangGraph node wrapper, real CrewAI task wrapper, ACL/tenancy/PII controls, durable shared-memory locking, visual Kosh Verify Studio, official external baseline adapters, 1,000-user queue-backed soak test, and Rust/native high-performance graph kernel.

## Recommendation

Freeze this as:

> **Kosh Verify v1.1 RC — Recursive Self-Healing + Framework-Agent Shared Memory**

Then build only three things next: ServiceNow connector, visual Studio, and public ITSM temporal-causal benchmark. Do not add more conceptual layers until these three are done.
