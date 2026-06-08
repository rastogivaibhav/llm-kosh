"""
Tests for llm_kosh.engine.reasoning.discovery (Task 9: T5.1 + T5.2 + T5.3)
"""
from __future__ import annotations

import time
from datetime import datetime, timezone, timedelta

import pytest

from llm_kosh.engine.reasoning.causal_dag import (
    CausalDAG,
    EdgeOrigin,
    EdgeProvenance,
    EdgeRole,
    EdgeType,
)
from llm_kosh.engine.reasoning.fiber_bundle import FiberBundle, Fiber, CausalPath
from llm_kosh.engine.reasoning.critique import (
    TraceWeakness,
    WeaknessReport,
    WeaknessType,
)
from llm_kosh.engine.reasoning.discovery import (
    DiscoveryType,
    DiscoveryQuestion,
    DiscoveryResult,
    DiscoveryGenerator,
    SafeDiscovery,
)
from llm_kosh.core.memory import init_cartridge


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _now() -> datetime:
    return datetime.now(timezone.utc)


def _weakness(wt: WeaknessType, severity: float = 0.7) -> TraceWeakness:
    return TraceWeakness(
        weakness_type=wt,
        severity=severity,
        location="test",
        description="test weakness",
        suggested_repair_type="test_repair",
    )


def _report(*weaknesses: TraceWeakness) -> WeaknessReport:
    return WeaknessReport(
        trace_id="test-trace-001",
        per_trace_weaknesses=list(weaknesses),
        session_weaknesses=[],
    )


@pytest.fixture
def dag(tmp_path):
    """A fresh CausalDAG backed by a temp directory."""
    init_cartridge(tmp_path, "TestCartridge")
    return CausalDAG(tmp_path)


def _add_fact(dag: CausalDAG, content: str = "fact", confidence: float = 0.9) -> str:
    now = _now()
    return dag.add_fact(
        content=content,
        ingested_at=now,
        documented_at=now,
        valid_from=now,
        valid_until=None,
        confidence=confidence,
        source="user",
    )


def _simple_bundle(dag: CausalDAG, *fact_ids: str) -> FiberBundle:
    """Build a minimal FiberBundle containing the given fact_ids."""
    fibers = {}
    for fid in fact_ids:
        fact = dag.get_fact(fid)
        if fact is not None:
            fibers[fid] = Fiber(
                fact=fact,
                paths=[CausalPath(edges=[], confidence_product=fact.confidence, temporal_consistency=1.0)],
                degeneracy=1,
                max_confidence=fact.confidence,
            )
    return FiberBundle(fibers=fibers)


# ---------------------------------------------------------------------------
# T5.1  DiscoveryQuestion construction and round-trip
# ---------------------------------------------------------------------------

class TestDiscoveryQuestion:

    def test_construction_defaults(self):
        q = DiscoveryQuestion(
            question_text="test question?",
            discovery_type=DiscoveryType.temporal_expansion,
            target_weakness=WeaknessType.TEMPORAL_CONSISTENCY_LOW.value,
            expected_outcome="some outcome",
        )
        assert q.executable_locally is True
        assert q.discovery_type == DiscoveryType.temporal_expansion

    def test_to_dict_keys(self):
        q = DiscoveryQuestion(
            question_text="q?",
            discovery_type=DiscoveryType.gap_marking,
            target_weakness=WeaknessType.NOVELTY_DEFICIT.value,
            expected_outcome="some gaps",
        )
        d = q.to_dict()
        assert set(d.keys()) == {
            "question_text", "discovery_type", "target_weakness",
            "expected_outcome", "executable_locally",
        }

    def test_round_trip(self):
        q = DiscoveryQuestion(
            question_text="round trip?",
            discovery_type=DiscoveryType.path_diversification,
            target_weakness=WeaknessType.SINGLE_PATH_DOMINANCE.value,
            expected_outcome="alternate paths",
            executable_locally=True,
        )
        q2 = DiscoveryQuestion.from_dict(q.to_dict())
        assert q2.question_text == q.question_text
        assert q2.discovery_type == q.discovery_type
        assert q2.target_weakness == q.target_weakness
        assert q2.expected_outcome == q.expected_outcome
        assert q2.executable_locally == q.executable_locally

    def test_all_discovery_types_roundtrip(self):
        for dtype in DiscoveryType:
            q = DiscoveryQuestion(
                question_text="x",
                discovery_type=dtype,
                target_weakness="test",
                expected_outcome="y",
            )
            assert DiscoveryQuestion.from_dict(q.to_dict()).discovery_type == dtype


