from __future__ import annotations

import json
import shutil
from pathlib import Path

from llm_kosh.verify import (
    KoshAgent,
    MultiAgentMemoryBus,
    build_synthetic_servicenow_dataset,
    split_servicenow_dataset_by_agent,
)


def main() -> None:
    root = Path("/tmp/kosh_servicenow_multi_agent_demo")
    if root.exists():
        shutil.rmtree(root)
    root.mkdir(parents=True, exist_ok=True)

    records = build_synthetic_servicenow_dataset()
    split = split_servicenow_dataset_by_agent(records)

    change_agent = KoshAgent("change_agent", "Understands ServiceNow changes", root / "change")
    incident_agent = KoshAgent("incident_agent", "Understands ServiceNow incidents", root / "incident")
    problem_agent = KoshAgent("problem_agent", "Understands ServiceNow problems/RCA", root / "problem")

    change_agent.ingest_servicenow_records(split["change_agent"])
    incident_agent.ingest_servicenow_records(split["incident_agent"])
    problem_agent.ingest_servicenow_records(split["problem_agent"])

    question = "What caused the checkout outage and what evidence is missing?"
    when = "2026-05-01T13:20:00+00:00"

    before = incident_agent.verify(question, temporal_context=when).report

    bus = MultiAgentMemoryBus()
    bus.transfer(change_agent, incident_agent, query="checkout deployment CHG9001")
    bus.transfer(problem_agent, incident_agent, query="checkout memory pressure root cause missing heap profile")

    after = incident_agent.verify(question, temporal_context=when).report

    print(json.dumps({
        "before_transfer": before.to_dict(),
        "after_transfer": after.to_dict(),
        "packets_transferred": len(bus.packets),
    }, indent=2, default=str))


if __name__ == "__main__":
    main()
