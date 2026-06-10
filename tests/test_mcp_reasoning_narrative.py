"""Tests that reasoning_query MCP tool returns narrative by default."""
import pytest
from pathlib import Path
from tempfile import TemporaryDirectory
from datetime import datetime, timezone

mcp = pytest.importorskip("mcp", reason="mcp package not installed")


def _make_engine(root: Path):
    from llm_kosh.engine.reasoning import ReasoningEngine
    return ReasoningEngine(root)


def test_reasoning_query_narrative_default():
    """reasoning_query returns string narrative by default."""
    with TemporaryDirectory() as t:
        root = Path(t)
        from llm_kosh.core.memory import init_cartridge
        init_cartridge(root, "test")
        engine = _make_engine(root)
        now = datetime.now(timezone.utc)
        engine.ingest("PostgreSQL auth decision", now, now, None, 0.9, [])

        # Patch WORKSPACE_PATH and call tool function directly
        import llm_kosh.mcp_server as mcp_mod
        original_ws = mcp_mod.WORKSPACE_PATH
        try:
            mcp_mod.WORKSPACE_PATH = root
            result = mcp_mod.reasoning_query("PostgreSQL")
        finally:
            mcp_mod.WORKSPACE_PATH = original_ws

        # Should be a string (narrative), not JSON
        assert isinstance(result, str)
        # Should contain CAUSAL TIMELINE header or empty chain message
        assert "CAUSAL TIMELINE" in result or "No causal chain found" in result


def test_reasoning_query_json_false():
    """reasoning_query with narrative=False returns JSON string."""
    import json
    with TemporaryDirectory() as t:
        root = Path(t)
        from llm_kosh.core.memory import init_cartridge
        init_cartridge(root, "test")
        engine = _make_engine(root)
        now = datetime.now(timezone.utc)
        engine.ingest("PostgreSQL auth decision", now, now, None, 0.9, [])

        import llm_kosh.mcp_server as mcp_mod
        original_ws = mcp_mod.WORKSPACE_PATH
        try:
            mcp_mod.WORKSPACE_PATH = root
            result = mcp_mod.reasoning_query("PostgreSQL", narrative=False)
        finally:
            mcp_mod.WORKSPACE_PATH = original_ws

        # Should be valid JSON
        parsed = json.loads(result)
        assert "anchors" in parsed
        assert "bundle" in parsed
        assert "stability" in parsed


def test_reasoning_query_empty_narrative():
    """reasoning_query on empty cartridge returns no-chain message."""
    with TemporaryDirectory() as t:
        root = Path(t)
        from llm_kosh.core.memory import init_cartridge
        init_cartridge(root, "test")

        import llm_kosh.mcp_server as mcp_mod
        original_ws = mcp_mod.WORKSPACE_PATH
        try:
            mcp_mod.WORKSPACE_PATH = root
            result = mcp_mod.reasoning_query("nothing here")
        finally:
            mcp_mod.WORKSPACE_PATH = original_ws

        assert isinstance(result, str)
        assert "No causal chain found" in result
