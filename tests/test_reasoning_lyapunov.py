import pytest
from datetime import datetime, timezone
from llm_kosh.core.memory import init_cartridge
from llm_kosh.engine.reasoning.causal_dag import CausalDAG, EdgeType, TemporalFact
from llm_kosh.engine.reasoning.fiber_bundle import FiberBundle, Fiber, CausalPath, CausalEdge
from llm_kosh.engine.reasoning.lyapunov_critic import LyapunovCritic, StabilityResult

def _now():
    return datetime.now(timezone.utc)

def _make_dag(tmp_path):
    init_cartridge(tmp_path, "Test")
    return CausalDAG(tmp_path)

def _make_edge(source_id, target_id, edge_type=EdgeType.CAUSES, conf=0.8):
    now = _now()
    return CausalEdge(id="e-test", source_id=source_id, target_id=target_id,
                      edge_type=edge_type, confidence=conf,
                      valid_from=now, valid_until=None, established_by="test")

def test_stability_result_fields():
    r = StabilityResult(score=0.8, status="stable",
                        dimensions={"temporal_consistency": 1.0, "contradiction_score": 0.0,
                                    "path_diversity": 0.8, "degeneracy": 0.9},
                        implicated_facts=[])
    assert r.score == 0.8
    assert r.status == "stable"

def test_empty_bundle_abstains(tmp_path):
    dag = _make_dag(tmp_path)
    critic = LyapunovCritic(dag)
    bundle = FiberBundle(fibers={})
    result = critic.evaluate(bundle)
    assert result.status == "no_evidence"
    assert result.abstain is True
    assert result.score == 0.0

def test_single_path_bundle_stable(tmp_path):
    dag = _make_dag(tmp_path)
    now = _now()
    fa = dag.add_fact("A", now, now, now, None, 0.9, "user")
    fb = dag.add_fact("B", now, now, now, None, 0.9, "user")
    fact_b = dag.get_fact(fb)
    edge = _make_edge(fa, fb)
    path = CausalPath(edges=[edge], confidence_product=0.8, temporal_consistency=1.0)
    fiber = Fiber(fact=fact_b, paths=[path], degeneracy=1, max_confidence=0.8)
    bundle = FiberBundle(fibers={fb: fiber})
    critic = LyapunovCritic(dag)
    result = critic.evaluate(bundle)
    assert result.status in ("stable", "marginal")

def test_contradiction_lowers_score(tmp_path):
    dag = _make_dag(tmp_path)
    now = _now()
    fa = dag.add_fact("A", now, now, now, None, 0.9, "user")
    fb = dag.add_fact("B", now, now, now, None, 0.9, "user")
    # Add contradiction edge
    dag.add_edge(fa, fb, EdgeType.CONTRADICTS, 1.0, now, None, "test")
    fact_a = dag.get_fact(fa)
    fact_b = dag.get_fact(fb)
    path_a = CausalPath(edges=[], confidence_product=1.0, temporal_consistency=1.0)
    path_b = CausalPath(edges=[], confidence_product=1.0, temporal_consistency=1.0)
    bundle = FiberBundle(fibers={
        fa: Fiber(fact=fact_a, paths=[path_a], degeneracy=1, max_confidence=1.0),
        fb: Fiber(fact=fact_b, paths=[path_b], degeneracy=1, max_confidence=1.0),
    })
    critic = LyapunovCritic(dag)
    result = critic.evaluate(bundle)
    assert result.dimensions["contradiction_score"] > 0.0

def test_thresholds_configurable(tmp_path):
    dag = _make_dag(tmp_path)
    critic = LyapunovCritic(dag, stable_threshold=0.9, unstable_threshold=0.6)
    bundle = FiberBundle(fibers={})
    result = critic.evaluate(bundle)
    # Empty bundle is now an explicit abstention/no-evidence state.
    assert result.status == "no_evidence"
    assert result.abstain is True
