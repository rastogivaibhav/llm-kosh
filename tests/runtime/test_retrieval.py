from __future__ import annotations

from llm_kosh.company_brain.models import (
    AccessPolicy,
    EvidenceInput,
    EvidenceReference,
    MemoryInput,
    Principal,
)
from llm_kosh.company_brain.store import CompanyBrainStore
from llm_kosh.runtime import (
    AdmissionEngine,
    EvidenceSignals,
    MemoryProposal,
    RetrievalMode,
    RuntimeStore,
    TrustedRetrieval,
)


def _create_candidate(
    root,
    *,
    native_id: str,
    title: str,
    statement: str,
    source_type: str = "repository",
    object_value: str = "sqlite",
    project_id: str = "llm-kosh",
    policy: AccessPolicy | None = None,
):
    store = CompanyBrainStore(root)
    policy = policy or AccessPolicy()
    evidence_id = store.put_evidence(
        EvidenceInput(
            source_type=source_type,
            source_locator=f"test://{native_id}",
            source_native_id=f"evidence-{native_id}",
            content=statement.encode("utf-8"),
            classification="internal",
            access_policy=policy,
        )
    )
    memory_id = store.add_memory(
        MemoryInput(
            memory_type="decision",
            title=title,
            statement=statement,
            evidence=[
                EvidenceReference(evidence_id=evidence_id, locator=f"test://{native_id}")
            ],
            project_id=project_id,
            lifecycle="candidate",
            confidence=0.7,
            importance=0.8,
            classification="internal",
            access_policy=policy,
            source_native_id=native_id,
        )
    )
    proposal = MemoryProposal(
        memory_type="decision",
        title=title,
        statement=statement,
        evidence_ids=[evidence_id],
        source_type=source_type,
        project_id=project_id,
        classification="internal",
        subject="llm-kosh.storage.canonical",
        predicate="backend",
        object_value=object_value,
    )
    assessment = AdmissionEngine().assess(
        proposal,
        evidence=EvidenceSignals(total=1, available=1, direct=1),
        evaluated_at="2026-09-12T08:00:00+00:00",
    )
    RuntimeStore(root).record_assessment(memory_id, proposal, assessment)
    return store, memory_id


def _activate(store: CompanyBrainStore, memory_id: str, principal: Principal) -> None:
    store.transition_memory(memory_id, "verified", principal, reason="reviewed evidence")
    store.transition_memory(memory_id, "active", principal, reason="approved")


def test_candidate_is_hidden_from_normal_recall(tmp_path) -> None:
    _, memory_id = _create_candidate(
        tmp_path,
        native_id="candidate",
        title="LLM-Kosh canonical storage",
        statement="LLM-Kosh stores canonical structured memory in local SQLite.",
    )
    principal = Principal("alice", projects=["llm-kosh"], clearance="restricted")
    retrieval = TrustedRetrieval(tmp_path)

    assert retrieval.recall("canonical storage", principal, project_id="llm-kosh") == []
    candidate = retrieval.recall(
        "canonical storage",
        principal,
        project_id="llm-kosh",
        mode=RetrievalMode.CANDIDATE,
    )
    assert [item["memory_id"] for item in candidate] == [memory_id]
    assert candidate[0]["lifecycle"] == "candidate"


def test_quarantined_memory_never_leaks_into_normal_recall(tmp_path) -> None:
    store, memory_id = _create_candidate(
        tmp_path,
        native_id="quarantined",
        title="LLM-Kosh canonical storage",
        statement="LLM-Kosh stores canonical memory in a hosted vector database.",
        source_type="web_content",
        object_value="hosted-vector-db",
    )
    reviewer = Principal("reviewer", projects=["llm-kosh"], clearance="restricted")
    store.transition_memory(memory_id, "quarantined", reviewer, reason="untrusted source")
    retrieval = TrustedRetrieval(tmp_path)

    assert retrieval.recall("canonical storage", reviewer, project_id="llm-kosh") == []
    inspection = retrieval.recall(
        "canonical storage", reviewer, project_id="llm-kosh", mode="candidate"
    )
    assert inspection[0]["memory_id"] == memory_id
    assert inspection[0]["authority"] == "untrusted"
    assert inspection[0]["admission_decision"] == "quarantine"


