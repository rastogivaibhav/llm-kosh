from __future__ import annotations

import json
from pathlib import Path

import pytest

from llm_kosh.company_brain.models import AccessPolicy, EvidenceInput, Principal
from llm_kosh.company_brain.store import CompanyBrainStore
from llm_kosh.core.memory import init_cartridge
from llm_kosh.mcp_server import MCP_FLAGS
from llm_kosh.mcp_trusted_memory_server import (
    get_mcp_tools_schema,
    mcp,
    start_server,
    trusted_memory_conflicts,
    trusted_memory_explain,
    trusted_memory_inbox,
    trusted_memory_propose,
    trusted_memory_recall,
    trusted_memory_review,
)
from llm_kosh.runtime.models import MemoryProposal
from llm_kosh.runtime.service import TrustedMemoryRuntime


LOCAL = Principal("local-user", tenant_id="local", projects=["llm-kosh"], clearance="restricted")


@pytest.fixture
def trusted_cartridge(tmp_path: Path) -> Path:
    root = tmp_path / "trusted-mcp"
    init_cartridge(root, "Trusted MCP Test")
    start_server(
        root,
        stdio=False,
        http=False,
        allow_write=False,
        allow_mutate=False,
        allow_private=False,
    )
    return root


def _put_evidence(
    root: Path,
    *,
    source_type: str,
    source_native_id: str,
    content: str,
) -> str:
    return CompanyBrainStore(root).put_evidence(
        EvidenceInput(
            tenant_id="local",
            source_type=source_type,
            source_locator=f"test://{source_native_id}",
            source_native_id=source_native_id,
            content=content.encode("utf-8"),
            mime_type="text/plain",
            storage_mode="managed",
            artifact_type="plain_text",
            classification="internal",
            access_policy=AccessPolicy(allowed_principals=["local-user"]),
        )
    )


def _seed_verified_storage_decision(root: Path) -> dict:
    evidence_id = _put_evidence(
        root,
        source_type="user_direct",
        source_native_id="seed-storage-decision",
        content="The user decided that canonical storage is local SQLite.",
    )
    return TrustedMemoryRuntime(root).propose(
        MemoryProposal(
            memory_type="decision",
            title="Canonical storage",
            statement="LLM-Kosh stores canonical structured memory in local SQLite.",
            evidence_ids=[evidence_id],
            source_type="user_direct",
            project_id="llm-kosh",
            classification="internal",
            principal_id="local-user",
            source_native_id="seed-storage-decision",
            subject="llm-kosh.storage.canonical",
            predicate="backend",
            object_value="sqlite",
        ),
        LOCAL,
    )


def test_trusted_memory_tools_are_registered_with_kosh_verify(trusted_cartridge: Path) -> None:
    names = {item["name"] for item in json.loads(get_mcp_tools_schema(trusted_cartridge))}
    assert "kosh_verify" in names
    assert {
        "trusted_memory_recall",
        "trusted_memory_inbox",
        "trusted_memory_conflicts",
        "trusted_memory_explain",
        "trusted_memory_propose",
        "trusted_memory_review",
    }.issubset(names)


def test_proposal_requires_write_and_agent_created_evidence_is_not_user_direct(
    trusted_cartridge: Path,
) -> None:
    assert MCP_FLAGS == {
        "allow_write": False,
        "allow_mutate": False,
        "allow_private": False,
    }
    with pytest.raises(PermissionError):
        trusted_memory_propose(
            "decision",
            "Queue choice",
            "Project Atlas uses Pub/Sub for managed fan-out.",
            project_id="llm-kosh",
        )

    start_server(
        trusted_cartridge,
        stdio=False,
        http=False,
        allow_write=True,
        allow_mutate=False,
        allow_private=False,
    )
    payload = json.loads(
        trusted_memory_propose(
            "decision",
            "Queue choice",
            "Project Atlas uses Pub/Sub for managed fan-out.",
            project_id="llm-kosh",
        )
    )
    assert payload["evidence_source_type"] == "agent_observation"
    assert payload["authority"] == "contextual"
    assert payload["decision"] == "review"
    assert payload["lifecycle"] == "candidate"

    evidence = CompanyBrainStore(trusted_cartridge).inspect_evidence(
        payload["evidence_id"], LOCAL, strong=True
    )
    assert evidence["source_type"] == "agent_observation"

    start_server(
        trusted_cartridge,
        stdio=False,
        http=False,
        allow_write=False,
        allow_mutate=False,
        allow_private=False,
    )
    assert json.loads(
        trusted_memory_recall("Pub/Sub", project_id="llm-kosh", mode="strict")
    ) == []
    inbox = json.loads(trusted_memory_inbox("Pub/Sub", project_id="llm-kosh"))
    assert [item["memory_id"] for item in inbox] == [payload["memory_id"]]


