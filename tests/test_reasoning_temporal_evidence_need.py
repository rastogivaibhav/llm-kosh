from __future__ import annotations

from datetime import datetime, timezone

from llm_kosh.engine.reasoning import ReasoningEngine
from llm_kosh.engine.reasoning.causal_dag import EdgeType
from llm_kosh.engine.reasoning.temporal_evidence import (
    TemporalConstraint,
    TemporalEvidenceEngine,
    TemporalSource,
    TemporalStatus,
)


def dt(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def test_exact_temporal_windows_are_required_for_supersession(tmp_path):
    """The software must distinguish what was true at different query times."""
    engine = ReasoningEngine(tmp_path)
    old_policy = engine.ingest(
        "Policy v1: remote work is allowed for the team.",
        documented_at=dt("2026-02-01T00:00:00Z"),
        valid_from=dt("2026-02-01T00:00:00Z"),
        valid_until=dt("2026-04-01T00:00:00Z"),
        confidence=0.9,
        causal_edges=[],
    )
    new_policy = engine.ingest(
        "Policy v2: remote work is not allowed for the team.",
        documented_at=dt("2026-04-01T00:00:00Z"),
        valid_from=dt("2026-04-01T00:00:00Z"),
        valid_until=None,
        confidence=0.95,
        causal_edges=[],
    )
    engine.add_edge_at(
        new_policy,
        old_policy,
        "SUPERSEDES",
        0.95,
        valid_from=dt("2026-04-01T00:00:00Z"),
        origin="OBSERVED",
        role="MECHANISTIC",
    )

    feb = engine.query("remote work allowed policy", "2026-02-15T00:00:00Z")
    may = engine.query("remote work allowed policy", "2026-05-15T00:00:00Z")

    assert old_policy in feb.bundle.fibers
    assert new_policy not in feb.bundle.fibers
    assert new_policy in may.bundle.fibers
    assert old_policy not in may.bundle.fibers


def test_timestamp_ablation_loses_temporal_truth(tmp_path):
    """If all facts are given the same fallback time, the system cannot know old vs new truth."""
    engine = ReasoningEngine(tmp_path)
    fallback = dt("2026-06-01T00:00:00Z")
    old_policy = engine.ingest(
        "Policy v1: remote work is allowed for the team.",
        documented_at=fallback,
        valid_from=fallback,
        valid_until=None,
        confidence=0.9,
        causal_edges=[],
    )
    new_policy = engine.ingest(
        "Policy v2: remote work is not allowed for the team.",
        documented_at=fallback,
        valid_from=fallback,
        valid_until=None,
        confidence=0.95,
        causal_edges=[],
    )

    feb = engine.query("remote work allowed policy", "2026-02-15T00:00:00Z")
    jun = engine.query("remote work allowed policy", "2026-06-15T00:00:00Z")

    # In February no fact is valid because both were artificially placed in June.
    assert feb.stability.status == "no_evidence"
    # In June both conflicting-looking facts can appear because no validity window separates them.
    assert old_policy in jun.bundle.fibers and new_policy in jun.bundle.fibers


def test_temporal_evidence_engine_detects_non_timestamp_time_signals():
    tee = TemporalEvidenceEngine()

    exact = tee.infer("Rollback was completed on 12 May 2026 after the leak was detected.")
    relative = tee.infer(
        "The rollback happened after the memory leak was detected.",
        fact_id="rollback",
        constraints=[TemporalConstraint("leak", "BEFORE", "rollback", 0.8, TemporalSource.CAUSAL_INFERENCE)],
    )
    versioned = tee.infer("Design v0.3 supersedes the earlier draft and changes the ingestion API.")
    unknown = tee.infer("This architecture is interesting and may help agents think better.")

    assert exact.status == TemporalStatus.EXACT
    assert relative.status == TemporalStatus.RELATIVE
    assert relative.usable_for_ordering()
    assert versioned.status == TemporalStatus.VERSIONED
    assert unknown.status == TemporalStatus.UNKNOWN
    assert unknown.should_abstain_for_time_sensitive_query()


def test_causal_edges_create_order_constraints_without_exact_timestamps(tmp_path):
    engine = ReasoningEngine(tmp_path)
    t = dt("2026-06-01T00:00:00Z")
    a = engine.ingest("Config file expanded beyond parser limit.", t, t, None, 0.9, [])
    b = engine.ingest("Parser failed while reading generated configuration.", t, t, None, 0.9, [])
    c = engine.ingest("Service degraded after the parser failed.", t, t, None, 0.9, [])
    engine.add_edge_at(a, b, "CAUSES", 0.8, t, origin="OBSERVED", role="MECHANISTIC")
    engine.add_edge_at(b, c, "CAUSES", 0.85, t, origin="OBSERVED", role="MECHANISTIC")

    tee = TemporalEvidenceEngine()
    constraints = tee.infer_constraints_from_edges(engine.dag)

    assert any(x.subject_id == a and x.relation == "BEFORE" and x.object_id == b for x in constraints)
    assert any(x.subject_id == b and x.relation == "BEFORE" and x.object_id == c for x in constraints)


def test_temporal_audit_flags_missing_or_collapsed_time(tmp_path):
    engine = ReasoningEngine(tmp_path)
    fallback = dt("2026-06-01T00:00:00Z")
    engine.dag.add_fact("Untimed design note about memory reasoning.", fallback, fallback, fallback, None, 0.9, "test")
    engine.dag.add_fact("v0.2 changes retrieval ordering after the first test run.", fallback, fallback, fallback, None, 0.9, "test")

    audit = TemporalEvidenceEngine().audit_dag(engine.dag)

    assert audit.total_facts == 2
    assert audit.unknown >= 1
    assert audit.time_dependency_score < 1.0
    assert audit.risk_flags or audit.recommendations
