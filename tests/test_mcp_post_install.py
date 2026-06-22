import json

import pytest

from llm_kosh.mcp_server import mcp, get_mcp_tools_schema, start_server


@pytest.fixture
def installed_workspace(tmp_path):
    root = tmp_path / "cartridge"
    root.mkdir()
    (root / "inbox").mkdir()
    (root / "exports").mkdir()
    (root / "LLM_KOSH.json").write_text(json.dumps({
        "schema": "llm-kosh.v0",
        "version": "1.0.0",
        "retrieval_weights": {},
    }), encoding="utf-8")
    (root / "CARTRIDGE_POLICY.json").write_text(json.dumps({
        "mcp": {
            "allow_write": True,
            "allow_mutation": True,
            "allow_private_exports": True,
        }
    }), encoding="utf-8")
    return root


def test_mcp_schema_is_printable_after_install(installed_workspace):
    schema = get_mcp_tools_schema(installed_workspace)
    parsed = json.loads(schema)

    tool_names = {tool["name"] for tool in parsed}
    assert "search_memory" in tool_names
    assert "reasoning_query" in tool_names
    assert "submit_memory_receipt" in tool_names


@pytest.mark.asyncio
async def test_mcp_tools_are_usable_with_post_install_policy(installed_workspace):
    start_server(installed_workspace, stdio=False, http=False, allow_write=False, allow_mutate=False, allow_private=False)

    search_res = await mcp.call_tool("search_memory", {"query": "missing"})
    assert "No results found" in str(search_res)

    receipt_res = await mcp.call_tool("submit_memory_receipt", {"receipt_content": "# MEMORY_RECEIPT\n"})
    assert "Receipt submitted" in str(receipt_res)

    reason_res = await mcp.call_tool("reasoning_query", {"query": "nothing here"})
    assert "No causal chain found" in str(reason_res)
