from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from llm_kosh.verify import build_cross_framework_servicenow_work_items, build_framework_orchestrator


def main() -> None:
    root = Path(".demo_framework_agents_memory")
    if root.exists():
        shutil.rmtree(root)

    items = build_cross_framework_servicenow_work_items()
    orchestrator = build_framework_orchestrator(root, items[0].transaction_id, items[0].user_id)

    orchestrator.agents["langgraph_state_agent"].run_work_item(
        items[0], question="Which deployment or incident did the workflow state observe?"
    )
    orchestrator.agents["crewai_rca_agent"].run_work_item(
        items[1], question="What RCA evidence and contradiction should be preserved?"
    )
    orchestrator.agents["salesforce_case_agent"].run_work_item(
        items[2], question="Which customer case was affected by checkout outage?"
    )

    before = orchestrator.agents["salesforce_case_agent"].verify(
        "Which change and RCA explain the customer checkout case?",
        temporal_context="2026-05-01T13:20:00+00:00",
    )

    publish_receipts = orchestrator.publish_all_to_transaction_pool(query="checkout CHG9001 PRB2001 CASE7001")
    pull_receipt = orchestrator.agents["salesforce_case_agent"].pull_from_pool(orchestrator.transaction_pool)

    after = orchestrator.agents["salesforce_case_agent"].verify(
        "Which change and RCA explain the customer checkout case?",
        temporal_context="2026-05-01T13:20:00+00:00",
    )
    transaction_report = orchestrator.verify_transaction(
        "What happened to checkout, what contradicted it, and which customer was affected?",
        temporal_context="2026-05-01T13:20:00+00:00",
    )

    out = {
        "scenario": "LangGraph-style + CrewAI-style + Salesforce-style agents share Kosh memory",
        "transaction_id": items[0].transaction_id,
        "user_id": items[0].user_id,
        "publish_receipts": [r.__dict__ for r in publish_receipts],
        "pull_receipt": pull_receipt.__dict__,
        "salesforce_before_shared_memory_fact_count": len(before.facts),
        "salesforce_after_shared_memory_fact_count": len(after.facts),
        "salesforce_after_has_chg9001": any("CHG9001" in f["content"] for f in after.facts),
        "salesforce_after_has_prb2001": any("PRB2001" in f["content"] for f in after.facts),
        "salesforce_after_has_case7001": any("CASE7001" in f["content"] for f in after.facts),
        "transaction_pool_report": transaction_report.to_dict(),
        "agent_after_pull_report": after.to_dict(),
    }
    print(json.dumps(out, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
