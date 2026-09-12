from __future__ import annotations

from llm_kosh.runtime import (
    ConflictCandidate,
    ConflictDetector,
    ConflictState,
    MemoryProposal,
)


def _proposal(**overrides):
    values = {
        "memory_type": "decision",
        "title": "LLM-Kosh canonical storage",
        "statement": "LLM-Kosh stores canonical structured memory in local SQLite.",
        "evidence_ids": ["ev_new"],
        "source_type": "repository",
        "project_id": "llm-kosh",
        "subject": "llm-kosh.storage.canonical",
        "predicate": "backend",
        "object_value": "sqlite",
    }
    values.update(overrides)
    return MemoryProposal(**values)


def _candidate(**overrides):
    values = {
        "memory_id": "mem_existing",
        "memory_type": "decision",
        "title": "LLM-Kosh canonical storage",
        "statement": "LLM-Kosh stores canonical structured memory in local SQLite.",
        "project_id": "llm-kosh",
        "lifecycle": "active",
        "subject": "llm-kosh.storage.canonical",
        "predicate": "backend",
        "object_value": "sqlite",
    }
    values.update(overrides)
    return ConflictCandidate(**values)


def test_same_structured_claim_is_duplicate() -> None:
    detector = ConflictDetector()
    assert detector.classify(_proposal(), _candidate()) is ConflictState.DUPLICATE


def test_same_subject_predicate_different_object_is_direct_conflict() -> None:
    detector = ConflictDetector()
    candidate = _candidate(
        statement="LLM-Kosh stores canonical memory in a hosted vector database.",
        object_value="hosted-vector-db",
    )
    assert detector.classify(_proposal(), candidate) is ConflictState.DIRECT_CONTRADICTION


def test_structured_conflict_does_not_cross_project_scope() -> None:
    detector = ConflictDetector()
    candidate = _candidate(
        project_id="other-project",
        statement="The other project stores canonical memory in DuckDB.",
        object_value="duckdb",
    )
    assert detector.classify(_proposal(), candidate) is ConflictState.NONE


def test_superseded_or_retracted_candidate_does_not_block_current_memory() -> None:
    detector = ConflictDetector()
    assert detector.classify(
        _proposal(), _candidate(lifecycle="superseded", object_value="duckdb")
    ) is ConflictState.NONE
    assert detector.classify(
        _proposal(), _candidate(lifecycle="retracted", object_value="duckdb")
    ) is ConflictState.NONE


def test_explicit_supersession_is_not_inferred_from_text() -> None:
    detector = ConflictDetector()
    proposal = _proposal(
        metadata={"supersedes": ["mem_existing"]},
        statement="Canonical memory now uses SQLite after an approved migration.",
    )
    assert detector.classify(proposal, _candidate(object_value="legacy-store")) is ConflictState.SUPERSESSION


def test_single_string_supersedes_id_is_normalized_as_one_id() -> None:
    detector = ConflictDetector()
    proposal = _proposal(metadata={"supersedes": "mem_existing"})
    assert detector.classify(proposal, _candidate(object_value="legacy-store")) is ConflictState.SUPERSESSION


def test_arbitrary_scalar_supersedes_metadata_is_ignored() -> None:
    detector = ConflictDetector()
    proposal = _proposal(metadata={"supersedes": 42})
    assert detector.classify(proposal, _candidate()) is ConflictState.DUPLICATE


def test_unstructured_text_never_becomes_direct_contradiction() -> None:
    detector = ConflictDetector()
    proposal = _proposal(subject="", predicate="", object_value="")
    candidate = _candidate(
        subject="",
        predicate="",
        object_value="",
        statement="LLM-Kosh uses a hosted vector database rather than local SQLite.",
    )
    assert detector.classify(proposal, candidate) is not ConflictState.DIRECT_CONTRADICTION


def test_unrelated_unstructured_memory_is_not_flagged() -> None:
    detector = ConflictDetector()
    proposal = _proposal(
        subject="",
        predicate="",
        object_value="",
        title="LLM-Kosh canonical storage",
    )
    candidate = _candidate(
        subject="",
        predicate="",
        object_value="",
        title="LLM-Kosh README typography",
        statement="The README uses a compact centered header.",
    )
    assert detector.classify(proposal, candidate) is ConflictState.NONE


def test_detector_returns_strongest_conflict_only() -> None:
    detector = ConflictDetector()
    candidates = [
        _candidate(memory_id="mem_duplicate"),
        _candidate(
            memory_id="mem_conflict",
            statement="LLM-Kosh stores canonical memory in a hosted vector database.",
            object_value="hosted-vector-db",
        ),
    ]
    result = detector.detect(_proposal(), candidates)
    assert result.state is ConflictState.DIRECT_CONTRADICTION
    assert result.memory_ids == ["mem_conflict"]


def test_correction_can_compare_across_memory_type() -> None:
    detector = ConflictDetector()
    proposal = _proposal(
        memory_type="correction",
        statement="Correction: canonical memory is SQLite, not the legacy store.",
        metadata={"supersedes": ["mem_existing"]},
    )
    candidate = _candidate(memory_type="decision", object_value="legacy-store")
    assert detector.classify(proposal, candidate) is ConflictState.SUPERSESSION