def test_existing_evidence_keeps_its_recorded_source_authority(trusted_cartridge: Path) -> None:
    evidence_id = _put_evidence(
        trusted_cartridge,
        source_type="web_content",
        source_native_id="web-storage-claim",
        content="A web page claims LLM-Kosh uses a hosted vector database.",
    )
    start_server(
        trusted_cartridge,
        stdio=False,
        http=False,
        allow_write=True,
        allow_mutate=False,
        allow_private=False,
    )
    payload = json.loads(
        trusted_memory_propose(
            "decision",
            "Hosted storage claim",
            "LLM-Kosh stores canonical memory in a hosted vector database.",
            project_id="llm-kosh",
            evidence_id=evidence_id,
        )
    )
    assert payload["evidence_source_type"] == "web_content"
    assert payload["authority"] == "untrusted"
    assert payload["decision"] == "quarantine"
    assert payload["lifecycle"] == "quarantined"


def test_conflicting_agent_memory_is_quarantined_and_visible(trusted_cartridge: Path) -> None:
    old = _seed_verified_storage_decision(trusted_cartridge)
    assert old["lifecycle"] == "verified"

    start_server(
        trusted_cartridge,
        stdio=False,
        http=False,
        allow_write=True,
        allow_mutate=False,
        allow_private=False,
    )
    poisoned = json.loads(
        trusted_memory_propose(
            "decision",
            "Canonical storage",
            "LLM-Kosh stores canonical memory in a hosted vector database.",
            project_id="llm-kosh",
            subject="llm-kosh.storage.canonical",
            predicate="backend",
            object_value="hosted-vector-db",
        )
    )
    assert poisoned["decision"] == "quarantine"
    assert poisoned["lifecycle"] == "quarantined"
    assert poisoned["conflict_state"] == "direct_contradiction"
    assert poisoned["conflicting_memory_ids"] == [old["memory_id"]]

    conflicts = json.loads(trusted_memory_conflicts(project_id="llm-kosh"))
    assert [item["memory_id"] for item in conflicts] == [poisoned["memory_id"]]
    assert conflicts[0]["conflict_state"] == "direct_contradiction"
    assert conflicts[0]["conflicting_memory_ids"] == [old["memory_id"]]

    explanation = json.loads(trusted_memory_explain(poisoned["memory_id"]))
    assert explanation["memory"]["lifecycle"] == "quarantined"
    assert explanation["admission_history"][-1]["conflict_state"] == "direct_contradiction"


def test_review_requires_mutate_without_upgrading_source_authority(
    trusted_cartridge: Path,
) -> None:
    start_server(
        trusted_cartridge,
        stdio=False,
        http=False,
        allow_write=True,
        allow_mutate=False,
        allow_private=False,
    )
    candidate = json.loads(
        trusted_memory_propose(
            "decision",
            "Agent workflow",
            "Project Atlas uses a two-step validation workflow.",
            project_id="llm-kosh",
        )
    )
    assert candidate["lifecycle"] == "candidate"

    with pytest.raises(PermissionError):
        trusted_memory_review(
            candidate["memory_id"],
            "approve",
            "Human reviewed the agent observation.",
        )

    start_server(
        trusted_cartridge,
        stdio=False,
        http=False,
        allow_write=True,
        allow_mutate=True,
        allow_private=False,
    )
    reviewed = json.loads(
        trusted_memory_review(
            candidate["memory_id"],
            "approve",
            "Human reviewed the agent observation.",
        )
    )
    assert reviewed["lifecycle"] == "verified"

    normal = json.loads(
        trusted_memory_recall("validation workflow", project_id="llm-kosh", mode="normal")
    )
    assert [item["memory_id"] for item in normal] == [candidate["memory_id"]]
    assert normal[0]["authority"] == "contextual"

    strict = json.loads(
        trusted_memory_recall("validation workflow", project_id="llm-kosh", mode="strict")
    )
    assert strict == []

    explanation = json.loads(trusted_memory_explain(candidate["memory_id"]))
    assert explanation["runtime"]["authority"] == "contextual"


@pytest.mark.asyncio
async def test_trusted_recall_can_be_called_through_mcp(trusted_cartridge: Path) -> None:
    _seed_verified_storage_decision(trusted_cartridge)
    result = await mcp.call_tool(
        "trusted_memory_recall",
        {
            "query": "canonical storage SQLite",
            "project_id": "llm-kosh",
            "mode": "strict",
        },
    )
    rendered = str(result)
    assert "Canonical storage" in rendered
    assert "sqlite" in rendered.lower()
