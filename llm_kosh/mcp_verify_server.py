"""MCP server surface with Kosh Verify registered as a read-only tool.

This module deliberately composes the existing MCP server instead of copying
its tool set or permission model. All existing read/write/mutate/private-export
boundaries remain owned by :mod:`llm_kosh.mcp_server`; this module adds one
read-only verification tool and delegates startup to the same server object.
"""

from __future__ import annotations

from llm_kosh import mcp_server as _base
from llm_kosh.verify import KoshVerify

mcp = _base.mcp
start_server = _base.start_server
get_mcp_tools_schema = _base.get_mcp_tools_schema


@mcp.tool()
def kosh_verify(
    query: str,
    temporal_context: str = "",
    depth: int = 4,
    dialectic: bool = True,
):
    """Verify a question against local temporal/causal evidence.

    This is read-only. The returned JSON report can include supporting facts,
    causal paths, contradictions, inferred-but-not-discovered relationships,
    missing evidence, stability information, and an explicit abstention state.

    It does not consult the internet, seed demo data, write or mutate memory,
    export private context, or make an imported source trustworthy.
    """
    report = KoshVerify(_base.WORKSPACE_PATH).verify(
        query,
        temporal_context=temporal_context or None,
        depth=depth,
        dialectic=dialectic,
    )
    return report.to_json(indent=2)


def main() -> None:
    """Run the standard LLM-Kosh MCP server with Kosh Verify registered."""
    _base.main()


if __name__ == "__main__":
    main()
