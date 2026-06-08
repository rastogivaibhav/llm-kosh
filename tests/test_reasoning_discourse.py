"""Tests for discourse marker extraction (Task 3 of Path A)."""
from llm_kosh.engine.reasoning.discourse import (
    extract_discourse_markers,
    infer_temporal_edge,
    should_auto_create_edge,
)


def test_extract_sequence_markers():
    text = "First the database was provisioned. Then the servers were deployed."
    marks = extract_discourse_markers(text)
    assert any(m.marker_type == "sequence" for m in marks)
    assert any("then" in m.marker for m in marks)


def test_extract_causality_markers():
    text = "The service crashed because the database connection failed."
    marks = extract_discourse_markers(text)
    assert any(m.marker_type == "causality" for m in marks)


def test_infer_edge_sequence():
    edge_type, conf = infer_temporal_edge("Subsequently, servers were configured.")
    assert edge_type == "ENABLES"
    assert conf >= 0.70


def test_infer_edge_causality():
    edge_type, conf = infer_temporal_edge("As a result, payment was processed.")
    assert edge_type == "CAUSES"
    assert conf >= 0.80


def test_no_edge_for_simultaneity():
    should, _, _ = should_auto_create_edge("DB provisioned.", "Meanwhile, servers configured.")
    assert not should


def test_no_edge_without_markers():
    should, _, _ = should_auto_create_edge("A fact.", "Another fact.")
    assert not should


def test_auto_edge_decision_sequence():
    should, edge_type, conf = should_auto_create_edge(
        "Contract signed.", "Following the contract, delivery arrived."
    )
    assert should
    assert edge_type in ("ENABLES", "CAUSES")
    assert conf >= 0.70
