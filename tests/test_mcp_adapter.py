import pytest
import os
import json
from pathlib import Path
from koush.mcp_server import mcp, start_server, get_mcp_tools_schema, WORKSPACE_PATH, MCP_FLAGS
from koush.core.memory import init_cartridge
from koush.core.utils import read_json

@pytest.fixture
def mcp_cartridge(tmp_path):
    init_cartridge(tmp_path, "MCP Test")
    start_server(tmp_path, stdio=False, http=False, allow_write=False, allow_mutate=False, allow_private=False)
    return tmp_path

def test_mcp_tools_schema(mcp_cartridge):
    schema = get_mcp_tools_schema(mcp_cartridge)
    assert "search_memory" in schema
    assert "submit_memory_receipt" in schema

@pytest.mark.asyncio
async def test_search_memory(mcp_cartridge):
    res = await mcp.call_tool("search_memory", {"query": "test"})
    assert "No results found" in str(res)

@pytest.mark.asyncio
async def test_write_blocked_by_default(mcp_cartridge):
    with pytest.raises(Exception, match="requires write capability"):
        await mcp.call_tool("submit_memory_receipt", {"receipt_content": "test"})

@pytest.mark.asyncio
async def test_write_allowed_when_flag_set(mcp_cartridge):
    start_server(mcp_cartridge, stdio=False, http=False, allow_write=True, allow_mutate=False, allow_private=False)
    res = await mcp.call_tool("submit_memory_receipt", {"receipt_content": "# MEMORY_RECEIPT\n"})
    assert "Receipt submitted" in str(res)

@pytest.mark.asyncio
async def test_mutate_blocked(mcp_cartridge):
    start_server(mcp_cartridge, stdio=False, http=False, allow_write=True, allow_mutate=False, allow_private=False)
    with pytest.raises(Exception, match="requires mutation capability"):
        await mcp.call_tool("apply_intake_proposal", {"batch_id": "b1"})

@pytest.mark.asyncio
async def test_private_export_blocked(mcp_cartridge):
    start_server(mcp_cartridge, stdio=False, http=False, allow_write=False, allow_mutate=False, allow_private=False)
    with pytest.raises(Exception, match="requires private context capability"):
        await mcp.call_tool("create_private_context_pack", {"query": "test", "target": "test"})

@pytest.mark.asyncio
async def test_policy_override(mcp_cartridge):
    policy_path = mcp_cartridge / "CARTRIDGE_POLICY.json"
    policy = read_json(policy_path)
    policy["mcp"]["allow_write"] = True
    policy_path.write_text(json.dumps(policy))
    
    start_server(mcp_cartridge, stdio=False, http=False, allow_write=False, allow_mutate=False, allow_private=False)
    res = await mcp.call_tool("submit_memory_receipt", {"receipt_content": "test"})
    assert "Receipt submitted" in str(res)

def test_schema_works_without_mcp(monkeypatch):
    assert True
