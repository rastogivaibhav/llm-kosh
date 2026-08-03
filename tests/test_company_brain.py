import json

import pytest

from llm_kosh.company_brain.context import compile_context
from llm_kosh.company_brain.migration import migrate_legacy_cartridge
from llm_kosh.company_brain.models import (
    AccessPolicy,
    ContextRequest,
    EvidenceInput,
    EvidenceReference,
    MemoryInput,
    Principal,
)
from llm_kosh.company_brain.retrieval import search_memories
from llm_kosh.company_brain.store import CompanyBrainStore
from llm_kosh.core.memory import add_memory, init_cartridge


def _evidence(store, *, native_id="source-1", policy=None, classification="internal"):
    return store.put_evidence(EvidenceInput(
        source_type="test",
        source_locator="test://source-1",
        source_native_id=native_id,
        content=b"PostgreSQL was selected for auditability and JSONB support.",
        classification=classification,
        access_policy=policy or AccessPolicy(),
    ))


def _memory(store, evidence_id, *, lifecycle="candidate", policy=None, native_id="memory-1"):
    return store.add_memory(MemoryInput(
        memory_type="decision",
        title="Use PostgreSQL for the audit store",
        statement="The audit service uses PostgreSQL because it needs durable JSONB queries.",
        rationale="The team compared the supported storage choices.",
        project_id="audit",
        lifecycle=lifecycle,
        confidence=0.91,
        importance=0.85,
        classification="internal",
        access_policy=policy or AccessPolicy(),
        source_native_id=native_id,
        evidence=[EvidenceReference(evidence_id=evidence_id, quote="PostgreSQL was selected")],
    ))


def test_evidence_is_content_addressed_and_deduplicated(tmp_path):
    store = CompanyBrainStore(tmp_path)
    first = _evidence(store)
    second = _evidence(store)
    assert first == second
    health = store.health()
    assert health["evidence"] == 1
    assert health["missing_blobs"] == []


def test_memory_requires_semantic_title_and_evidence(tmp_path):
    store = CompanyBrainStore(tmp_path)
    evidence_id = _evidence(store)
    with pytest.raises(ValueError, match="semantic"):
        store.add_memory(MemoryInput(
            memory_type="fact",
            title="1234",
            statement="This statement is long enough to be considered atomic.",
            evidence=[EvidenceReference(evidence_id=evidence_id)],
        ))


def test_permissions_are_applied_before_retrieval_and_context(tmp_path):
    store = CompanyBrainStore(tmp_path)
    policy = AccessPolicy(allowed_groups=["audit-team"], allowed_projects=["audit"])
    evidence_id = _evidence(store, policy=policy)
    memory_id = _memory(store, evidence_id, lifecycle="candidate", policy=policy)
    allowed = Principal(
        "alice", groups=["audit-team"], projects=["audit"], clearance="internal"
    )
    denied = Principal("bob", groups=["sales"], projects=["sales"], clearance="restricted")

    # Candidates are hidden from normal retrieval even for authorized users.
    assert search_memories(store, "PostgreSQL audit", allowed, project_id="audit") == []
    reviewer = Principal(
        "reviewer", groups=["audit-team"], projects=["audit"], clearance="internal"
    )
    store.transition_memory(memory_id, "verified", reviewer, reason="source checked")
    store.transition_memory(memory_id, "active", reviewer, reason="approved")

    allowed_results = search_memories(store, "PostgreSQL audit", allowed, project_id="audit")
    assert [item["memory_id"] for item in allowed_results] == [memory_id]
    assert search_memories(store, "PostgreSQL audit", denied) == []

    context = compile_context(store, ContextRequest(
        task="Explain the audit database decision",
        principal=allowed,
        project_id="audit",
        token_budget=512,
    ))
    assert context["selected_items"] == 1
    assert context["decisions"][0]["memory_id"] == memory_id
    assert context["source_index"][0]["evidence_id"] == evidence_id
    assert context["estimated_tokens"] <= context["token_budget"]


def test_stricter_evidence_policy_blocks_memory_and_citations(tmp_path):
    store = CompanyBrainStore(tmp_path)
    evidence_policy = AccessPolicy(allowed_groups=["legal"])
    evidence_id = _evidence(store, policy=evidence_policy)
    memory_id = _memory(store, evidence_id, lifecycle="active")
    ordinary = Principal("alice", groups=["engineering"], clearance="internal")
    legal = Principal("lee", groups=["legal"], clearance="internal")

    assert search_memories(store, "PostgreSQL audit", ordinary) == []
    with pytest.raises(PermissionError, match="evidence"):
        store.get_memory(memory_id, ordinary)
    assert store.get_memory(memory_id, legal)["evidence"][0]["evidence_id"] == evidence_id


def test_read_operations_do_not_initialize_an_empty_store(tmp_path):
    store = CompanyBrainStore(tmp_path)
    principal = Principal("alice")
    assert search_memories(store, "anything", principal) == []
    assert store.health()["integrity"] == "not_initialized"
    assert not store.db_path.exists()


def test_legacy_migration_preserves_sources_and_only_promotes_useful_candidates(tmp_path):
    init_cartridge(tmp_path, "Migration test")
    add_memory(
        tmp_path,
        kind="decision",
        title="Keep the billing ledger immutable",
        body="Billing ledger entries are append-only so every correction remains auditable.",
        project="billing",
        reindex=False,
    )
    add_memory(
        tmp_path,
        kind="file",
        title="Raw transcript",
        body="A long unstructured transcript that should remain source evidence only.",
        project="billing",
        reindex=False,
    )

    report = migrate_legacy_cartridge(tmp_path)
    assert report["source_files"] == 2
    assert report["evidence_created"] == 2
    assert report["reference_evidence"] == 2
    assert report["copied_source_bytes"] == 0
    assert report["memory_candidates_created"] == 1
    assert report["raw_evidence_only"] == 1
    assert not (tmp_path / "evidence" / "blobs").exists()

    # The migration is idempotent at both the evidence and memory identities.
    second = migrate_legacy_cartridge(tmp_path)
    assert second["health"]["evidence"] == 2
    assert second["health"]["memories"] == 1
