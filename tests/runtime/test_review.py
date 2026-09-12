from __future__ import annotations

import pytest

from llm_kosh.company_brain.models import EvidenceInput, Principal
from llm_kosh.company_brain.store import CompanyBrainStore
from llm_kosh.runtime import MemoryProposal, TrustedMemoryReviewer, TrustedMemoryRuntime


def _evidence(root, native_id: str, text: str, source_type: str) -> str:
    return CompanyBrainStore(root).put_evidence(
        EvidenceInput(
            source_type=source_type,
            source_locator=f"test://{native_id}",
            source_native_id=native_id,
            content=text.encode("utf-8"),
            classification="internal",
        )
    )


def _proposal(evidence_id: str, **overrides) -> MemoryProposal:
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


def test_simple_review_approves_unconflicted_candidate(tmp_path) -> None:
    principal = Principal("local-user", projects=["llm-kosh"], clearance="restricted")
    statement = "LLM-Kosh stores canonical structured memory in local SQLite."
    evidence_id = _evidence(tmp_path, "repo-storage", statement, "repository")
    runtime = TrustedMemoryRuntime(tmp_path)
    proposed = runtime.propose(_proposal(evidence_id, source_type="repository"), principal)
    assert proposed["decision"] == "review"
    assert proposed["lifecycle"] == "candidate"

    approved = TrustedMemoryReviewer(tmp_path).review(
        proposed["memory_id"],
        principal,
        action="approve",
        reason="Repository evidence reviewed",
    )
    assert approved["lifecycle"] == "verified"


def test_supersession_is_atomic_and_preserves_history(tmp_path) -> None:
    principal = Principal("local-user", projects=["llm-kosh"], clearance="restricted")
    runtime = TrustedMemoryRuntime(tmp_path)

    old_text = "LLM-Kosh stores canonical structured memory in local SQLite."
    old_id = _evidence(tmp_path, "sqlite-decision", old_text, "user_direct")
    old = runtime.propose(_proposal(old_id), principal)
    assert old["lifecycle"] == "verified"

    new_text = "LLM-Kosh now stores canonical structured memory in local DuckDB."
    new_id = _evidence(tmp_path, "duckdb-decision", new_text, "user_direct")
    replacement = runtime.propose(
        _proposal(
            new_id,
            statement=new_text,
            object_value="duckdb",
            metadata={"supersedes": old["memory_id"]},
        ),
        principal,
    )
    assert replacement["decision"] == "review"
    assert replacement["conflict_state"] == "supersession"
    assert replacement["lifecycle"] == "candidate"

    result = TrustedMemoryReviewer(tmp_path).review(
        replacement["memory_id"],
        principal,
        action="supersede",
        reason="Approved local storage migration",
    )
    assert result["memory"]["lifecycle"] == "verified"
    assert result["memory"]["supersedes"] == [old["memory_id"]]
    assert result["superseded_memory_ids"] == [old["memory_id"]]

    store = CompanyBrainStore(tmp_path)
    assert store.get_memory(old["memory_id"], principal)["lifecycle"] == "superseded"

    current = runtime.recall("canonical storage DuckDB", principal, project_id="llm-kosh")
    assert [item["memory_id"] for item in current] == [replacement["memory_id"]]
    historical = runtime.recall(
        "canonical storage SQLite",
        principal,
        project_id="llm-kosh",
        mode="historical",
    )
    assert old["memory_id"] in {item["memory_id"] for item in historical}


def test_generic_approve_refuses_unresolved_supersession(tmp_path) -> None:
    principal = Principal("local-user", projects=["llm-kosh"], clearance="restricted")
    runtime = TrustedMemoryRuntime(tmp_path)
    old_text = "LLM-Kosh stores canonical structured memory in local SQLite."
    old_ev = _evidence(tmp_path, "old", old_text, "user_direct")
    old = runtime.propose(_proposal(old_ev), principal)

    new_text = "LLM-Kosh now stores canonical structured memory in local DuckDB."
    new_ev = _evidence(tmp_path, "new", new_text, "user_direct")
    new = runtime.propose(
        _proposal(
            new_ev,
            statement=new_text,
            object_value="duckdb",
            metadata={"supersedes": old["memory_id"]},
        ),
        principal,
    )

    with pytest.raises(ValueError, match="supersede explicitly"):
        TrustedMemoryReviewer(tmp_path).review(
            new["memory_id"], principal, action="approve", reason="generic approval"
        )
    assert CompanyBrainStore(tmp_path).get_memory(new["memory_id"], principal)["lifecycle"] == "candidate"
    assert CompanyBrainStore(tmp_path).get_memory(old["memory_id"], principal)["lifecycle"] == "verified"


def test_reject_is_explicit_lifecycle_action(tmp_path) -> None:
    principal = Principal("local-user", projects=["llm-kosh"], clearance="restricted")
    statement = "LLM-Kosh stores canonical structured memory in local SQLite."
    evidence_id = _evidence(tmp_path, "review-reject", statement, "repository")
    proposed = TrustedMemoryRuntime(tmp_path).propose(
        _proposal(evidence_id, source_type="repository"), principal
    )

    rejected = TrustedMemoryReviewer(tmp_path).review(
        proposed["memory_id"], principal, action="reject", reason="Evidence was outdated"
    )
    assert rejected["lifecycle"] == "rejected"


def test_failed_supersession_does_not_partially_promote_replacement(tmp_path) -> None:
    principal = Principal("local-user", projects=["llm-kosh"], clearance="restricted")
    runtime = TrustedMemoryRuntime(tmp_path)
    store = CompanyBrainStore(tmp_path)

    old_text = "LLM-Kosh stores canonical structured memory in local SQLite."
    old_ev = _evidence(tmp_path, "rollback-old", old_text, "user_direct")
    old = runtime.propose(_proposal(old_ev), principal)

    new_text = "LLM-Kosh now stores canonical structured memory in local DuckDB."
    new_ev = _evidence(tmp_path, "rollback-new", new_text, "user_direct")
    new = runtime.propose(
        _proposal(
            new_ev,
            statement=new_text,
            object_value="duckdb",
            metadata={"supersedes": old["memory_id"]},
        ),
        principal,
    )

    # Simulate the target being resolved elsewhere before this review executes.
    store.transition_memory(old["memory_id"], "superseded", principal, reason="resolved elsewhere")

    with pytest.raises(ValueError, match="Invalid supersession transition"):
        TrustedMemoryReviewer(tmp_path).review(
            new["memory_id"],
            principal,
            action="supersede",
            reason="stale review attempt",
        )

    assert store.get_memory(new["memory_id"], principal)["lifecycle"] == "candidate"


def test_other_principal_cannot_review_private_candidate(tmp_path) -> None:
    owner = Principal("local-user", projects=["llm-kosh"], clearance="restricted")
    evidence_id = _evidence(
        tmp_path,
        "private-review",
        "LLM-Kosh stores canonical structured memory in local SQLite.",
        "repository",
    )
    proposed = TrustedMemoryRuntime(tmp_path).propose(
        _proposal(evidence_id, source_type="repository"), owner
    )
    other = Principal("other", projects=["llm-kosh"], clearance="restricted")

    with pytest.raises(PermissionError):
        TrustedMemoryReviewer(tmp_path).review(
            proposed["memory_id"], other, action="approve", reason="not authorized"
        )