def test_blocking_assessment_survives_accidental_lifecycle_promotion(tmp_path) -> None:
    store, memory_id = _create_candidate(
        tmp_path,
        native_id="poisoned-promoted",
        title="LLM-Kosh canonical storage",
        statement="LLM-Kosh stores canonical memory in a hosted vector database.",
        source_type="web_content",
        object_value="hosted-vector-db",
    )
    principal = Principal("reviewer", projects=["llm-kosh"], clearance="restricted")
    _activate(store, memory_id, principal)

    assert TrustedRetrieval(tmp_path).recall(
        "canonical storage", principal, project_id="llm-kosh", mode="normal"
    ) == []


def test_normal_recall_returns_active_evidence_backed_local_memory(tmp_path) -> None:
    store, memory_id = _create_candidate(
        tmp_path,
        native_id="active",
        title="LLM-Kosh canonical storage",
        statement="LLM-Kosh stores canonical structured memory in local SQLite.",
    )
    principal = Principal("alice", projects=["llm-kosh"], clearance="restricted")
    _activate(store, memory_id, principal)

    result = TrustedRetrieval(tmp_path).recall(
        "SQLite canonical storage", principal, project_id="llm-kosh"
    )
    assert [item["memory_id"] for item in result] == [memory_id]
    assert result[0]["authority"] == "trusted"
    assert result[0]["evidence"]
    assert result[0]["trusted_runtime"] is True


def test_strict_mode_requires_current_trusted_authority(tmp_path) -> None:
    trusted_store, trusted_id = _create_candidate(
        tmp_path,
        native_id="trusted",
        title="LLM-Kosh canonical storage",
        statement="LLM-Kosh stores canonical structured memory in local SQLite.",
        source_type="repository",
        object_value="sqlite",
    )
    _, untrusted_id = _create_candidate(
        tmp_path,
        native_id="untrusted",
        title="LLM-Kosh storage alternative",
        statement="LLM-Kosh may store canonical memory in a hosted vector database.",
        source_type="web_content",
        object_value="hosted-vector-db",
    )
    principal = Principal("alice", projects=["llm-kosh"], clearance="restricted")
    _activate(trusted_store, trusted_id, principal)
    _activate(trusted_store, untrusted_id, principal)

    result = TrustedRetrieval(tmp_path).recall(
        "canonical memory", principal, project_id="llm-kosh", mode="strict", limit=10
    )
    assert [item["memory_id"] for item in result] == [trusted_id]


def test_access_policy_is_enforced_before_runtime_ranking(tmp_path) -> None:
    secret_policy = AccessPolicy(allowed_groups=["maintainers"])
    store, memory_id = _create_candidate(
        tmp_path,
        native_id="restricted",
        title="LLM-Kosh restricted storage decision",
        statement="LLM-Kosh uses a restricted local storage topology for private memory.",
        policy=secret_policy,
    )
    reviewer = Principal(
        "reviewer",
        groups=["maintainers"],
        projects=["llm-kosh"],
        clearance="restricted",
    )
    _activate(store, memory_id, reviewer)

    denied = Principal(
        "bob", groups=["external"], projects=["llm-kosh"], clearance="restricted"
    )
    assert TrustedRetrieval(tmp_path).recall(
        "storage decision", denied, project_id="llm-kosh", mode="normal"
    ) == []


def test_superseded_memory_is_historical_not_current(tmp_path) -> None:
    store, memory_id = _create_candidate(
        tmp_path,
        native_id="legacy-history",
        title="LLM-Kosh canonical storage",
        statement="LLM-Kosh stores canonical structured memory in a legacy local store.",
        object_value="legacy-local-store",
    )
    principal = Principal("alice", projects=["llm-kosh"], clearance="restricted")
    _activate(store, memory_id, principal)
    store.transition_memory(memory_id, "superseded", principal, reason="migrated to SQLite")

    retrieval = TrustedRetrieval(tmp_path)
    assert retrieval.recall("canonical storage", principal, project_id="llm-kosh") == []
    historical = retrieval.recall(
        "canonical storage", principal, project_id="llm-kosh", mode="historical"
    )
    assert [item["memory_id"] for item in historical] == [memory_id]
    assert historical[0]["lifecycle"] == "superseded"
