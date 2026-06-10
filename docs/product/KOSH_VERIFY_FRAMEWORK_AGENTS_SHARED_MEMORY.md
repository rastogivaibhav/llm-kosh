# Kosh Verify Framework Agents + Shared Memory Pool

## Purpose

This package verifies the Silicon Valley product-wedge direction using the actual LLM-Kosh / TheHypoKosh codebase rather than a paper-only argument.

The target capability is:

> Independent agents from different frameworks can do their own work, preserve local Kosh memory, publish selected memory into a transaction/user scoped shared pool, and pull that shared memory back with provenance.

The implemented agents are framework-style adapters, not hard dependencies on external SDKs:

- `LangGraphKoshAgent` — state/workflow agent shape.
- `CrewAIKoshAgent` — role/task analyst agent shape.
- `SalesforceKoshAgent` — customer/case agent shape.

They are intentionally SDK-light so the memory layer remains project-native and testable without requiring LangGraph, CrewAI, Salesforce or LLM credentials.

## Implemented modules

```text
llm_kosh/verify/agent_frameworks.py
```

Core classes:

```text
AgentWorkItem
AgentWorkResult
FrameworkKoshAgent
LangGraphKoshAgent
CrewAIKoshAgent
SalesforceKoshAgent
KoshSharedMemoryPool
AgentFrameworkMemoryOrchestrator
SharedPoolReceipt
```

## Memory architecture verified

```text
LangGraph-style Agent      CrewAI-style Agent      Salesforce-style Agent
(local Kosh cartridge)     (local Kosh cartridge)  (local Kosh cartridge)
        │                         │                        │
        ├──────── publish ────────┼──────── publish ───────┤
        ▼                         ▼                        ▼
              Kosh Shared Transaction Memory Pool
              scope = transaction:txn_checkout_2026_05_01
        ▲                         ▲                        ▲
        └──────────── pull / import with provenance ────────┘

              Kosh Shared User Memory Pool
              scope = user:customer_acme_001
```

## What this proves

The current Python code can support:

1. Independent agent-local memory.
2. ServiceNow-shaped operational data ingestion.
3. Framework-style agent adapters.
4. Transaction-scoped shared memory.
5. User-scoped shared memory.
6. Provenance-preserving memory publish and pull.
7. A Salesforce-style agent using memory produced by LangGraph-style and CrewAI-style agents.

## What this does not yet prove

This package does not yet include production SDK integrations for:

- actual LangGraph runtime nodes;
- actual CrewAI runtime tasks/tools;
- actual Salesforce Agentforce / CRM APIs;
- actual ServiceNow API incremental sync;
- hosted visual Studio UI.

It proves the memory architecture and API seam needed to build those integrations next.

## Demo

Run:

```bash
python examples/kosh_verify/framework_agents_shared_memory_demo.py
```

The demo creates a synthetic checkout transaction:

- LangGraph-style agent observes workflow state and ServiceNow change/incident records.
- CrewAI-style agent preserves RCA evidence and contradiction.
- Salesforce-style agent preserves customer case memory.
- All agents publish into a transaction pool.
- Salesforce-style agent pulls from the pool and can then verify change + RCA + customer impact together.

## Tests

Targeted test file:

```text
tests/test_kosh_verify_framework_agents_shared_pool.py
```

The test verifies:

1. Framework-style agents operate independently on ServiceNow-shaped data.
2. All three publish into a shared transaction pool.
3. One agent pulls shared memory and reasons with other agents' memories.
4. User pool is separate from transaction pool.

## Product significance

This turns Kosh Verify from a single-agent verification API into an agent reliability substrate:

> Agents can work independently, exchange evidence, preserve provenance, and reason over a scoped shared memory pool without collapsing local and shared truth.

That is the product wedge: reliability memory for long-running enterprise agents.
