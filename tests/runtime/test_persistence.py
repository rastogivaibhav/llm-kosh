from __future__ import annotations

from llm_kosh.company_brain.models import (
    EvidenceInput,
    EvidenceReference,
    MemoryInput,
    Principal,
)
from llm_kosh.company_brain.store import CompanyBrainStore
from llm_kosh.runtime import (
    AdmissionDecision,
    AdmissionEngine,
    ConflictSignals,
    ConflictState,
    EvidenceSignals,
    MemoryProposal,
)
from llm_kosh.runtime.persistence import RUNTIME_SCHEMA_VERSION, RuntimeStore


def _candidate(root):
    store = CompanyBrainStore(root)
    evidence_id = store.put_evidence(EvidenceInput(
        source_type="repository",
        source_locator="repo://architecture.md#messaging",
        source_native_id="architecture-messaging-v1",
        content=b"Atlas moved from Redis queues to Pub/Sub for managed fan-out.",
        classification="internal",
    ))
    memory_id = store.add_memory(MemoryInput(
        memory_type="decision",
        title="Atlas messaging platform",
        statement="Project Atlas uses Google Pub/Sub for managed fan-out.",
        rationale="Architecture evidence records the migration decision.",
        project_id="atlas",
        lifecycle="candidate",
        confidence=0.5,
        importance=0.8,
        classification="internal",
        source_native_id="atlas-messaging-candidate",
        evidence=[EvidenceReference(
            evidence_id=evidence_id,
            locator="architecture.md#messaging",
            support="direct",
        )],
    ))
    return store, evidence_id, memory_id


def _proposal(evidence_id):
    return MemoryProposal(
        memory_type="decision",
        title="Atlas messaging platform",
        statement="Project Atlas uses Google Pub/Sub for managed fan-out.",
        evidence_ids=[evidence_id],
        source_type="repository",
        project_id="atlas",
        classification="internal",
        subject="project:atlas.messaging",
        predicate="implementation",
        object_value="pubsub",
    )


def test_dry_run_and_reads_do_not_initialize_database(tmp_path) -> None:
    runtime = RuntimeStore(tmp_path)
    assert runtime.list_assessments("mem_missing") == []
    report = runtime.migrate(dry_run=True)
    assert report["dry_run"] is True
    assert report["database_exists"] is False
    assert report["existing_memories"] == 0
    assert not runtime.db_path.exists()


def test_runtime_migration_is_additive_and_idempotent(tmp_path) -> None:
    store, _, memory_id = _candidate(tmp_path)
    runtime = RuntimeStore(tmp_path)

    first = runtime.migrate()
    second = runtime.migrate()

    assert first["applied"] is True
    assert second["actions"] == []
    with store.read_connect() as conn:
        columns = {row[1] for row in conn.execute("PRAGMA table_info(memories)")}
        version = conn.execute(
            "SELECT value FROM schema_meta WHERE key='trusted_memory_runtime_schema_version'"
        ).fetchone()[0]
    assert {"authority", "risk_tier", "subject", "predicate", "object_value"} <= columns
    assert int(version) == RUNTIME_SCHEMA_VERSION
    assert store.get_memory(
        memory_id,
        Principal("local-user", clearance="restricted"),
    )["memory_id"] == memory_id


def test_assessment_is_persisted_without_changing_lifecycle(tmp_path) -> None:
    store, evidence_id, memory_id = _candidate(tmp_path)
    proposal = _proposal(evidence_id)
    assessment = AdmissionEngine().assess(
        proposal,
        evidence=EvidenceSignals(total=1, available=1, direct=1),
        conflicts=ConflictSignals(state=ConflictState.NONE),
        evaluated_at="2026-09-11T20:00:00+00:00",
    )
    runtime = RuntimeStore(tmp_path)
    assessment_id = runtime.record_assessment(memory_id, proposal, assessment)

    assert assessment_id.startswith("assessment_")
    metadata = runtime.runtime_metadata(memory_id)
    assert metadata["authority"] == "trusted"
    assert metadata["risk_tier"] == "medium"
    assert metadata["subject"] == "project:atlas.messaging"
    assert metadata["object_value"] == "pubsub"
    assert metadata["admission_decision"] == AdmissionDecision.REVIEW.value

    history = runtime.list_assessments(memory_id)
    assert len(history) == 1
    assert history[0]["proposal_id"] == assessment.proposal_id
    assert history[0]["reasons"] == assessment.reasons

    with store.read_connect() as conn:
        lifecycle = conn.execute(
            "SELECT lifecycle FROM memories WHERE memory_id=?", (memory_id,)
        ).fetchone()[0]
    assert lifecycle == "candidate"


def test_unknown_memory_cannot_receive_assessment(tmp_path) -> None:
    _, evidence_id, _ = _candidate(tmp_path)
    proposal = _proposal(evidence_id)
    assessment = AdmissionEngine().assess(proposal)
    runtime = RuntimeStore(tmp_path)

    try:
        runtime.record_assessment("mem_missing", proposal, assessment)
    except ValueError as exc:
        assert "Unknown memory_id" in str(exc)
    else:
        raise AssertionError("unknown memory assessment should fail")

    with runtime.base.read_connect() as conn:
        count = conn.execute("SELECT COUNT(*) FROM admission_assessments").fetchone()[0]
    assert count == 0


def test_assessment_history_is_append_only(tmp_path) -> None:
    _, evidence_id, memory_id = _candidate(tmp_path)
    proposal = _proposal(evidence_id)
    runtime = RuntimeStore(tmp_path)

    first = AdmissionEngine().assess(
        proposal,
        evidence=EvidenceSignals(total=1, available=1, direct=1),
        evaluated_at="2026-09-11T20:00:00+00:00",
    )
    second = AdmissionEngine().assess(
        proposal,
        evidence=EvidenceSignals(total=1, available=1, direct=1),
        conflicts=ConflictSignals(
            state=ConflictState.DIRECT_CONTRADICTION,
            memory_ids=["mem_existing"],
        ),
        evaluated_at="2026-09-11T20:01:00+00:00",
    )
    runtime.record_assessment(memory_id, proposal, first)
    runtime.record_assessment(memory_id, proposal, second)

    history = runtime.list_assessments(memory_id)
    assert len(history) == 2
    assert {item["decision"] for item in history} == {"review", "quarantine"}
    assert runtime.runtime_metadata(memory_id)["admission_decision"] == "quarantine"