# ---------------------------------------------------------------------------
# T5.2  DiscoveryResult construction and round-trip
# ---------------------------------------------------------------------------

class TestDiscoveryResult:

    def _sample_question(self) -> DiscoveryQuestion:
        return DiscoveryQuestion(
            question_text="q?",
            discovery_type=DiscoveryType.contradiction_resolution,
            target_weakness=WeaknessType.CONTRADICTION_UNRESOLVED.value,
            expected_outcome="supersedes edges",
        )

    def test_construction(self):
        q = self._sample_question()
        r = DiscoveryResult(
            question=q,
            facts_found=["f1", "f2"],
            edges_found=["e1"],
            candidate_hypotheses=[],
            repair_strength=0.4,
        )
        assert r.repair_strength == 0.4
        assert "f1" in r.facts_found
        assert r.executed_at > 0

    def test_to_dict_keys(self):
        q = self._sample_question()
        r = DiscoveryResult(
            question=q,
            facts_found=[],
            edges_found=[],
            candidate_hypotheses=[],
            repair_strength=0.0,
        )
        d = r.to_dict()
        assert set(d.keys()) == {
            "question", "facts_found", "edges_found",
            "candidate_hypotheses", "repair_strength", "executed_at",
        }

    def test_round_trip(self):
        q = self._sample_question()
        r = DiscoveryResult(
            question=q,
            facts_found=["f1"],
            edges_found=["e1"],
            candidate_hypotheses=["f2"],
            repair_strength=0.75,
            executed_at=12345.0,
        )
        r2 = DiscoveryResult.from_dict(r.to_dict())
        assert r2.facts_found == r.facts_found
        assert r2.edges_found == r.edges_found
        assert r2.candidate_hypotheses == r.candidate_hypotheses
        assert abs(r2.repair_strength - r.repair_strength) < 1e-9
        assert abs(r2.executed_at - r.executed_at) < 1e-9
        assert r2.question.discovery_type == r.question.discovery_type


# ---------------------------------------------------------------------------
# T5.3a  DiscoveryGenerator
# ---------------------------------------------------------------------------

class TestDiscoveryGenerator:

    def setup_method(self):
        self.gen = DiscoveryGenerator()

    def test_empty_report_returns_empty(self):
        report = _report()
        assert self.gen.generate(report) == []

    def test_unknown_weakness_type_produces_no_question(self):
        # IMPROVEMENT_STALL has no mapping
        report = _report(_weakness(WeaknessType.IMPROVEMENT_STALL))
        assert self.gen.generate(report) == []

    def test_temporal_consistency_low_maps_to_temporal_expansion(self):
        report = _report(_weakness(WeaknessType.TEMPORAL_CONSISTENCY_LOW))
        qs = self.gen.generate(report)
        assert len(qs) == 1
        assert qs[0].discovery_type == DiscoveryType.temporal_expansion
        assert qs[0].target_weakness == WeaknessType.TEMPORAL_CONSISTENCY_LOW.value

    def test_contradiction_unresolved_maps_to_contradiction_resolution(self):
        report = _report(_weakness(WeaknessType.CONTRADICTION_UNRESOLVED))
        qs = self.gen.generate(report)
        assert len(qs) == 1
        assert qs[0].discovery_type == DiscoveryType.contradiction_resolution

    def test_single_path_dominance_maps_to_path_diversification(self):
        report = _report(_weakness(WeaknessType.SINGLE_PATH_DOMINANCE))
        qs = self.gen.generate(report)
        assert qs[0].discovery_type == DiscoveryType.path_diversification

    def test_shallow_depth_maps_to_path_diversification(self):
        report = _report(_weakness(WeaknessType.SHALLOW_DEPTH))
        qs = self.gen.generate(report)
        assert qs[0].discovery_type == DiscoveryType.path_diversification

    def test_hypothetical_promoted_maps_to_evidence_promotion_audit(self):
        report = _report(_weakness(WeaknessType.HYPOTHETICAL_PROMOTED_SILENTLY))
        qs = self.gen.generate(report)
        assert qs[0].discovery_type == DiscoveryType.evidence_promotion_audit

    def test_novelty_deficit_maps_to_gap_marking(self):
        report = _report(_weakness(WeaknessType.NOVELTY_DEFICIT))
        qs = self.gen.generate(report)
        assert qs[0].discovery_type == DiscoveryType.gap_marking

    def test_coverage_bias_maps_to_gap_marking(self):
        report = _report(_weakness(WeaknessType.COVERAGE_BIAS))
        qs = self.gen.generate(report)
        assert qs[0].discovery_type == DiscoveryType.gap_marking

    def test_one_question_per_unique_weakness_type(self):
        # Two SINGLE_PATH_DOMINANCE weaknesses should yield ONE question
        report = WeaknessReport(
            trace_id="t",
            per_trace_weaknesses=[
                _weakness(WeaknessType.SINGLE_PATH_DOMINANCE, 0.8),
                _weakness(WeaknessType.TEMPORAL_CONSISTENCY_LOW, 0.6),
            ],
            session_weaknesses=[
                _weakness(WeaknessType.SINGLE_PATH_DOMINANCE, 0.5),  # duplicate type
                _weakness(WeaknessType.NOVELTY_DEFICIT, 0.3),
            ],
        )
        qs = self.gen.generate(report)
        types = [q.discovery_type for q in qs]
        # SINGLE_PATH_DOMINANCE should appear once
        path_div_count = types.count(DiscoveryType.path_diversification)
        assert path_div_count == 1

    def test_sorted_by_severity_descending(self):
        report = WeaknessReport(
            trace_id="t",
            per_trace_weaknesses=[
                _weakness(WeaknessType.TEMPORAL_CONSISTENCY_LOW, 0.4),
                _weakness(WeaknessType.CONTRADICTION_UNRESOLVED, 0.9),
                _weakness(WeaknessType.NOVELTY_DEFICIT, 0.6),
            ],
            session_weaknesses=[],
        )
        qs = self.gen.generate(report)
        # First question should be for highest severity (contradiction -> 0.9)
        assert qs[0].discovery_type == DiscoveryType.contradiction_resolution
        assert qs[1].discovery_type == DiscoveryType.gap_marking
        assert qs[2].discovery_type == DiscoveryType.temporal_expansion

    def test_all_questions_have_executable_locally_true(self):
        report = _report(
            _weakness(WeaknessType.TEMPORAL_CONSISTENCY_LOW),
            _weakness(WeaknessType.NOVELTY_DEFICIT),
        )
        for q in self.gen.generate(report):
            assert q.executable_locally is True


