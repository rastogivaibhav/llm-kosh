#!/usr/bin/env python3
"""Sustained 100-user stress test for Kosh Verify framework agents.

This runner simulates many users/transactions interacting with three different
framework-style agents:

- LangGraph-style workflow/state agent
- CrewAI-style RCA/role agent
- Salesforce-style customer/case agent

Each user gets its own transaction-scoped shared memory pool and user-scoped
shared memory pool.  The test verifies that every agent can work locally,
publish to the transaction pool, and pull shared memory back with provenance.

No external LLM, Salesforce, ServiceNow, LangGraph, or CrewAI dependency is used.
The goal is to stress the Kosh memory/reasoning substrate and adapter shapes.
"""
from __future__ import annotations

import argparse
import sys
import json
import statistics
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from llm_kosh.verify.agent_frameworks import (
    AgentFrameworkMemoryOrchestrator,
    AgentWorkItem,
    CrewAIKoshAgent,
    LangGraphKoshAgent,
    SalesforceKoshAgent,
)
from llm_kosh.verify.multi_agent import ServiceNowRecord


def iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def build_user_work_items(user_index: int) -> List[AgentWorkItem]:
    """Create one synthetic but realistic cross-agent incident/case flow."""
    uid = f"customer_acme_{user_index:03d}"
    txn = f"txn_checkout_{user_index:03d}_2026_05_01"
    chg_num = f"CHG{9000 + user_index}"
    inc_num = f"INC{1000 + user_index}"
    inc_contra_num = f"INC{3000 + user_index}"
    prb_num = f"PRB{2000 + user_index}"
    case_num = f"CASE{7000 + user_index}"
    chg_sys = f"chg_{9000 + user_index}"
    inc_sys = f"inc_{1000 + user_index}"
    inc_contra_sys = f"inc_{3000 + user_index}"
    prb_sys = f"prb_{2000 + user_index}"
    case_sys = f"case_{7000 + user_index}"

    return [
        AgentWorkItem(
            work_id=f"lg_state_{user_index:03d}",
            transaction_id=txn,
            user_id=uid,
            title=f"LangGraph workflow triage for checkout transaction {user_index}",
            description=f"Workflow state connected {chg_num} to checkout incidents and preserved temporal order.",
            source_system="langgraph",
            event_time="2026-05-01T12:32:00+00:00",
            records=[
                ServiceNowRecord(
                    table="change_request",
                    sys_id=chg_sys,
                    number=chg_num,
                    short_description=f"Checkout deployment v4.2 changed payment timeout and cache settings for transaction {user_index}",
                    opened_at="2026-05-01T11:55:00+00:00",
                    updated_at="2026-05-01T12:05:00+00:00",
                    state="implemented",
                    priority="3",
                    cmdb_ci="checkout-service",
                    assignment_group="payments-platform",
                    fields={"risk": "medium", "confidence": 0.88},
                    work_notes=[f"Workflow state observed deployment {chg_num} before incidents."],
                ),
                ServiceNowRecord(
                    table="incident",
                    sys_id=inc_sys,
                    number=inc_num,
                    short_description=f"Checkout outage: user {uid} cannot complete payment",
                    opened_at="2026-05-01T12:22:00+00:00",
                    updated_at="2026-05-01T12:30:00+00:00",
                    state="major_incident",
                    priority="1",
                    cmdb_ci="checkout-service",
                    assignment_group="service-desk",
                    fields={"caused_by_change": chg_sys, "confidence": 0.94},
                    work_notes=[f"Failures started after {chg_num} and affected payment completion."],
                ),
            ],
            metadata={"confidence": 0.90, "state_key": f"checkout.incident.triage.{user_index}"},
        ),
        AgentWorkItem(
            work_id=f"crew_rca_{user_index:03d}",
            transaction_id=txn,
            user_id=uid,
            title=f"CrewAI analyst root-cause review for transaction {user_index}",
            description=f"Analyst preserved memory pressure as likely RCA for {prb_num} and noted missing heap profile evidence.",
            source_system="crewai",
            event_time="2026-05-01T13:10:00+00:00",
            records=[
                ServiceNowRecord(
                    table="problem",
                    sys_id=prb_sys,
                    number=prb_num,
                    short_description=f"Root cause review: checkout memory pressure increased after {chg_num} config path",
                    opened_at="2026-05-01T13:05:00+00:00",
                    updated_at="2026-05-01T15:00:00+00:00",
                    state="rca_in_progress",
                    priority="2",
                    cmdb_ci="checkout-service",
                    assignment_group="platform-sre",
                    fields={"root_cause": f"configuration path in {chg_num}", "confidence": 0.84},
                    work_notes=["Heap profile missing for 12:30 to 13:00, so certainty remains bounded."],
                ),
                ServiceNowRecord(
                    table="incident",
                    sys_id=inc_contra_sys,
                    number=inc_contra_num,
                    short_description=f"Status update says checkout issue for {uid} not related to memory pressure",
                    opened_at="2026-05-01T12:27:00+00:00",
                    updated_at="2026-05-01T12:31:00+00:00",
                    state="closed",
                    priority="3",
                    cmdb_ci="checkout-service",
                    assignment_group="service-desk",
                    fields={"contradicts": prb_sys, "confidence": 0.62},
                    work_notes=["Early update denied memory pressure; later RCA suggested memory pressure."],
                ),
            ],
            metadata={"confidence": 0.86, "crew_role": "rca_analyst"},
        ),
        AgentWorkItem(
            work_id=f"sf_case_{user_index:03d}",
            transaction_id=txn,
            user_id=uid,
            title=f"Salesforce customer case escalation for {uid}",
            description="Customer reported checkout payment failures during the same transaction window.",
            source_system="salesforce",
            event_time="2026-05-01T12:40:00+00:00",
            records=[
                ServiceNowRecord(
                    table="case",
                    sys_id=case_sys,
                    number=case_num,
                    short_description=f"Acme customer case {case_num}: payment failure during checkout outage window",
                    opened_at="2026-05-01T12:40:00+00:00",
                    updated_at="2026-05-01T12:45:00+00:00",
                    state="escalated",
                    priority="1",
                    cmdb_ci="checkout-service",
                    assignment_group="customer-success",
                    fields={"customer": uid, "related_incident": inc_num, "confidence": 0.89},
                    work_notes=[f"Customer impact aligns with checkout outage transaction {txn}."],
                ),
            ],
            metadata={"confidence": 0.87, "account": "Acme", "case_priority": "P1"},
        ),
    ]


