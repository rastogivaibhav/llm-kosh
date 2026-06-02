from mcp.server.fastmcp import FastMCP
from pathlib import Path
import json

from koush.engine.search import query_memory, semantic_search
from koush.engine.commands import verify_ledger

mcp = FastMCP("Cartridge Memory Server", dependencies=["mcp", "pydantic"])

# We assume the MCP server is initialized with an environment variable 
# or default workspace path if started independently.
import os
WORKSPACE_PATH = Path(os.environ.get("CARTRIDGE_WORKSPACE", "."))

@mcp.tool()
def search_cartridge(query: str, limit: int = 10, use_semantic: bool = False) -> str:
    """
    Search the Cartridge Knowledge Base for memories, decisions, and files.
    """
    if use_semantic:
        results = semantic_search(WORKSPACE_PATH, query, k=limit)
    else:
        results = query_memory(WORKSPACE_PATH, query, limit=limit)
    
    output = []
    for r in results:
        output.append(f"[{r.get('kind', 'note').upper()}] {r.get('title', 'Untitled')} ({r.get('path', '')})\n{r.get('snippet', '')}\n")
    
    return "\n---\n".join(output) if output else "No results found."

@mcp.tool()
def heal_ledger() -> str:
    """
    Verifies and attempts to heal the cryptographic ledger of the Cartridge.
    """
    try:
        report = verify_ledger(WORKSPACE_PATH, quiet=True)
        return json.dumps(report, indent=2)
    except Exception as e:
        return f"Ledger heal failed: {e}"

if __name__ == "__main__":
    print(f"Starting Cartridge MCP Server on stdio... (Workspace: {WORKSPACE_PATH})")
    mcp.run()
