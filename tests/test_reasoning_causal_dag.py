import json
import pytest
from datetime import datetime, timezone, timedelta
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


# ---------------------------------------------------------------------------
# Task 3 tests: import_existing_memories
# ---------------------------------------------------------------------------

from llm_kosh.engine.search import rebuild_index
from llm_kosh.core.utils import now_iso
import sqlite3


def _write_test_memory(root, title="Test Memory", body="A test fact", kind="note"):
    """Write a minimal memory markdown file and rebuild the index."""
    import uuid
    from pathlib import Path
    src = root / "source" / "notes"
    src.mkdir(parents=True, exist_ok=True)
    mem_id = "test." + uuid.uuid4().hex[:8]
    content = f"""---
id: {mem_id}
type: {kind}
title: {title}
project: test-project
status: active
visibility: private
created: {now_iso()}
---

{body}
"""
    (src / f"{mem_id}.md").write_text(content, encoding="utf-8")
    rebuild_index(root)
    return mem_id


def test_import_existing_memories(cartridge):
    mem_id = _write_test_memory(cartridge, "Gravity Note", "Objects fall at 9.8 m/s²")
    dag = CausalDAG(cartridge)
    dag.import_existing_memories()
    found = any(f.content and "9.8" in f.content for f in dag.nodes.values())
    assert found, "Expected imported memory in CausalDAG nodes"


def test_import_does_not_duplicate(cartridge):
    _write_test_memory(cartridge, "Unique Note", "Only once")
    dag = CausalDAG(cartridge)
    dag.import_existing_memories()
    count_before = len(dag.nodes)
    dag.import_existing_memories()
    assert len(dag.nodes) == count_before


# ---------------------------------------------------------------------------
# Task 11 tests: Snapshot — Cold Storage Tier
# ---------------------------------------------------------------------------

def test_snapshot_save_and_load(cartridge):
    dag1 = CausalDAG(cartridge)
    now = _now()
    fid = dag1.add_fact("Snapshot fact", now, now, now, None, 0.9, "user")
    dag1.save_snapshot()
    snapshot_path = cartridge / "reasoning" / "snapshot.json"
    assert snapshot_path.exists()

    # Load from snapshot — should not need to replay log
    dag2 = CausalDAG(cartridge)
    assert fid in dag2.nodes

def test_corrupt_snapshot_falls_back_to_log(cartridge):
    dag1 = CausalDAG(cartridge)
    now = _now()
    fid = dag1.add_fact("Log-only fact", now, now, now, None, 0.9, "user")
    dag1.save_snapshot()
    # Corrupt the snapshot
    (cartridge / "reasoning" / "snapshot.json").write_text("NOT JSON", encoding="utf-8")
    # Should still load from log
    dag2 = CausalDAG(cartridge)
    assert fid in dag2.nodes


# ---------------------------------------------------------------------------
# Task 3 (Path A) tests: Discourse marker auto-edge creation
# ---------------------------------------------------------------------------

def test_auto_edge_creation_from_discourse(tmp_path):
    """Discourse markers in new fact auto-create edges from preceding facts."""
    init_cartridge(tmp_path, "Test")
    dag = CausalDAG(tmp_path)
    now = datetime.now(timezone.utc)

    fact_1 = dag.add_fact(
        "Contract with vendor signed on April 1st.",
        now, now, now, None, 0.9, "test",
    )
    fact_2 = dag.add_fact(
        "Following the contract, the first delivery arrived on April 15th.",
        now + timedelta(minutes=1),
        now + timedelta(minutes=1),
        now + timedelta(minutes=1),
        None, 0.9, "test",
    )

    outgoing = dag.edges.get(fact_1, [])
    assert any(e.target_id == fact_2 for e in outgoing), (
        f"Expected auto-edge {fact_1} → {fact_2}; edges: {[(e.source_id, e.target_id) for e in outgoing]}"
    )