def build_orchestrator(root: Path, transaction_id: str, user_id: str) -> AgentFrameworkMemoryOrchestrator:
    orch = AgentFrameworkMemoryOrchestrator(root=root, transaction_id=transaction_id, user_id=user_id)
    orch.register(LangGraphKoshAgent("langgraph_state_agent", "workflow-state-triage", root / "agents" / "langgraph"))
    orch.register(CrewAIKoshAgent("crewai_rca_agent", "role-based-rca", root / "agents" / "crewai"))
    orch.register(SalesforceKoshAgent("salesforce_case_agent", "customer-case-memory", root / "agents" / "salesforce"))
    return orch


def run_user_session(base_root: Path, user_index: int, rounds: int) -> Dict[str, Any]:
    started = time.perf_counter()
    errors: List[str] = []
    validation: Dict[str, bool] = {}
    facts_seen = 0
    receipts_seen = 0
    reports_seen = 0

    items = build_user_work_items(user_index)
    txn = items[0].transaction_id
    uid = items[0].user_id
    root = base_root / f"user_{user_index:03d}"
    orch = build_orchestrator(root, txn, uid)
    when = "2026-05-01T13:20:00+00:00"
    chg_num = f"CHG{9000 + user_index}"
    prb_num = f"PRB{2000 + user_index}"
    case_num = f"CASE{7000 + user_index}"

    try:
        # Independent local work by each framework-style agent.
        local_results = [
            orch.agents["langgraph_state_agent"].run_work_item(
                items[0], question=f"Which deployment or incident did the workflow state observe for {uid}?"
            ),
            orch.agents["crewai_rca_agent"].run_work_item(
                items[1], question=f"What RCA evidence and contradiction should be preserved for {uid}?"
            ),
            orch.agents["salesforce_case_agent"].run_work_item(
                items[2], question=f"Which customer case was affected for {uid}?"
            ),
        ]
        reports_seen += len(local_results)
        validation["local_agents_non_abstain"] = all(not r.local_report.abstain for r in local_results)

        # Sustained interaction rounds.  Each round republishes fresh agent evidence
        # to the scoped transaction pool and verifies the pool.  We pull into the
        # Salesforce agent once after the sustained rounds to avoid duplicate
        # exponential memory growth in this prototype.
        for round_idx in range(rounds):
            receipts = orch.publish_all_to_transaction_pool(query=f"checkout outage {chg_num} {prb_num} {case_num}")
            receipts_seen += len(receipts)
            tx_report = orch.verify_transaction(
                f"Round {round_idx}: what changed, what contradicted it, and which customer was affected for {txn}?",
                temporal_context=when,
            )
            reports_seen += 1
            facts_seen += len(tx_report.facts)

        pull_receipt = orch.agents["salesforce_case_agent"].pull_from_pool(
            orch.transaction_pool,
            query=None,
        )
        receipts_seen += 1
        after = orch.agents["salesforce_case_agent"].verify(
            f"Which change and RCA explain the customer checkout case {case_num}?",
            temporal_context=when,
        )
        reports_seen += 1
        facts_seen += len(after.facts)

        # Publish customer memory separately to user-scoped pool.
        user_receipt = orch.publish_agent_to_user_pool("salesforce_case_agent", query=f"Acme customer case {case_num}")
        receipts_seen += 1
        user_report = orch.verify_user(f"What should we remember about {uid} customer case?", temporal_context=when)
        reports_seen += 1
        facts_seen += len(user_report.facts)

        sf_report = orch.agents["salesforce_case_agent"].verify(
            f"Which change and RCA explain the customer checkout case {case_num}?",
            temporal_context=when,
        )
        sf_text = "\n".join(f["content"] for f in sf_report.facts)
        pool_report = orch.verify_transaction(
            f"What happened in {txn} across LangGraph, CrewAI and Salesforce agents?",
            temporal_context=when,
        )
        pool_text = "\n".join(f["content"] for f in pool_report.facts)
        # Retrieval can legitimately select a subset of the pool. For storage/publish
        # correctness, validate against the full scoped pool memory.
        full_pool_text = "\n".join(
            fact.content for fact in orch.transaction_pool.kv.engine.dag.nodes.values()
        )
        user_text = "\n".join(f["content"] for f in user_report.facts)
        reports_seen += 2
        facts_seen += len(sf_report.facts) + len(pool_report.facts)

        validation["transaction_pool_has_all_frameworks"] = all(
            token in full_pool_text for token in ["langgraph", "crewai", "salesforce"]
        )
        validation["transaction_pool_has_business_ids"] = all(
            token in full_pool_text for token in [chg_num, prb_num, case_num]
        )
        validation["salesforce_pulled_other_agents_memory"] = chg_num in sf_text and prb_num in sf_text and case_num in sf_text
        validation["user_pool_is_scoped"] = f"SharedMemory[user:{uid}]" in user_text and case_num in user_text
        validation["publish_pull_receipts_created"] = receipts_seen >= (rounds * 3 + 2)
        validation["no_abstain_after_memory_share"] = not sf_report.abstain and not pool_report.abstain
    except Exception as exc:  # keep stress run going and report failures
        errors.append(f"{type(exc).__name__}: {exc}")

    elapsed = time.perf_counter() - started
    return {
        "user_index": user_index,
        "transaction_id": txn,
        "user_id": uid,
        "elapsed_seconds": elapsed,
        "rounds": rounds,
        "reports_seen": reports_seen,
        "receipts_seen": receipts_seen,
        "facts_seen_in_reports": facts_seen,
        "validation": validation,
        "passed": not errors and all(validation.values()) and len(validation) >= 6,
        "errors": errors,
    }


