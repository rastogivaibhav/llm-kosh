import pytest
from datetime import datetime, timezone
from llm_kosh.engine.reasoning.causal_dag import (
    EdgeType, TemporalFact, CausalEdge, HyperEdge, TrajectoryState
)

def _now() -> datetime:
    return datetime.now(timezone.utc)

def test_edge_type_values():
    assert EdgeType.ENABLES.value == "ENABLES"
    assert EdgeType.CAUSES.value == "CAUSES"
    assert EdgeType.CONTRADICTS.value == "CONTRADICTS"
    assert EdgeType.SUPERSEDES.value == "SUPERSEDES"
    assert EdgeType.INFERS.value == "INFERS"

def test_temporal_fact_creation():
    now = _now()
    fact = TemporalFact(
        id="f1",
        content="Apples fall downward",
        ingested_at=now,
        documented_at=now,
        valid_from=now,
        valid_until=None,
        confidence=0.9,
        resonance_profile={"low": [0.1], "mid": [0.2], "high": [0.3]},
        source="user",
    )
    assert fact.id == "f1"
    assert fact.confidence == 0.9
    assert fact.valid_until is None
    assert fact.source == "user"

def test_causal_edge_creation():
    now = _now()
    edge = CausalEdge(
        id="e1",
        source_id="f1",
        target_id="f2",
        edge_type=EdgeType.CAUSES,
        confidence=0.8,
        valid_from=now,
        valid_until=None,
        established_by="agent-1",
    )
    assert edge.source_id == "f1"
    assert edge.edge_type == EdgeType.CAUSES

def test_hyperedge_creation():
    now = _now()
    he = HyperEdge(
        id="he1",
        source_ids={"f1", "f2"},
        target_id="f3",
        edge_type=EdgeType.ENABLES,
        confidence=0.75,
        valid_from=now,
        valid_until=None,
    )
    assert "f1" in he.source_ids
    assert he.target_id == "f3"

def test_trajectory_state_defaults():
    ts = TrajectoryState(session_id="s1")
    assert ts.escape_count == 0
    assert ts.steps == []
    assert ts.stability == 1.0
