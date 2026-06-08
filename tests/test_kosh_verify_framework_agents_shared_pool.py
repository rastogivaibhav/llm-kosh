from pathlib import Path

from llm_kosh.verify import (
    build_cross_framework_servicenow_work_items,
    build_framework_orchestrator,
)


def _setup(tmp_path: Path):
    items = build_cross_framework_servicenow_work_items()
    orchestrator = build_framework_orchestrator(
        tmp_path / "framework_demo",
        transaction_id=items[0].transaction_id,
        user_id=items[0].user_id,
    )
    # Each framework-style agent operates independently first.
    orchestrator.agents["langgraph_state_agent"].run_work_item(
        items[0], question="Which deployment or incident did the workflow state observe?"
    )
    orchestrator.agents["crewai_rca_agent"].run_work_item(
        items[1], question="What RCA evidence and contradiction should be preserved?"
    )
    orchestrator.agents["salesforce_case_agent"].run_work_item(
        items[2], question="Which customer case was affected by checkout outage?"
    )
    return items, orchestrator


def test_framework_agents_operate_individually_on_servicenow_shaped_data(tmp_path: Path):
    items, orchestrator = _setup(tmp_path)
    when = "2026-05-01T13:20:00+00:00"

    langgraph_report = orchestrator.agents["langgraph_state_agent"].verify(
        "Which ServiceNow change did the workflow state observe?", temporal_context=when
    )
    crew_report = orchestrator.agents["crewai_rca_agent"].verify(
        "Which problem record mentions missing heap profile evidence?", temporal_context=when
    )
    sf_report = orchestrator.agents["salesforce_case_agent"].verify(
        "Which customer case was affected by checkout outage?", temporal_context=when
    )

    assert not langgraph_report.abstain
    assert not crew_report.abstain
    assert not sf_report.abstain
    assert any("CHG9001" in f["content"] for f in langgraph_report.facts)
    assert any("PRB2001" in f["content"] for f in crew_report.facts)
    assert any("CASE7001" in f["content"] for f in sf_report.facts)


def test_framework_agents_publish_to_shared_transaction_pool(tmp_path: Path):
    items, orchestrator = _setup(tmp_path)
    when = "2026-05-01T13:20:00+00:00"

    receipts = orchestrator.publish_all_to_transaction_pool(query="checkout outage CHG9001 PRB2001 CASE7001")
    pool_report = orchestrator.verify_transaction(
        "What changed, what contradicted it, and which customer was affected in transaction txn_checkout_2026_05_01?",
        temporal_context=when,
    )

    assert len(receipts) == 3
    assert all(r.fact_count >= 1 for r in receipts)
    assert not pool_report.abstain
    contents = "\n".join(f["content"] for f in pool_report.facts)
    assert "SharedMemory[transaction:txn_checkout_2026_05_01]" in contents
    assert "langgraph" in contents
    assert "crewai" in contents
    assert "salesforce" in contents
    assert "CHG9001" in contents
    assert "PRB2001" in contents
    assert "CASE7001" in contents


def test_agent_can_pull_shared_memory_and_reason_with_other_agents_memories(tmp_path: Path):
    items, orchestrator = _setup(tmp_path)
    when = "2026-05-01T13:20:00+00:00"

    # Before shared memory, Salesforce agent only has the customer case, not RCA/change memory.
    before = orchestrator.agents["salesforce_case_agent"].verify(
        "Which change and RCA explain the customer checkout case?", temporal_context=when
    )
    before_text = "\n".join(f["content"] for f in before.facts)
    assert "CHG9001" not in before_text or "PRB2001" not in before_text

    orchestrator.publish_all_to_transaction_pool(query="checkout CHG9001 PRB2001 CASE7001")
    receipt = orchestrator.agents["salesforce_case_agent"].pull_from_pool(
        orchestrator.transaction_pool
    )

    after = orchestrator.agents["salesforce_case_agent"].verify(
        "Which change and RCA explain the customer checkout case?", temporal_context=when
    )
    after_text = "\n".join(f["content"] for f in after.facts)

    assert receipt.fact_count >= 2
    assert "transaction_pool_txn_checkout_2026_05_01" in after_text
    assert "CHG9001" in after_text
    assert "PRB2001" in after_text
    assert "CASE7001" in after_text


def test_user_pool_is_separate_from_transaction_pool(tmp_path: Path):
    items, orchestrator = _setup(tmp_path)
    when = "2026-05-01T13:20:00+00:00"

    tx_receipts = orchestrator.publish_all_to_transaction_pool(query="checkout outage")
    user_receipt = orchestrator.publish_agent_to_user_pool(
        "salesforce_case_agent", query="Acme customer case CASE7001"
    )

    tx_report = orchestrator.verify_transaction("What happened to checkout?", temporal_context=when)
    user_report = orchestrator.verify_user("What should we remember about Acme customer?", temporal_context=when)

    tx_text = "\n".join(f["content"] for f in tx_report.facts)
    user_text = "\n".join(f["content"] for f in user_report.facts)

    assert len(tx_receipts) == 3
    assert user_receipt.fact_count >= 1
    assert "SharedMemory[transaction:txn_checkout_2026_05_01]" in tx_text
    assert "SharedMemory[user:customer_acme_001]" in user_text
    assert "CASE7001" in user_text
