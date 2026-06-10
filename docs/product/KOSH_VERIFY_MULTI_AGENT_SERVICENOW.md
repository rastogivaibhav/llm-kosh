# Kosh Verify Multi-Agent ServiceNow Work Package

## Purpose

This work package turns Kosh Verify into a small multi-agent verification harness grounded in the existing LLM-Kosh / TheHypoKosh codebase.

It tests two concrete questions:

1. Can separate agents operate independently on ServiceNow-shaped ITSM records?
2. Can two agents share and transfer memories without relying on an LLM?

## What was added

```text
llm_kosh/verify/multi_agent.py
examples/kosh_verify/servicenow_multi_agent_demo.py
tests/test_kosh_verify_multi_agent_servicenow.py
docs/product/KOSH_VERIFY_MULTI_AGENT_SERVICENOW.md
reports/kosh_verify_multi_agent/servicenow_multi_agent_demo_output.json
reports/kosh_verify_multi_agent/MULTI_AGENT_SERVICENOW_TEST_REPORT.md
```

## New concepts

### KoshAgent

An independent Kosh Verify agent with its own local cartridge.

Each agent can:

- ingest ServiceNow-shaped records;
- create temporal facts;
- create ServiceNow relationship edges deterministically;
- verify questions using the existing Kosh Verify dialectic engine;
- export a memory packet;
- import a memory packet from another agent.

### ServiceNowRecord

A schema-light representation of ServiceNow ITSM data:

```text
table
sys_id
number
short_description
opened_at
updated_at
resolved_at
state
priority
cmdb_ci
assignment_group
fields
work_notes
```

This allows incidents, changes, problems, CIs, alerts and work notes to be converted into Kosh facts without an LLM.

### MemoryTransferPacket

A provenance-preserving packet containing:

```text
source_agent
target_agent
facts
edges
hyperedges
transfer_scope
created_at
```

When imported, the receiving agent creates new local fact IDs and records the source as:

```text
agent_transfer:<source_agent>:<original_source>
```

This prevents silent identity collision while preserving origin.

### MultiAgentMemoryBus

A tiny in-process bus for test/demo use. It transfers a packet from one `KoshAgent` to another.

## Synthetic ServiceNow dataset

The test dataset contains no private data. It includes:

- `CHG9001`: checkout deployment v4.2 changed timeout/cache settings.
- `INC1001`: checkout outage where customers could not complete payment.
- `INC1002`: checkout latency and worker saturation after deployment.
- `PRB2001`: root-cause review pointing to memory/config path.
- `INC1003`: contradictory status update denying memory pressure.

## Test result

Targeted multi-agent tests:

```text
3 passed
```

Relevant reasoning/product regression tests:

```text
71 passed
```

Focused product/reasoning pack:

```text
22 passed
```

## What this proves

The current Python code can run multi-agent memory verification without an LLM:

- a change agent can reason over change records;
- an incident agent can reason over incident records;
- a problem agent can reason over root-cause records;
- a receiving agent can import memory from another agent;
- transferred memory becomes query-visible in the receiving agent;
- provenance shows the memory came from another agent.

## What this does not yet prove

This is not a production ServiceNow connector yet.

Still pending:

- OAuth/API connector for real ServiceNow instances;
- pagination/incremental sync;
- ACL and PII redaction;
- mapping for journal entries, related lists and CMDB dependencies;
- conflict-resolution when two agents transfer competing facts;
- shared-memory hub with trust scoring;
- benchmark over a real anonymised incident dataset.

## Next enhancement

Build a real `ServiceNowAdapter`:

```text
llm_kosh/adapters/servicenow.py
```

The adapter should fetch:

- incidents;
- changes;
- problems;
- CMDB CIs;
- task SLA records;
- work notes and comments;
- incident-change-problem relationships.

Then route records into KoshAgent ingestion.
