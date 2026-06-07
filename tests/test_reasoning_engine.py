import pytest, time
from datetime import datetime, timezone
from pathlib import Path
from llm_kosh.core.memory import init_cartridge
from llm_kosh.engine.reasoning import ReasoningEngine, QueryResult

def _now():
    return datetime.now(timezone.utc)

@pytest.fixture
def engine(tmp_path):
    init_cartridge(tmp_path, "Test")
    return ReasoningEngine(tmp_path)

def test_engine_initializes(engine):
    assert engine is not None
    assert engine.dag is not None

def test_engine_ingest_returns_id(engine):
    now = _now()
    fid = engine.ingest(
        content="The sun rises in the east",
        documented_at=now,
        valid_from=now,
        valid_until=None,
        confidence=0.95,
        causal_edges=[],
    )
    assert fid.startswith("fact.")

def test_engine_ingest_with_edge(engine):
    now = _now()
    fid1 = engine.ingest("Cause fact", now, now, None, 0.9, [])
    fid2 = engine.ingest("Effect fact", now, now, None, 0.9,
                         [{"target_id": fid1, "edge_type": "ENABLES", "confidence": 0.8}])
    assert fid1 in engine.dag.nodes
    assert fid2 in engine.dag.nodes

def test_engine_query_returns_result(engine):
    now = _now()
    engine.ingest("Gravity pulls objects toward Earth", now, now, None, 0.95, [])
    engine.ingest("Newton studied gravity and motion", now, now, None, 0.9, [])
    result = engine.query("gravity Newton", temporal_context=None, depth=2)
    assert isinstance(result, QueryResult)
    assert hasattr(result, "bundle")
    assert hasattr(result, "stability")
    assert hasattr(result, "anchors")

def test_engine_critique(engine):
    now = _now()
    fid = engine.ingest("Test fact", now, now, None, 0.9, [])
    result = engine.critique([fid])
    assert 0.0 <= result.score <= 1.0
    assert result.status in ("stable", "marginal", "unstable")

def test_engine_explore(engine):
    now = _now()
    fid1 = engine.ingest("Source", now, now, None, 0.9, [])
    fid2 = engine.ingest("Target", now, now, None, 0.9,
                         [{"target_id": fid1, "edge_type": "CAUSES", "confidence": 0.8}])
    bundle = engine.explore(fid2, fid1, max_hops=2)
    from llm_kosh.engine.reasoning.fiber_bundle import FiberBundle
    assert isinstance(bundle, FiberBundle)

def test_engine_rebuilds_from_log(tmp_path):
    init_cartridge(tmp_path, "Test")
    e1 = ReasoningEngine(tmp_path)
    now = _now()
    fid = e1.ingest("Persisted fact", now, now, None, 0.9, [])
    # Fresh engine must see the same fact
    e2 = ReasoningEngine(tmp_path)
    assert fid in e2.dag.nodes