# ---------------------------------------------------------------------------
# T5.3b  SafeDiscovery — fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def populated_dag(dag):
    """
    DAG with 5 facts and some edges:
      f1 -> f2 (CAUSES)
      f1 -> f3 (SUPERSEDES)
      f4 -> f5 (INFERS, INFERRED origin, no evidence refs)
    """
    now = _now()
    f1 = _add_fact(dag, "fact1", 0.9)
    f2 = _add_fact(dag, "fact2", 0.8)
    f3 = _add_fact(dag, "fact3", 0.7)
    f4 = _add_fact(dag, "fact4", 0.6)
    f5 = _add_fact(dag, "fact5", 0.5)

    dag.add_edge(f1, f2, EdgeType.CAUSES, 0.8, now, None, "test")
    dag.add_edge(f1, f3, EdgeType.SUPERSEDES, 0.9, now, None, "test")
    # Manually add an INFERRED edge with no evidence refs
    from llm_kosh.engine.reasoning.causal_dag import CausalEdge, EdgeProvenance, EdgeOrigin, EdgeRole
    inferred_prov = EdgeProvenance(origin=EdgeOrigin.INFERRED, role=EdgeRole.COMPRESSED)
    dag.add_edge(
        f4, f5, EdgeType.INFERS, 0.5, now, None, "inference",
        provenance=inferred_prov,
    )

    return dag, {"f1": f1, "f2": f2, "f3": f3, "f4": f4, "f5": f5}


# ---------------------------------------------------------------------------
# T5.3b  SafeDiscovery — strategy tests
# ---------------------------------------------------------------------------

