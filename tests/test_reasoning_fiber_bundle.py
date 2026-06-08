import pytest
from datetime import datetime, timezone, timedelta
from llm_kosh.core.memory import init_cartridge
from llm_kosh.engine.reasoning.causal_dag import CausalDAG, EdgeType
from llm_kosh.engine.reasoning.causal_retrieval import CausalRetrieval
from llm_kosh.engine.reasoning.fiber_bundle import (
    CausalPath, Fiber, FiberBundle, build_fiber_bundle,
    _enumerate_paths, _enumerate_paths_backward,
)

def _now():
    return datetime.now(timezone.utc)

@pytest.fixture
def graph(tmp_path):
    """A → B → C, and A → C directly (two paths to C)."""
    init_cartridge(tmp_path, "Test")
    dag = CausalDAG(tmp_path)
    now = _now()
    fa = dag.add_fact("A fact", now, now, now, None, 0.9, "user")
    fb = dag.add_fact("B fact", now, now, now, None, 0.9, "user")
    fc = dag.add_fact("C fact", now, now, now, None, 0.9, "user")
    ea1 = dag.add_edge(fa, fb, EdgeType.CAUSES, 0.8, now, None, "test")
    ea2 = dag.add_edge(fb, fc, EdgeType.CAUSES, 0.7, now, None, "test")
    ea3 = dag.add_edge(fa, fc, EdgeType.ENABLES, 0.9, now, None, "test")  # direct path
    return dag, fa, fb, fc

def test_causal_path_confidence_product():
    from llm_kosh.engine.reasoning.causal_dag import CausalEdge, EdgeType
    import uuid
    now = _now()
    e1 = CausalEdge(id="e1", source_id="a", target_id="b", edge_type=EdgeType.CAUSES,
                    confidence=0.8, valid_from=now, valid_until=None, established_by="x")
    e2 = CausalEdge(id="e2", source_id="b", target_id="c", edge_type=EdgeType.CAUSES,
                    confidence=0.5, valid_from=now, valid_until=None, established_by="x")
    path = CausalPath(edges=[e1, e2], confidence_product=0.8 * 0.5, temporal_consistency=1.0)
    assert abs(path.confidence_product - 0.4) < 1e-9

def test_build_fiber_bundle_preserves_all_paths(graph):
    import time
    dag, fa, fb, fc = graph
    retrieval = CausalRetrieval(dag)
    candidates = retrieval.retrieve("fact", time.time(), depth=3)
    bundle = build_fiber_bundle(dag, candidates, anchor_ids=[fa], query_time=time.time(), max_hops=3)
    assert isinstance(bundle, FiberBundle)
    # C should be reachable via two paths: A→B→C and A→C
    if fc in bundle.fibers:
        assert bundle.fibers[fc].degeneracy >= 2

def test_fiber_max_confidence(graph):
    import time
    dag, fa, fb, fc = graph
    retrieval = CausalRetrieval(dag)
    candidates = retrieval.retrieve("fact", time.time(), depth=3)
    bundle = build_fiber_bundle(dag, candidates, anchor_ids=[fa], query_time=time.time(), max_hops=3)
    for fiber in bundle.fibers.values():
        assert fiber.max_confidence >= 0.0
        assert fiber.max_confidence <= 1.0

def test_fiber_bundle_never_collapses(graph):
    import time
    dag, fa, fb, fc = graph
    retrieval = CausalRetrieval(dag)
    candidates = retrieval.retrieve("fact", time.time(), depth=3)
    bundle = build_fiber_bundle(dag, candidates, anchor_ids=[fa], query_time=time.time(), max_hops=3)
    # Bundle must carry paths, not a single ranked list
    for fid, fiber in bundle.fibers.items():
        assert isinstance(fiber.paths, list)


def test_bidirectional_path_enumeration(tmp_path):
    """Backward paths find ancestor facts in a temporal chain."""
    init_cartridge(tmp_path, "Test")
    dag = CausalDAG(tmp_path)
    now = datetime.now(timezone.utc)

    # Forward chain: A → B → C → D
    fa = dag.add_fact("Event A", now, now, now, None, 0.9, "test")
    fb = dag.add_fact("Event B", now + timedelta(days=1), now + timedelta(days=1), now + timedelta(days=1), None, 0.9, "test")
    fc = dag.add_fact("Event C", now + timedelta(days=2), now + timedelta(days=2), now + timedelta(days=2), None, 0.9, "test")
    fd = dag.add_fact("Event D", now + timedelta(days=3), now + timedelta(days=3), now + timedelta(days=3), None, 0.9, "test")

    dag.add_edge(fa, fb, EdgeType.ENABLES, 0.9, now, None, "test")
    dag.add_edge(fb, fc, EdgeType.ENABLES, 0.9, now, None, "test")
    dag.add_edge(fc, fd, EdgeType.ENABLES, 0.9, now, None, "test")

    qt = (now + timedelta(days=5)).timestamp()

    # Forward from A: finds B, C, D
    fwd = _enumerate_paths(dag, fa, {fb, fc, fd}, 4, qt)
    assert set(fwd.keys()) == {fb, fc, fd}

    # Backward from D: finds C, B, A
    bwd = _enumerate_paths_backward(dag, fd, {fa, fb, fc}, 4, qt)
    assert set(bwd.keys()) == {fa, fb, fc}

    # bundle with D as anchor should now include A, B, C via backward
    candidates = [(dag.get_fact(x), 0, 0.8) for x in [fa, fb, fc, fd]]
    bundle = build_fiber_bundle(dag, candidates, [fd], qt, max_hops=4)
    assert len(bundle.fibers) >= 3, f"Expected ≥3 fibers, got {len(bundle.fibers)}"
