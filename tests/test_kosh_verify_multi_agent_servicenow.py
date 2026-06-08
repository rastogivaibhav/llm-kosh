from pathlib import Path

from llm_kosh.verify import (
    KoshAgent,
    MemoryTransferPacket,
    MultiAgentMemoryBus,
    build_synthetic_servicenow_dataset,
    split_servicenow_dataset_by_agent,
)


def test_servicenow_agents_operate_individually(tmp_path: Path):
    records = build_synthetic_servicenow_dataset()
    split = split_servicenow_dataset_by_agent(records)

    change_agent = KoshAgent("change_agent", "change-risk", tmp_path / "change")
    incident_agent = KoshAgent("incident_agent", "incident-triage", tmp_path / "incident")
    problem_agent = KoshAgent("problem_agent", "problem-rca", tmp_path / "problem")

    change_agent.ingest_servicenow_records(split["change_agent"])
    incident_agent.ingest_servicenow_records(split["incident_agent"])
    problem_agent.ingest_servicenow_records(split["problem_agent"])

    when = "2026-05-01T13:20:00+00:00"
    change_report = change_agent.verify("Which checkout change happened before the outage?", temporal_context=when).report
    incident_report = incident_agent.verify("What checkout incidents happened?", temporal_context=when).report
    problem_report = problem_agent.verify("What root cause evidence is missing for checkout?", temporal_context=when).report

    assert not change_report.abstain
    assert not incident_report.abstain
    assert not problem_report.abstain
    assert any("CHG9001" in fact["content"] for fact in change_report.facts)
    assert any("INC1001" in fact["content"] for fact in incident_report.facts)
    assert any("PRB2001" in fact["content"] for fact in problem_report.facts)


def test_two_agents_share_and_transfer_memories(tmp_path: Path):
    records = build_synthetic_servicenow_dataset()
    split = split_servicenow_dataset_by_agent(records)

    change_agent = KoshAgent("change_agent", "change-risk", tmp_path / "change")
    incident_agent = KoshAgent("incident_agent", "incident-triage", tmp_path / "incident")

    change_agent.ingest_servicenow_records(split["change_agent"])
    incident_agent.ingest_servicenow_records(split["incident_agent"])

    when = "2026-05-01T13:20:00+00:00"
    before = incident_agent.verify("Which ServiceNow change_request caused checkout outage?", temporal_context=when).report
    before_has_change = any("ServiceNow change_request CHG9001" in fact["content"] for fact in before.facts)

    bus = MultiAgentMemoryBus()
    facts_imported, edges_imported, hyperedges_imported = bus.transfer(
        change_agent, incident_agent, query="checkout deployment CHG9001"
    )

    after = incident_agent.verify("Which ServiceNow change_request caused checkout outage?", temporal_context=when).report
    after_has_change = any("ServiceNow change_request CHG9001" in fact["content"] for fact in after.facts)

    assert before_has_change is False
    assert facts_imported >= 1
    assert edges_imported >= 0
    assert hyperedges_imported >= 0
    assert len(bus.packets) == 1
    assert after_has_change is True
    assert any("Transferred from agent change_agent" in fact["content"] for fact in after.facts)


def test_memory_transfer_packet_serializes(tmp_path: Path):
    records = build_synthetic_servicenow_dataset()
    split = split_servicenow_dataset_by_agent(records)
    change_agent = KoshAgent("change_agent", "change-risk", tmp_path / "change")
    change_agent.ingest_servicenow_records(split["change_agent"])

    packet = change_agent.export_memory_packet(target_agent="incident_agent", query="CHG9001 checkout deployment")
    text = packet.to_json(indent=2)
    restored = MemoryTransferPacket.from_json(text)

    assert restored.source_agent == "change_agent"
    assert restored.target_agent == "incident_agent"
    assert len(restored.facts) >= 1
    assert "CHG9001" in restored.facts[0]["content"]
