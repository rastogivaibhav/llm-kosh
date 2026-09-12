from __future__ import annotations

import pytest

from llm_kosh.company_brain.models import AccessPolicy, EvidenceInput, Principal
from llm_kosh.company_brain.store import CompanyBrainStore
from llm_kosh.runtime import MemoryProposal, TrustedMemoryRuntime


def _evidence(
    root,
    *,
    native_id: str,
    text: str,
    source_type: str,
    policy: AccessPolicy | None = None,
) -> str:
    return CompanyBrainStore(root).put_evidence(
        EvidenceInput(
            source_type=source_type,
            source_locator=f"test://{native_id}",
            source_native_id=native_id,
            content=text.encode("utf-8"),
            classification="internal",
            access_policy=policy or AccessPolicy(),
        )
    )


def _storage_proposal(evidence_id: str, **overrides) -> MemoryProposal:
    values = {
        "memory_type": "decision",
        "title": "LLM-Kosh canonical storage",
        "statement": "LLM-Kosh stores canonical structured memory in local SQLite.",
        "evidence_ids": [evidence_id],
        "source_type": "user_direct",
        "project_id": "llm-kosh",
        "classification": "internal",
        "principal_id": "local-user",
        "subject": "llm-kosh.storage.canonical",
        "predicate": "backend",
        "object_value": "sqlite",
    }
    values.update(overrides)
    return MemoryProposal(**values)


def test_low_risk_direct_preference_auto_admits_and_is_idempotent(tmp_path) -> None:
    statement = "The user explicitly prefers read-only MCP access by default."
    evidence_id = _evidence(
        tmp_path,
        native_id="mcp-default",
        text=statement,
        source_type="user_direct",
    )
    proposal = MemoryProposal(
        memory_type="preference",
        title="Default MCP access mode",
        statement=statement,
        evidence_ids=[evidence_id],
        source_type="user_direct",
        project_id="llm-kosh",
        classification="internal",
        principal_id="local-user",
        subject="llm-kosh.mcp.default_access",
        predicate="mode",
        object_value="read-only",
    )
    principal = Principal("local-user", projects=["llm-kosh"], clearance="restricted")
    runtime = TrustedMemoryRuntime(tmp_path)

    first = runtime.propose(proposal, principal)
    second = runtime.propose(proposal, principal)

    assert first["decision"] == "admit"
    assert first["lifecycle"] == "verified"
    assert first["idempotent"] is False
    assert second["memory_id"] == first["memory_id"]
    assert second["decision"] == "admit"
    assert second["lifecycle"] == "verified"
    assert second["idempotent"] is True
    assert len(runtime.explain(first["memory_id"], principal)["admission_history"]) == 1


def test_trusted_medium_decision_stays_candidate_for_review(tmp_path) -> None:
    statement = "LLM-Kosh stores canonical structured memory in local SQLite."
    evidence_id = _evidence(
        tmp_path,
        native_id="repo-storage",
        text=statement,
        source_type="repository",
    )
    proposal = _storage_proposal(evidence_id, source_type="repository")
    principal = Principal("local-user", projects=["llm-kosh"], clearance="restricted")

    result = TrustedMemoryRuntime(tmp_path).propose(proposal, principal)

    assert result["decision"] == "review"
    assert result["lifecycle"] == "candidate"


def test_untrusted_contradiction_is_quarantined_without_replacing_current_memory(tmp_path) -> None:
    principal = Principal("local-user", projects=["llm-kosh"], clearance="restricted")
    runtime = TrustedMemoryRuntime(tmp_path)

    trusted_text = "LLM-Kosh stores canonical structured memory in local SQLite."
    trusted_evidence = _evidence(
        tmp_path,
        native_id="trusted-storage",
        text=trusted_text,
        source_type="user_direct",
    )
    trusted = runtime.propose(_storage_proposal(trusted_evidence), principal)
    assert trusted["lifecycle"] == "verified"

    poisoned_text = "LLM-Kosh stores canonical memory in a hosted vector database."
    poisoned_evidence = _evidence(
        tmp_path,
        native_id="untrusted-storage-page",
        text=poisoned_text,
        source_type="web_content",
    )
    poisoned = runtime.propose(
        _storage_proposal(
            poisoned_evidence,
            statement=poisoned_text,
            source_type="web_content",
            object_value="hosted-vector-db",
        ),
        principal,
    )

    assert poisoned["decision"] == "quarantine"
    assert poisoned["lifecycle"] == "quarantined"
    assert poisoned["conflict_state"] == "direct_contradiction"
    assert poisoned["conflicting_memory_ids"] == [trusted["memory_id"]]

    recalled = runtime.recall(
        "canonical storage SQLite", principal, project_id="llm-kosh", mode="normal"
    )
    assert [item["memory_id"] for item in recalled] == [trusted["memory_id"]]


def test_explicit_supersession_requires_review_and_does_not_mutate_old_memory(tmp_path) -> None:
    principal = Principal("local-user", projects=["llm-kosh"], clearance="restricted")
    runtime = TrustedMemoryRuntime(tmp_path)

    old_text = "LLM-Kosh stores canonical structured memory in local SQLite."
    old_evidence = _evidence(
        tmp_path,
        native_id="old-storage",
        text=old_text,
        source_type="user_direct",
    )
    old = runtime.propose(_storage_proposal(old_evidence), principal)
    assert old["lifecycle"] == "verified"

    correction_text = "LLM-Kosh now stores canonical structured memory in local DuckDB."
    correction_evidence = _evidence(
        tmp_path,
        native_id="approved-storage-correction",
        text=correction_text,
        source_type="user_direct",
    )
    correction = runtime.propose(
        _storage_proposal(
            correction_evidence,
            memory_type="correction",
            statement=correction_text,
            object_value="duckdb",
            metadata={"supersedes": old["memory_id"]},
        ),
        principal,
    )

    assert correction["decision"] == "review"
    assert correction["lifecycle"] == "candidate"
    assert correction["conflict_state"] == "supersession"
    assert CompanyBrainStore(tmp_path).get_memory(old["memory_id"], principal)["lifecycle"] == "verified"


def test_proposal_cannot_use_evidence_hidden_from_principal(tmp_path) -> None:
    restricted = AccessPolicy(allowed_principals=["alice"])
    evidence_id = _evidence(
        tmp_path,
        native_id="alice-only",
        text="LLM-Kosh stores canonical structured memory in local SQLite.",
        source_type="repository",
        policy=restricted,
    )
    bob = Principal("bob", projects=["llm-kosh"], clearance="restricted")
    proposal = _storage_proposal(
        evidence_id,
        source_type="repository",
        principal_id="bob",
    )

    with pytest.raises(PermissionError):
        TrustedMemoryRuntime(tmp_path).propose(proposal, bob)
