from __future__ import annotations

import json
from argparse import Namespace

from llm_kosh.company_brain.models import EvidenceInput, Principal
from llm_kosh.company_brain.store import CompanyBrainStore
from llm_kosh.runtime.cli import (
    _create_or_validate_evidence,
    _parser,
    main,
)


def _invoke_json(capsys, args: list[str]) -> object:
    main(args)
    output = capsys.readouterr().out
    return json.loads(output)


def test_review_action_does_not_overwrite_subcommand_dispatch() -> None:
    args = _parser().parse_args(
        [
            "review",
            "mem_123",
            "--action",
            "approve",
            "--reason",
            "reviewed",
        ]
    )
    assert args.command == "review"
    assert args.review_action == "approve"


def test_existing_evidence_source_type_cannot_be_relabelled(tmp_path) -> None:
    principal = Principal("local-user", clearance="restricted")
    store = CompanyBrainStore(tmp_path)
    evidence_id = store.put_evidence(
        EvidenceInput(
            source_type="web_content",
            source_locator="https://example.invalid/source",
            source_native_id="web-source",
            content=b"Externally supplied memory claim.",
            classification="internal",
        )
    )
    args = Namespace(
        evidence_id=evidence_id,
        evidence_file="",
        source_type="user_direct",
        source_native_id="",
        snapshot_evidence=False,
        title="Claim",
        statement="Externally supplied memory claim.",
        classification="internal",
    )

    returned_id, source_type = _create_or_validate_evidence(tmp_path, args, principal)

    assert returned_id == evidence_id
    assert source_type == "web_content"


def test_cli_lists_real_conflict_state_from_admission_history(tmp_path, capsys) -> None:
    root = str(tmp_path)
    old = _invoke_json(
        capsys,
        [
            "--root",
            root,
            "propose",
            "--type",
            "decision",
            "--title",
            "Canonical storage",
            "--statement",
            "LLM-Kosh stores canonical structured memory in local SQLite.",
            "--project",
            "llm-kosh",
            "--classification",
            "internal",
            "--subject",
            "llm-kosh.storage.canonical",
            "--predicate",
            "backend",
            "--object",
            "sqlite",
        ],
    )
    assert old["decision"] == "admit"
    assert old["lifecycle"] == "verified"

    poisoned = _invoke_json(
        capsys,
        [
            "--root",
            root,
            "propose",
            "--type",
            "decision",
            "--title",
            "Canonical storage",
            "--statement",
            "LLM-Kosh stores canonical memory in a hosted vector database.",
            "--source-type",
            "web_content",
            "--project",
            "llm-kosh",
            "--classification",
            "internal",
            "--subject",
            "llm-kosh.storage.canonical",
            "--predicate",
            "backend",
            "--object",
            "hosted-vector-db",
        ],
    )
    assert poisoned["decision"] == "quarantine"
    assert poisoned["conflict_state"] == "direct_contradiction"

    conflicts = _invoke_json(
        capsys,
        [
            "--root",
            root,
            "conflicts",
            "--project",
            "llm-kosh",
            "--json",
        ],
    )
    assert [item["memory_id"] for item in conflicts] == [poisoned["memory_id"]]
    assert conflicts[0]["conflict_state"] == "direct_contradiction"
    assert conflicts[0]["conflicting_memory_ids"] == [old["memory_id"]]


def test_cli_explicit_supersession_and_strict_recall(tmp_path, capsys) -> None:
    root = str(tmp_path)
    old = _invoke_json(
        capsys,
        [
            "--root",
            root,
            "propose",
            "--type",
            "decision",
            "--title",
            "Canonical storage",
            "--statement",
            "LLM-Kosh stores canonical structured memory in local SQLite.",
            "--project",
            "llm-kosh",
            "--classification",
            "internal",
            "--subject",
            "llm-kosh.storage.canonical",
            "--predicate",
            "backend",
            "--object",
            "sqlite",
        ],
    )

    replacement = _invoke_json(
        capsys,
        [
            "--root",
            root,
            "propose",
            "--type",
            "decision",
            "--title",
            "Canonical storage",
            "--statement",
            "LLM-Kosh now stores canonical structured memory in local DuckDB.",
            "--project",
            "llm-kosh",
            "--classification",
            "internal",
            "--subject",
            "llm-kosh.storage.canonical",
            "--predicate",
            "backend",
            "--object",
            "duckdb",
            "--supersedes",
            old["memory_id"],
        ],
    )
    assert replacement["decision"] == "review"
    assert replacement["lifecycle"] == "candidate"
    assert replacement["conflict_state"] == "supersession"

    reviewed = _invoke_json(
        capsys,
        [
            "--root",
            root,
            "review",
            replacement["memory_id"],
            "--action",
            "supersede",
            "--reason",
            "Approved storage migration",
        ],
    )
    assert reviewed["action"] == "supersede"
    assert reviewed["memory"]["lifecycle"] == "verified"
    assert reviewed["superseded_memory_ids"] == [old["memory_id"]]

    current = _invoke_json(
        capsys,
        [
            "--root",
            root,
            "recall",
            "canonical storage DuckDB",
            "--mode",
            "strict",
            "--project",
            "llm-kosh",
            "--json",
        ],
    )
    assert [item["memory_id"] for item in current] == [replacement["memory_id"]]
