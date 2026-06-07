import pytest
import json
from pathlib import Path
from llm_kosh.core.memory import init_cartridge
from llm_kosh.mcp_server import mcp, start_server


def _extract_text(res) -> str:
    """FastMCP call_tool returns a list of TextContent objects; extract the text."""
    if isinstance(res, str):
        return res
    if isinstance(res, list) and res:
        item = res[0]
        if hasattr(item, "text"):
            return item.text
    return str(res)


@pytest.fixture
def mcp_cartridge(tmp_path):
    init_cartridge(tmp_path, "MCP Reasoning Test")
    start_server(tmp_path, stdio=False, http=False,
                 allow_write=True, allow_mutate=False, allow_private=False)
    return tmp_path

@pytest.mark.asyncio
async def test_reasoning_ingest_tool(mcp_cartridge):
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).isoformat()
    res = await mcp.call_tool("reasoning_ingest", {
        "content": "Test memory from MCP",
        "documented_at": now,
        "valid_from": now,
        "confidence": 0.9,
    })
    assert "fact." in _extract_text(res)

@pytest.mark.asyncio
async def test_reasoning_query_tool(mcp_cartridge):
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).isoformat()
    await mcp.call_tool("reasoning_ingest", {
        "content": "Apples fall due to gravity",
        "documented_at": now,
        "valid_from": now,
        "confidence": 0.9,
    })
    res = await mcp.call_tool("reasoning_query", {"query": "gravity apples"})
    data = json.loads(_extract_text(res))
    assert "anchors" in data
    assert "bundle" in data
    assert "stability" in data

@pytest.mark.asyncio
async def test_reasoning_critique_tool(mcp_cartridge):
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).isoformat()
    ingest_res = await mcp.call_tool("reasoning_ingest", {
        "content": "Fact to critique",
        "documented_at": now,
        "valid_from": now,
        "confidence": 0.8,
    })
    ingest_text = _extract_text(ingest_res)
    fact_id = ingest_text.split("fact.")[1].split('"')[0]
    fact_id = "fact." + fact_id
    res = await mcp.call_tool("reasoning_critique", {"fact_ids": [fact_id]})
    data = json.loads(_extract_text(res))
    assert "score" in data
    assert "status" in data

@pytest.mark.asyncio
async def test_reasoning_explore_tool(mcp_cartridge):
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).isoformat()
    fid1_raw = await mcp.call_tool("reasoning_ingest", {
        "content": "Source fact",
        "documented_at": now,
        "valid_from": now,
        "confidence": 0.9,
    })
    fid2_raw = await mcp.call_tool("reasoning_ingest", {
        "content": "Target fact",
        "documented_at": now,
        "valid_from": now,
        "confidence": 0.9,
    })
    # explore with no path — should return empty bundle gracefully
    fid1_text = _extract_text(fid1_raw)
    fid2_text = _extract_text(fid2_raw)
    fid1 = fid1_text.split('"fact_id": "')[1].split('"')[0] if '"fact_id"' in fid1_text else "fact.missing"
    fid2 = fid2_text.split('"fact_id": "')[1].split('"')[0] if '"fact_id"' in fid2_text else "fact.missing"
    res = await mcp.call_tool("reasoning_explore", {"from_fact_id": fid1, "to_fact_id": fid2})
    data = json.loads(_extract_text(res))
    assert "fibers" in data
