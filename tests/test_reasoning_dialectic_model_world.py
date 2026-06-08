from datetime import datetime, timezone

from llm_kosh.core.memory import init_cartridge
from llm_kosh.engine.reasoning import ReasoningEngine
from llm_kosh.engine.reasoning.causal_dag import EdgeType
from llm_kosh.engine.reasoning.convergent import ConvergentEngine
from llm_kosh.engine.reasoning.opposition import OppositionEngine
from llm_kosh.engine.reasoning.model_world import (
    ModelWorld,
    ModelWorldLink,
    ModelWorldNode,
    ModelWorldNodeKind,
)


def _now():
    return datetime(2026, 1, 1, tzinfo=timezone.utc)


def _engine(tmp_path):
    init_cartridge(tmp_path, "Dialectic Test")
    return ReasoningEngine(tmp_path)


def _incident_graph(engine):
    now = _now()
    a = engine.dag.add_fact("A: patch deployed to checkout service", now, now, now, None, 0.95, "test")
    b = engine.dag.add_fact("B: patch introduced memory leak", now, now, now, None, 0.90, "test")
    c = engine.dag.add_fact("C: checkout service crashed after saturation", now, now, now, None, 0.92, "test")
    alt = engine.dag.add_fact("Alternative: traffic spike also contributed to saturation", now, now, now, None, 0.72, "test")
    contra = engine.dag.add_fact("Contradiction: status report denied memory pressure", now, now, now, None, 0.70, "test")
    engine.dag.add_edge(a, b, EdgeType.CAUSES, 0.90, now, None, "observed")
    engine.dag.add_edge(b, c, EdgeType.CAUSES, 0.90, now, None, "observed")
    engine.add_edge_at(a, c, "INFERS", 0.45, now, established_by="inference", origin="INFERRED", role="COMPRESSED", derived_from=[])
    engine.dag.add_edge(alt, c, EdgeType.ENABLES, 0.62, now, None, "observed")
    engine.dag.add_edge(contra, b, EdgeType.CONTRADICTS, 0.80, now, None, "observed")
    engine._retrieval._build_resonance_index()
    return a, b, c, alt, contra


def test_convergent_engine_compresses_without_losing_provenance(tmp_path):
    engine = _engine(tmp_path)
    a, b, c, _alt, _contra = _incident_graph(engine)
    bundle = engine.explore(a, c, max_hops=3)

    converged = ConvergentEngine().converge(bundle)

    assert converged.primary_fact_id == c
    assert converged.has_answer
    assert converged.selected_path is not None
    assert converged.compression_candidates
    candidate = converged.compression_candidates[0]
    assert candidate.source_id == a
    assert candidate.target_id == c
    assert candidate.recommended_origin == "INFERRED"
    assert candidate.recommended_role == "COMPRESSED"
    assert "not discovered truth" in candidate.warning


def test_opposition_attacks_inferred_compressed_shortcut(tmp_path):
    engine = _engine(tmp_path)
    a, _b, c, _alt, _contra = _incident_graph(engine)
    bundle = engine.explore(a, c, max_hops=1)  # selects the direct inferred shortcut

    converged = ConvergentEngine().converge(bundle)
    opposed = OppositionEngine().oppose(converged, bundle, dag=engine.dag)

    assert opposed.challenged
    assert any(f.kind == "unproven_selected_edge" for f in opposed.findings)
    assert any("independent evidence" in q for q in opposed.falsification_questions)


def test_dialectic_query_runs_converge_oppose_reopen_loop(tmp_path):
    engine = _engine(tmp_path)
    _incident_graph(engine)

    result = engine.dialectic_query(
        "Why did checkout service crash after patch memory leak?",
        temporal_context=_now().isoformat(),
        depth=3,
    )

    assert result.converged.has_answer
    assert result.opposition.status in {
        "survived_initial_opposition",
        "challenged",
        "needs_evidence",
    }
    assert result.final_status in {
        "survived_opposition",
        "reopened_for_non_convergent_review",
        "needs_evidence",
        "challenged",
        "no_evidence",
    }
    assert "opposition_status" in result.synthesis


def test_model_world_records_dialectic_result_and_plans_million_nodes(tmp_path):
    engine = _engine(tmp_path)
    _incident_graph(engine)
    result = engine.dialectic_query(
        "Why did checkout service crash after patch memory leak?",
        temporal_context=_now().isoformat(),
        depth=3,
    )

    world = ModelWorld(target_nodes_per_partition=100_000)
    n1 = ModelWorldNode("fact.checkout", ModelWorldNodeKind.TEMPORAL_FACT, "checkout incident corpus")
    n2 = ModelWorldNode("hypothesis.rootcause", ModelWorldNodeKind.HYPOTHESIS, "patch caused outage")
    world.add_node(n1)
    world.add_node(n2)
    world.add_link(ModelWorldLink("fact.checkout", "hypothesis.rootcause", "SUPPORTS", confidence=0.8))
    dialectic_node = world.record_dialectic_result(result)

    assert dialectic_node in world.nodes
    plan = world.partition_plan(1_000_000)
    assert plan["recommended_partitions"] == 10
    stats = world.stats(target_total_nodes=1_000_000)
    assert stats.node_count == 3
    assert stats.kind_counts["MODEL"] == 1
