# Kosh Verify Temporal-Causal Provenance Dataset Evaluation

Generated: 2026-06-09T22:13:10.298343+00:00

## Executive verdict

Checks passed: **6/6**

> The uploaded ITSM datasets are suitable for validating Kosh Verify temporal-causal reasoning and provenance on real operational structures: incident state histories, lifecycle transitions, change/problem/RFC relationships, SLA deadlines, response/resolution times, and joint-causality evidence.

## Full dataset audit

### Archive 4 — ServiceNow-style incident event log

- Rows: **141,712**
- Unique incidents: **24,918**
- sys_updated_at range: **2016-02-29 01:23:00 → 2017-02-18 15:00:00**
- Rows with caused_by: **23** across **3** incidents
- Rows with problem_id: **2,295**
- Rows with RFC: **991**
- Reopened rows: **2,314** across **275** incidents
- Events per incident: mean **5.687**, median **5.0**, p95 **13.0**, max **58**

### Archive 5 — ITSM SLA dataset

- Rows / unique tickets: **100,000 / 100,000**
- Created range: **2024-04-01 00:00:00 → 2024-08-11 23:58:00**
- First-response SLA labels: `{'Met': 100000}`
- Resolution SLA labels: `{'Met': 100000}`
- Mean first response: **31.257 min**; p95 **58.0 min**
- Mean resolution: **140.074 min**; p95 **236.0 min**
- Temporal anomalies: `{'first_before_created': 0, 'resolution_before_first': 0, 'close_before_resolution': 0, 'first_response_after_sla_due_but_marked_met': 0, 'resolution_after_sla_due_but_marked_met': 0}`

## Kosh engine ingestion subset

- Incident sample incidents: **100**
- Incident sample rows: **809**
- Ticket sample rows: **100**
- Facts in Kosh cartridge: **1,667**
- Binary edges: **2,522**
- Hyperedges: **200**
- Build time: **3.071s**
- Eval time: **0.326s**

## Verification checks

| Check | Passed | Score | Notes |
|---|---:|---:|---|
| `incident_temporal_state_validity_windows` | yes | 1.000 | checked_states=809, passed_states=809 |
| `incident_causal_lifecycle_path_preserved` | yes | 1.000 | checked_incidents=100, passed=100 |
| `edge_and_hyperedge_provenance_coverage` | yes | 1.000 | edges=2522, edges_with_evidence_refs=2522, hyperedges=200, hyperedges_with_evidence_refs=200, allowed_origins_edges=2522 |
| `sla_joint_causality_hyperedges_fire_only_with_required_sources` | yes | 1.000 | checked_hyperedge_cases=200, passed=200 |
| `unrelated_query_no_evidence_or_low_stability` | yes | 1.000 | fibers=0, stability_status=no_evidence, stability_score=0.0 |
| `dialectic_result_created_for_ticket_query` | yes | 1.000 | ticket=TCKT-117688, final_status=reopened_for_non_convergent_review, opposition_findings=2 |

## Time-ablation result

- Incident state-at-midpoint cases: **1,000**
- Exact-time state accuracy: **1.000**
- Sequence-order state accuracy if the query is event-index based: **1.000**
- Static collapsed-time state accuracy: **0.001**
- SLA cases: **2,000**
- SLA exact-time accuracy: **1.000**
- SLA sequence-only accuracy: **0.000**
- SLA static/no-time accuracy: **0.000**

Interpretation: State ordering can sometimes be recovered from sequence/mod_count, but SLA compliance and exact state-at-clock-time require real temporal evidence. Collapsing to the latest state loses historical truth.

## What this proves

This validates that Kosh Verify can model real ITSM evidence as temporal facts, lifecycle edges, supersession edges, change/problem/RFC provenance, and SLA joint-causality hyperedges. It also shows why time matters: state-at-time and SLA compliance degrade sharply when timestamps are collapsed or absent.

## Honest limitations

- Archive 4 is strong for temporal incident-state reasoning, but sparse for explicit `caused_by` change relationships.
- Archive 5 is strong for SLA temporal reasoning, but all SLA labels are `Met`, so it is not a balanced breach/non-breach benchmark.
- The Kosh cartridge test uses a representative subset for runtime practicality; the full-dataset audit covers all rows.
- This run is deterministic and non-LLM; it validates the memory/reasoning kernel, not LLM extraction quality.