from __future__ import annotations

import json
from pathlib import Path

import pytest

from llm_kosh.core.memory import init_cartridge
from llm_kosh.mcp_server import MCP_FLAGS
from llm_kosh.mcp_verify_server import get_mcp_tools_schema, kosh_verify, mcp, start_server
from llm_kosh.verify import seed_incident_cartridge


QUESTION = "Why did checkout fail and what evidence contradicts the explanation?"
WHEN = "2026-05-01T13:30:00+00:00"


@pytest.fixture
def verify_cartridge(tmp_path: Path) -> Path:
    root = tmp_path / "verify"
    seed_incident_cartridge(root)
    start_server(
        root,
        stdio=False,
        http=False,
        allow_write=False,
        allow_mutate=False,
        allow_private=False,
    )
    return root


def test_kosh_verify_is_registered_as_an_mcp_tool(verify_cartridge: Path) -> None:
    schema = json.loads(get_mcp_tools_schema(verify_cartridge))
    assert any(tool["name"] == "kosh_verify" for tool in schema)


def test_kosh_verify_is_read_only_and_returns_structured_report(
    verify_cartridge: Path,
) -> None:
    assert MCP_FLAGS == {
        "allow_write": False,
        "allow_mutate": False,
        "allow_private": False,
    }

    payload = json.loads(
        kosh_verify(
            QUESTION,
            temporal_context=WHEN,
            depth=5,
            dialectic=True,
        )
    )

    assert payload["abstain"] is False
    assert payload["primary_answer"]
    assert payload["paths"]
    assert payload["inferred_not_discovered"]
    assert payload["missing_evidence"]


@pytest.mark.asyncio
async def test_kosh_verify_can_be_called_through_mcp(verify_cartridge: Path) -> None:
    result = await mcp.call_tool(
        "kosh_verify",
        {
            "query": QUESTION,
            "temporal_context": WHEN,
            "depth": 5,
            "dialectic": True,
        },
    )
    rendered = str(result)
    assert "primary_answer" in rendered
    assert "inferred_not_discovered" in rendered


def test_kosh_verify_abstains_when_local_evidence_is_absent(tmp_path: Path) -> None:
    root = tmp_path / "empty"
    init_cartridge(root, "MCP Verify Empty")
    start_server(
        root,
        stdio=False,
        http=False,
        allow_write=False,
        allow_mutate=False,
        allow_private=False,
    )

    payload = json.loads(kosh_verify("What happened to the moon cheese inventory?"))
    assert payload["abstain"] is True
    assert payload["status"] == "no_evidence"
    assert payload["primary_answer"] is None
