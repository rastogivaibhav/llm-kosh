import json
import pytest
from datetime import datetime, timezone
from llm_kosh.engine.reasoning.causal_dag import (
    EdgeType, TemporalFact, CausalEdge, HyperEdge, TrajectoryState,
    IntervalTree, CausalDAG,
)
from llm_kosh.core.memory import init_cartridge

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


# ---------------------------------------------------------------------------
# Task 2 tests: IntervalTree + CausalDAG event log
# ---------------------------------------------------------------------------

@pytest.fixture
def cartridge(tmp_path):
    init_cartridge(tmp_path, "Test")
    return tmp_path


def test_interval_tree_valid_at():
    tree = IntervalTree()
    now = _now()
    t0 = now.timestamp()
    tree.add("f1", t0 - 100, None)          # started 100s ago, still valid
    tree.add("f2", t0 - 200, t0 - 50)       # expired 50s ago
    tree.add("f3", t0 + 100, None)           # starts in future

    valid = tree.query_valid_at(t0)
    assert "f1" in valid
    assert "f2" not in valid
    assert "f3" not in valid


def test_interval_tree_remove():
    tree = IntervalTree()
    now = _now().timestamp()
    tree.add("f1", now - 10, None)
    tree.remove("f1")
    assert tree.query_valid_at(now) == []


def test_causal_dag_add_fact_writes_log(cartridge):
    dag = CausalDAG(cartridge)
    now = _now()
    fact_id = dag.add_fact(
        content="Gravity pulls objects down",
        ingested_at=now,
        documented_at=now,
        valid_from=now,
        valid_until=None,
        confidence=0.95,
        source="user",
    )
    assert fact_id.startswith("fact.")
    assert fact_id in dag.nodes

    # Event log was written
    log_path = cartridge / "reasoning" / "events.jsonl"
    assert log_path.exists()
    events = [json.loads(l) for l in log_path.read_text().splitlines() if l.strip()]
    assert any(e["event"] == "fact.added" and e["payload"]["id"] == fact_id for e in events)


def test_causal_dag_add_edge(cartridge):
    dag = CausalDAG(cartridge)
    now = _now()
    fid1 = dag.add_fact("A", now, now, now, None, 0.9, "user")
    fid2 = dag.add_fact("B", now, now, now, None, 0.9, "user")
    eid = dag.add_edge(fid1, fid2, EdgeType.CAUSES, 0.8, now, None, "test-agent")
    assert eid in {e.id for e in dag.edges.get(fid1, [])}


def test_causal_dag_rebuild_from_log(cartridge):
    dag1 = CausalDAG(cartridge)
    now = _now()
    fid = dag1.add_fact("Persistent fact", now, now, now, None, 0.9, "user")

    # Fresh instance must rebuild from log
    dag2 = CausalDAG(cartridge)
    assert fid in dag2.nodes
    assert dag2.nodes[fid].content == "Persistent fact"
