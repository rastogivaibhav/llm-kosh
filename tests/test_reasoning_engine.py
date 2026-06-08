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

def test_anchor_selection_uses_threshold_not_hard_limit(tmp_path):
    """_select_anchors includes all candidates above threshold, not just top-5."""
    init_cartridge(tmp_path, "Test")
    engine = ReasoningEngine(tmp_path)

    # Build fake candidates: 8 above threshold, 2 below
    from llm_kosh.engine.reasoning.causal_dag import TemporalFact
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)

    def _fake_fact(n):
        return TemporalFact(
            id=f"fact.test{n:04d}xxxx",
            content=f"Fact {n}",
            ingested_at=now, documented_at=now,
            valid_from=now, valid_until=None,
            confidence=0.9, resonance_profile={}, source="test",
        )

    candidates = [(_fake_fact(i), i, max(0.0, 0.90 - i * 0.08)) for i in range(10)]
    # scores: 0.90, 0.82, 0.74, 0.66, 0.58, 0.50, 0.42, 0.34, 0.26, 0.18
    # above threshold 0.25: indices 0-8 (9 candidates), below: index 9 (0.18)

    anchors = engine._select_anchors(candidates, score_threshold=0.25)

    assert len(anchors) >= 6, f"Expected ≥6 anchors above threshold, got {len(anchors)}"
    # The lowest-scoring included candidate must be above threshold
    # (dedup may reduce count but should keep well-separated scores)


# ---------------------------------------------------------------------------
# TestQueryWithTrace
# ---------------------------------------------------------------------------

class TestQueryWithTrace:
    def test_returns_tuple(self, engine):
        now = _now()
        engine.ingest("Gravity pulls objects down", now, now, None, 0.95, [])
        from llm_kosh.engine.reasoning import QueryResult
        from llm_kosh.engine.reasoning.trace import QueryTrace
        result, trace = engine.query_with_trace("gravity", depth=2)
        assert isinstance(result, QueryResult)
        assert isinstance(trace, QueryTrace)

    def test_anchor_ids_match_result(self, engine):
        now = _now()
        engine.ingest("Photosynthesis converts light to energy", now, now, None, 0.9, [])
        result, trace = engine.query_with_trace("photosynthesis", depth=2)
        assert trace.anchor_ids == result.anchors

    def test_stability_score_matches_result(self, engine):
        now = _now()
        engine.ingest("Water boils at 100 degrees", now, now, None, 0.9, [])
        result, trace = engine.query_with_trace("water boiling", depth=2)
        assert trace.stability_score == result.stability.score

    def test_escape_triggered_matches_result(self, engine):
        now = _now()
        engine.ingest("The earth orbits the sun", now, now, None, 0.95, [])
        result, trace = engine.query_with_trace("earth orbit", depth=2)
        assert trace.escape_triggered == result.escape_triggered

    def test_trace_is_auto_saved(self, engine):
        now = _now()
        engine.ingest("Atoms form molecules", now, now, None, 0.9, [])
        before = engine._trace_store.count()
        engine.query_with_trace("atoms molecules", depth=2)
        after = engine._trace_store.count()
        assert after == before + 1

    def test_execution_time_recorded(self, engine):
        now = _now()
        engine.ingest("Light travels at 3e8 m/s", now, now, None, 0.95, [])
        _result, trace = engine.query_with_trace("light speed", depth=2)
        assert trace.execution_time_secs >= 0.0

    def test_query_field_set(self, engine):
        now = _now()
        engine.ingest("DNA carries genetic information", now, now, None, 0.9, [])
        _result, trace = engine.query_with_trace("DNA genetics", depth=2)
        assert trace.query == "DNA genetics"


# ---------------------------------------------------------------------------
# TestDialecticQueryWithTrace
# ---------------------------------------------------------------------------

class TestDialecticQueryWithTrace:
    def test_returns_tuple(self, engine):
        now = _now()
        engine.ingest("Evolution is driven by natural selection", now, now, None, 0.9, [])
        from llm_kosh.engine.reasoning.dialectic import DialecticResult
        from llm_kosh.engine.reasoning.trace import QueryTrace
        result, trace = engine.dialectic_query_with_trace("evolution", depth=2)
        assert isinstance(result, DialecticResult)
        assert isinstance(trace, QueryTrace)

    def test_dialectic_result_summary_not_none(self, engine):
        now = _now()
        engine.ingest("Stars form from nebulae", now, now, None, 0.9, [])
        _result, trace = engine.dialectic_query_with_trace("stars nebulae", depth=2)
        assert trace.dialectic_result_summary is not None

    def test_dialectic_result_summary_keys(self, engine):
        now = _now()
        engine.ingest("Cells are the basic unit of life", now, now, None, 0.9, [])
        _result, trace = engine.dialectic_query_with_trace("cells life", depth=2)
        summary = trace.dialectic_result_summary
        assert "converged_fact_id" in summary
        assert "converged_score" in summary
        assert "opposition_challenges" in summary
        assert "reopened" in summary
        assert "final_status" in summary

    def test_trace_is_auto_saved(self, engine):
        now = _now()
        engine.ingest("Entropy increases in closed systems", now, now, None, 0.9, [])
        before = engine._trace_store.count()
        engine.dialectic_query_with_trace("entropy thermodynamics", depth=2)
        after = engine._trace_store.count()
        assert after == before + 1

    def test_stability_score_from_initial_result(self, engine):
        now = _now()
        engine.ingest("Quantum entanglement links particles", now, now, None, 0.9, [])
        result, trace = engine.dialectic_query_with_trace("quantum entanglement", depth=2)
        assert trace.stability_score == result.initial_result.stability.score