def percentile(values: List[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    idx = min(len(ordered) - 1, max(0, int(round((pct / 100.0) * (len(ordered) - 1)))))
    return ordered[idx]


def write_markdown_report(result: Dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    summary = result["summary"]
    lines = [
        "# Kosh Verify 100-User Framework-Agent Stress Test Report",
        "",
        f"Generated at: `{result['generated_at']}`",
        "",
        "## Scenario",
        "",
        "This sustained test simulates 100 independent users/transactions interacting with three framework-style Kosh agents:",
        "",
        "- LangGraph-style workflow/state agent",
        "- CrewAI-style RCA/role agent",
        "- Salesforce-style customer/case agent",
        "",
        "Each user has local agent cartridges, a transaction-scoped shared memory pool, and a user-scoped shared memory pool.",
        "The test validates local work, publish-to-pool, pull-from-pool, provenance-marked shared memory, and scoped user memory.",
        "",
        "## Summary",
        "",
        f"- Users simulated: **{summary['users_requested']}**",
        f"- Users completed: **{summary['users_completed']}**",
        f"- Users passed all validations: **{summary['users_passed']}**",
        f"- Users failed: **{summary['users_failed']}**",
        f"- Rounds per user: **{summary['rounds_per_user']}**",
        f"- Agent work actions: **{summary['agent_work_actions']}**",
        f"- Publish/pull receipts: **{summary['publish_pull_receipts']}**",
        f"- Verify reports observed: **{summary['verify_reports']}**",
        f"- Total wall time: **{summary['wall_time_seconds']:.3f}s**",
        f"- Throughput: **{summary['users_per_second']:.2f} users/s**",
        "",
        "## Latency per user",
        "",
        f"- p50: **{summary['latency_seconds']['p50']:.3f}s**",
        f"- p90: **{summary['latency_seconds']['p90']:.3f}s**",
        f"- p95: **{summary['latency_seconds']['p95']:.3f}s**",
        f"- max: **{summary['latency_seconds']['max']:.3f}s**",
        "",
        "## Validation checks",
        "",
    ]
    for check, count in summary["validation_pass_counts"].items():
        lines.append(f"- `{check}`: {count}/{summary['users_completed']} users")
    lines.extend([
        "",
        "## Interpretation",
        "",
        "This test does not prove production-scale readiness. It proves the current Python prototype can sustain a 100-user, multi-agent memory-sharing simulation without an LLM dependency, while preserving transaction/user scoped memory behaviour.",
        "",
        "The next level of stress testing should add real concurrent service processes, durable locking, ACLs, PII redaction, queue-based ingestion, and external framework adapters.",
    ])
    if summary["users_failed"]:
        lines.extend(["", "## Failed users", ""])
        for item in result["users"]:
            if not item["passed"]:
                lines.append(f"- user_index={item['user_index']}, errors={item['errors']}, validation={item['validation']}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run 100-user Kosh Verify framework-agent stress test")
    parser.add_argument("--users", type=int, default=100)
    parser.add_argument("--rounds", type=int, default=3, help="publish/pull/verify rounds per user")
    parser.add_argument("--workers", type=int, default=10)
    parser.add_argument("--root", type=Path, default=Path("./.stress_runs/framework_agents_100_users"))
    parser.add_argument("--out", type=Path, default=Path("reports/kosh_verify_framework_agents/100_user_stress_results.json"))
    parser.add_argument("--markdown", type=Path, default=Path("reports/kosh_verify_framework_agents/100_USER_SUSTAINED_STRESS_TEST_REPORT.md"))
    args = parser.parse_args()

    args.root.mkdir(parents=True, exist_ok=True)
    start = time.perf_counter()
    users: List[Dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = [pool.submit(run_user_session, args.root, i, args.rounds) for i in range(1, args.users + 1)]
        for future in as_completed(futures):
            users.append(future.result())

    users.sort(key=lambda item: item["user_index"])
    wall = time.perf_counter() - start
    latencies = [u["elapsed_seconds"] for u in users]
    validation_keys = sorted({key for u in users for key in u["validation"].keys()})
    validation_pass_counts = {
        key: sum(1 for u in users if u["validation"].get(key) is True)
        for key in validation_keys
    }
    passed = sum(1 for u in users if u["passed"])
    summary = {
        "users_requested": args.users,
        "users_completed": len(users),
        "users_passed": passed,
        "users_failed": len(users) - passed,
        "rounds_per_user": args.rounds,
        "workers": args.workers,
        "agent_work_actions": len(users) * 3,
        "publish_pull_receipts": sum(u["receipts_seen"] for u in users),
        "verify_reports": sum(u["reports_seen"] for u in users),
        "facts_seen_in_reports": sum(u["facts_seen_in_reports"] for u in users),
        "wall_time_seconds": wall,
        "users_per_second": (len(users) / wall) if wall else 0.0,
        "latency_seconds": {
            "min": min(latencies) if latencies else 0.0,
            "p50": percentile(latencies, 50),
            "p90": percentile(latencies, 90),
            "p95": percentile(latencies, 95),
            "max": max(latencies) if latencies else 0.0,
            "mean": statistics.mean(latencies) if latencies else 0.0,
        },
        "validation_pass_counts": validation_pass_counts,
    }
    result = {
        "generated_at": iso_now(),
        "summary": summary,
        "users": users,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    write_markdown_report(result, args.markdown)
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0 if summary["users_failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
