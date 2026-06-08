from datetime import datetime, timezone

import pytest

from llm_kosh.core.memory import init_cartridge
from llm_kosh.engine.reasoning import ReasoningEngine
from llm_kosh.engine.reasoning.causal_dag import (
    EdgeOrigin,
    EdgeRole,
    EdgeType,
    EvidenceRef,
    CausalDAG,
)
from llm_kosh.engine.reasoning.fiber_bundle import _enumerate_paths
from llm_kosh.engine.reasoning.lyapunov_critic import LyapunovCritic
from llm_kosh.engine.reasoning.fiber_bundle import FiberBundle


def _now():
    return datetime(2026, 1, 1, tzinfo=timezone.utc)


def _dag(tmp_path):
    init_cartridge(tmp_path, "Provenance Test")
    return CausalDAG(tmp_path)


def test_invalid_edge_rejects_missing_facts(tmp_path):
    dag = _dag(tmp_path)
    now = _now()
    with pytest.raises(ValueError):
        dag.add_edge("missing-a", "missing-b", EdgeType.CAUSES, 0.8, now, None, "test")


def test_inferred_shortcut_can_be_reinforced_without_discovery_promotion(tmp_path):
    dag = _dag(tmp_path)
    now = _now()
    a = dag.add_fact("A: patch deployed", now, now, now, None, 0.9, "user")
    b = dag.add_fact("B: memory leak introduced", now, now, now, None, 0.9, "user")
    c = dag.add_fact("C: service crashed", now, now, now, None, 0.9, "user")
    dag.add_edge(a, b, EdgeType.CAUSES, 0.9, now, None, "observed")
    dag.add_edge(b, c, EdgeType.CAUSES, 0.9, now, None, "observed")
    shortcut = dag.add_edge(
        a,
        c,
        EdgeType.INFERS,
        0.4,
        now,
        None,
        "inference",
    )

    edge = dag.get_edge(shortcut)
    assert edge.provenance.origin == EdgeOrigin.INFERRED
    assert edge.provenance.role == EdgeRole.COMPRESSED

    dag.reinforce_edge(shortcut, used_at=now)
    edge = dag.get_edge(shortcut)
    assert edge.provenance.origin == EdgeOrigin.INFERRED
    assert edge.provenance.promotion_status == "reinforced_not_discovered"
    assert edge.provenance.reinforcement.count == 1
    assert edge.confidence == 0.4


def test_discovery_promotion_requires_evidence(tmp_path):
    dag = _dag(tmp_path)
    now = _now()
    a = dag.add_fact("A", now, now, now, None, 0.9, "user")
    c = dag.add_fact("C", now, now, now, None, 0.9, "user")
    eid = dag.add_edge(a, c, EdgeType.INFERS, 0.4, now, None, "inference")

    with pytest.raises(ValueError):
        dag.promote_edge_to_discovered(eid, [])

    dag.promote_edge_to_discovered(eid, [EvidenceRef(source_id="postmortem-1", observed_at=now)])
    edge = dag.get_edge(eid)
    assert edge.provenance.origin == EdgeOrigin.DISCOVERED
    assert edge.provenance.promotion_status == "promoted_by_evidence"
    assert edge.confidence >= 0.75


def test_empty_bundle_is_no_evidence_abstention(tmp_path):
    dag = _dag(tmp_path)
    result = LyapunovCritic(dag).evaluate(FiberBundle(fibers={}))
    assert result.status == "no_evidence"
    assert result.abstain is True


def test_hyperedge_requires_all_sources_in_path_context(tmp_path):
    dag = _dag(tmp_path)
    now = _now()
    a = dag.add_fact("A: condition one", now, now, now, None, 0.9, "user")
    b = dag.add_fact("B: condition two", now, now, now, None, 0.9, "user")
    c = dag.add_fact("C: joint consequence", now, now, now, None, 0.9, "user")
    dag.add_hyperedge({a, b}, c, EdgeType.CAUSES, 0.8, now, None)

    # Starting from only A should not activate A ∧ B -> C.
    paths = _enumerate_paths(dag, a, {c}, max_hops=2, query_time=now.timestamp())
    assert c not in paths

    # Once B is on the active path, the hyperedge can fire.
    dag.add_edge(a, b, EdgeType.ENABLES, 0.9, now, None, "observed")
    paths = _enumerate_paths(dag, a, {c}, max_hops=3, query_time=now.timestamp())
    assert c in paths


def test_reasoning_mode_empirical_filters_unproven_analogy(tmp_path):
    init_cartridge(tmp_path, "Mode Test")
    engine = ReasoningEngine(tmp_path)
    now = _now()
    a = engine.dag.add_fact("database pressure resembles biological selection", now, now, now, None, 0.9, "user")
    c = engine.dag.add_fact("architecture adapts under pressure", now, now, now, None, 0.9, "user")
    engine.dag.add_edge(a, c, EdgeType.ANALOGY, 0.5, now, None, "theory")

    balanced = engine.query("pressure adapts architecture", temporal_context=now.isoformat(), depth=2, reasoning_mode="BALANCED")
    empirical = engine.query("pressure adapts architecture", temporal_context=now.isoformat(), depth=2, reasoning_mode="EMPIRICAL")

    assert balanced.reasoning_mode == "BALANCED"
    assert empirical.reasoning_mode == "EMPIRICAL"
    # Empirical mode should not preserve ungrounded analogical paths as evidence.
    assert all(
        all(edge.provenance.role != EdgeRole.ANALOGICAL for edge in path.edges)
        for fiber in empirical.bundle.fibers.values()
        for path in fiber.paths
    )