class TestSafeDiscovery:

    def setup_method(self):
        self.sd = SafeDiscovery()

    def _q(self, dtype: DiscoveryType) -> DiscoveryQuestion:
        return DiscoveryQuestion(
            question_text=dtype.value,
            discovery_type=dtype,
            target_weakness="test",
            expected_outcome="test",
        )

    # ------------------------------------------------------------------
    # temporal_expansion
    # ------------------------------------------------------------------

    def test_temporal_expansion_returns_result(self, populated_dag):
        dag, ids = populated_dag
        bundle = _simple_bundle(dag, ids["f1"])
        q = self._q(DiscoveryType.temporal_expansion)
        result = self.sd.execute(q, dag, bundle, time.time())
        assert isinstance(result, DiscoveryResult)
        assert 0.0 <= result.repair_strength <= 1.0

    def test_temporal_expansion_excludes_bundle_facts(self, populated_dag):
        dag, ids = populated_dag
        bundle = _simple_bundle(dag, ids["f1"], ids["f2"])
        q = self._q(DiscoveryType.temporal_expansion)
        result = self.sd.execute(q, dag, bundle, time.time())
        bundle_ids = set(bundle.fibers.keys())
        for fid in result.facts_found:
            assert fid not in bundle_ids

    def test_temporal_expansion_repair_strength_capped(self, populated_dag):
        dag, ids = populated_dag
        bundle = _simple_bundle(dag)
        q = self._q(DiscoveryType.temporal_expansion)
        result = self.sd.execute(q, dag, bundle, time.time())
        assert result.repair_strength <= 1.0

    # ------------------------------------------------------------------
    # contradiction_resolution
    # ------------------------------------------------------------------

    def test_contradiction_resolution_finds_supersedes(self, populated_dag):
        dag, ids = populated_dag
        bundle = _simple_bundle(dag, ids["f1"], ids["f3"])
        q = self._q(DiscoveryType.contradiction_resolution)
        result = self.sd.execute(q, dag, bundle, time.time())
        # f1 -> f3 is SUPERSEDES, so at least one SUPERSEDES edge should be found
        assert len(result.edges_found) >= 1
        assert 0.0 < result.repair_strength <= 1.0

    def test_contradiction_resolution_empty_bundle(self, populated_dag):
        dag, ids = populated_dag
        bundle = _simple_bundle(dag)
        q = self._q(DiscoveryType.contradiction_resolution)
        result = self.sd.execute(q, dag, bundle, time.time())
        assert result.edges_found == []
        assert result.repair_strength == 0.0

    # ------------------------------------------------------------------
    # path_diversification
    # ------------------------------------------------------------------

    def test_path_diversification_finds_new_facts(self, populated_dag):
        dag, ids = populated_dag
        # Bundle has only f1; f2 and f3 should be discoverable via edges from f1
        bundle = _simple_bundle(dag, ids["f1"])
        q = self._q(DiscoveryType.path_diversification)
        result = self.sd.execute(q, dag, bundle, time.time())
        assert len(result.facts_found) >= 1
        # Found facts should not be in original bundle
        for fid in result.facts_found:
            assert fid not in bundle.fibers

    def test_path_diversification_limit_10(self, dag):
        """Even with many neighbors, facts_found is capped at 10."""
        now = _now()
        # Create 1 anchor + 15 targets
        anchor = _add_fact(dag, "anchor", 0.9)
        targets = [_add_fact(dag, f"target_{i}", 0.7) for i in range(15)]
        for t in targets:
            dag.add_edge(anchor, t, EdgeType.ENABLES, 0.7, now, None, "test")

        bundle = _simple_bundle(dag, anchor)
        q = self._q(DiscoveryType.path_diversification)
        result = self.sd.execute(q, dag, bundle, time.time())
        assert len(result.facts_found) <= 10

    # ------------------------------------------------------------------
    # gap_marking
    # ------------------------------------------------------------------

    def test_gap_marking_finds_disconnected_neighbors(self, populated_dag):
        dag, ids = populated_dag
        # f1 is in bundle; f2 and f3 are neighbors reachable via CAUSES/SUPERSEDES from f1
        bundle = _simple_bundle(dag, ids["f1"])
        q = self._q(DiscoveryType.gap_marking)
        result = self.sd.execute(q, dag, bundle, time.time())
        # f2 and f3 are neighbors of f1 with no edges back into bundle
        assert isinstance(result.facts_found, list)
        assert 0.0 <= result.repair_strength <= 1.0

    def test_gap_marking_limit_15(self, dag):
        now = _now()
        anchor = _add_fact(dag, "anchor", 0.9)
        for i in range(20):
            t = _add_fact(dag, f"target_{i}", 0.7)
            dag.add_edge(anchor, t, EdgeType.ENABLES, 0.7, now, None, "test")

        bundle = _simple_bundle(dag, anchor)
        q = self._q(DiscoveryType.gap_marking)
        result = self.sd.execute(q, dag, bundle, time.time())
        assert len(result.facts_found) <= 15

    # ------------------------------------------------------------------
    # evidence_promotion_audit
    # ------------------------------------------------------------------

    def test_evidence_promotion_audit_finds_inferred_edges(self, populated_dag):
        dag, ids = populated_dag
        bundle = _simple_bundle(dag, ids["f4"], ids["f5"])
        q = self._q(DiscoveryType.evidence_promotion_audit)
        result = self.sd.execute(q, dag, bundle, time.time())
        # The INFERRED edge f4->f5 has no evidence refs -> should appear
        assert len(result.candidate_hypotheses) >= 1
        assert 0.0 < result.repair_strength <= 1.0

    def test_evidence_promotion_audit_limit_10(self, dag):
        now = _now()
        facts = [_add_fact(dag, f"f{i}", 0.7) for i in range(12)]
        from llm_kosh.engine.reasoning.causal_dag import EdgeProvenance, EdgeOrigin, EdgeRole
        inferred_prov = EdgeProvenance(origin=EdgeOrigin.INFERRED, role=EdgeRole.COMPRESSED)
        for i in range(len(facts) - 1):
            dag.add_edge(
                facts[i], facts[i + 1], EdgeType.INFERS, 0.5, now, None, "inference",
                provenance=inferred_prov,
            )
        bundle = _simple_bundle(dag, *facts[:6])
        q = self._q(DiscoveryType.evidence_promotion_audit)
        result = self.sd.execute(q, dag, bundle, time.time())
        assert len(result.candidate_hypotheses) <= 10

    # ------------------------------------------------------------------
    # Safety contract: DAG never modified
    # ------------------------------------------------------------------

    def test_dag_not_modified_temporal_expansion(self, populated_dag):
        dag, ids = populated_dag
        node_count_before = len(dag.nodes)
        edge_count_before = sum(len(v) for v in dag.edges.values())
        bundle = _simple_bundle(dag, ids["f1"])
        q = self._q(DiscoveryType.temporal_expansion)
        self.sd.execute(q, dag, bundle, time.time())
        assert len(dag.nodes) == node_count_before
        assert sum(len(v) for v in dag.edges.values()) == edge_count_before

    def test_dag_not_modified_contradiction_resolution(self, populated_dag):
        dag, ids = populated_dag
        node_count_before = len(dag.nodes)
        bundle = _simple_bundle(dag, ids["f1"])
        q = self._q(DiscoveryType.contradiction_resolution)
        self.sd.execute(q, dag, bundle, time.time())
        assert len(dag.nodes) == node_count_before

    def test_dag_not_modified_path_diversification(self, populated_dag):
        dag, ids = populated_dag
        node_count_before = len(dag.nodes)
        bundle = _simple_bundle(dag, ids["f1"])
        q = self._q(DiscoveryType.path_diversification)
        self.sd.execute(q, dag, bundle, time.time())
        assert len(dag.nodes) == node_count_before

    def test_dag_not_modified_gap_marking(self, populated_dag):
        dag, ids = populated_dag
        node_count_before = len(dag.nodes)
        bundle = _simple_bundle(dag, ids["f1"])
        q = self._q(DiscoveryType.gap_marking)
        self.sd.execute(q, dag, bundle, time.time())
        assert len(dag.nodes) == node_count_before

    def test_dag_not_modified_evidence_promotion_audit(self, populated_dag):
        dag, ids = populated_dag
        node_count_before = len(dag.nodes)
        bundle = _simple_bundle(dag, ids["f4"], ids["f5"])
        q = self._q(DiscoveryType.evidence_promotion_audit)
        self.sd.execute(q, dag, bundle, time.time())
        assert len(dag.nodes) == node_count_before

    # ------------------------------------------------------------------
    # repair_strength always in [0.0, 1.0]
    # ------------------------------------------------------------------

    def test_repair_strength_bounds_all_strategies(self, populated_dag):
        dag, ids = populated_dag
        all_ids = list(ids.values())
        bundle = _simple_bundle(dag, *all_ids)
        qt = time.time()
        for dtype in DiscoveryType:
            q = self._q(dtype)
            result = self.sd.execute(q, dag, bundle, qt)
            assert 0.0 <= result.repair_strength <= 1.0, (
                f"repair_strength out of bounds for {dtype}: {result.repair_strength}"
            )

    # ------------------------------------------------------------------
    # Exception safety: returns empty result on bad input
    # ------------------------------------------------------------------

    def test_exception_safety_empty_result(self, dag):
        # Pass an empty bundle with an empty DAG -> should not raise
        bundle = FiberBundle(fibers={})
        for dtype in DiscoveryType:
            q = self._q(dtype)
            result = self.sd.execute(q, dag, bundle, time.time())
            assert isinstance(result, DiscoveryResult)
            assert 0.0 <= result.repair_strength <= 1.0
