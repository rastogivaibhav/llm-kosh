import os
import json
from pathlib import Path
from functools import wraps
from typing import Dict, Any, List

from mcp.server.fastmcp import FastMCP

from llm_kosh.engine.search import query_memory, semantic_search, get_memory_map, get_project_context
from llm_kosh.engine.commands import verify_ledger
from llm_kosh.engine.compiler import pack_context
from llm_kosh.engine.intake import intake_scan, intake_list, processor_apply
from llm_kosh.core.utils import append_ledger, read_json

# Global flags set during startup
MCP_FLAGS = {
    "allow_write": False,
    "allow_mutate": False,
    "allow_private": False,
}

WORKSPACE_PATH = Path(os.environ.get("CARTRIDGE_WORKSPACE", "."))

mcp = FastMCP("Cartridge Memory Server", dependencies=["mcp", "pydantic"])

def require_capability(cap: str):
    """Decorator to gate tools based on CLI flags and policy config."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Check policy if exists
            policy_path = WORKSPACE_PATH / "CARTRIDGE_POLICY.json"
            policy = read_json(policy_path) if policy_path.exists() else {}
            mcp_policy = policy.get("mcp", {})
            
            # Write operations
            if cap == "write":
                if not MCP_FLAGS["allow_write"] and not mcp_policy.get("allow_write", False):
                    raise PermissionError("Tool requires write capability. Start MCP server with --allow-write.")
                append_ledger(WORKSPACE_PATH, "mcp.write_action", {"tool": func.__name__})
                
            # Mutate operations (subset of write, implies higher trust)
            elif cap == "mutate":
                if not MCP_FLAGS["allow_mutate"] and not mcp_policy.get("allow_mutation", False):
                    raise PermissionError("Tool requires mutation capability. Start MCP server with --allow-mutate.")
                append_ledger(WORKSPACE_PATH, "mcp.mutate_action", {"tool": func.__name__})
                
            # Private export operations
            elif cap == "private":
                if not MCP_FLAGS["allow_private"] and not mcp_policy.get("allow_private_exports", False):
                    raise PermissionError("Tool requires private context capability. Start MCP server with --allow-private.")
                append_ledger(WORKSPACE_PATH, "mcp.private_export", {"tool": func.__name__})
                
            return func(*args, **kwargs)
        return wrapper
    return decorator


# --- READ OPERATIONS ---

@mcp.tool()
def search_memory(query: str, limit: int = 10, use_semantic: bool = False):
    """Search the Cartridge Knowledge Base for memories, decisions, and files."""
    if use_semantic:
        results = semantic_search(WORKSPACE_PATH, query, k=limit)
    else:
        results = query_memory(WORKSPACE_PATH, query, limit=limit)
    
    output = []
    for r in results:
        output.append(f"[{r.get('kind', 'note').upper()}] {r.get('title', 'Untitled')} ({r.get('path', '')})\n{r.get('snippet', '')}\n")
    return "\n---\n".join(output) if output else "No results found."

@mcp.tool()
def get_cartridge_memory_map():
    """Returns a structural map of the knowledge base projects and active concepts."""
    return json.dumps(get_memory_map(WORKSPACE_PATH), indent=2)

@mcp.tool()
def get_project_context(project_name: str):
    """Fetches all context and active decisions for a specific project."""
    return json.dumps(get_project_context(WORKSPACE_PATH, project_name), indent=2)

@mcp.tool()
def list_intake(status: str = "pending"):
    """Lists the current items pending in the intake queue."""
    res = intake_list(WORKSPACE_PATH, status="pending")
    return json.dumps(res, indent=2)

@mcp.tool()
def get_daemon_status():
    """Verifies the cryptographic ledger of the Cartridge."""
    try:
        report = verify_ledger(WORKSPACE_PATH, quiet=True)
        return json.dumps(report, indent=2)
    except Exception as e:
        return f"Ledger verify failed: {e}"

# --- EXPORT OPERATIONS ---

@mcp.tool()
@require_capability("private")
def create_private_context_pack(query: str, target: str = "llm"):
    """
    Creates a highly focused context pack for a specific task.
    Includes private and sensitive information.
    """
    out_dir = WORKSPACE_PATH / "exports"
    out_dir.mkdir(exist_ok=True)
    dest = out_dir / "mcp_pack.zip"
    pack_context(WORKSPACE_PATH, query, target, dest, include_private=True, quiet=True)
    return f"Created private context pack at {dest}"


# --- WRITE OPERATIONS ---

@mcp.tool()
@require_capability("write")
def submit_memory_receipt(receipt_content: str):
    """
    Submits a MEMORY_RECEIPT.md formatted string to the intake queue.
    Does not apply it directly; it must be reviewed and applied.
    """
    import uuid
    inbox_dir = WORKSPACE_PATH / "inbox"
    inbox_dir.mkdir(exist_ok=True)
    file_id = f"receipt_{uuid.uuid4().hex[:8]}.md"
    dest = inbox_dir / file_id
    dest.write_text(receipt_content, encoding="utf-8")
    # Scan it so it shows up in intake immediately
    intake_scan(WORKSPACE_PATH)
    return f"Receipt submitted to inbox as {file_id}. Awaiting review/application."

@mcp.tool()
@require_capability("write")
def intake_convert_file(file_path: str, project: str = ""):
    """
    Converts a local file (e.g. PDF, DOCX, XLSX, PPTX, PNG, WAV) to structured markdown 
    using the MarkItDown converter and ingests it into the cartridge.
    """
    from llm_kosh.engine.intake import intake_file_or_dir
    try:
        path = Path(file_path).expanduser().resolve()
        if not path.exists():
            return f"Error: File not found at path {file_path}"
        res = intake_file_or_dir(WORKSPACE_PATH, path, project=project, visibility="private")
        return f"Ingestion completed: added {res['added']} memory items, failed {res['failed']}"
    except Exception as e:
        return f"Failed to ingest and convert file: {e}"


# --- MUTATE OPERATIONS ---

@mcp.tool()
@require_capability("mutate")
def apply_intake_proposal(batch_id: str):
    """
    Directly applies an intake proposal batch to the live memory.
    """
    try:
        res = processor_apply(WORKSPACE_PATH, batch_id)
        return f"Successfully applied batch {batch_id}: {res}"
    except Exception as e:
        return f"Failed to apply batch: {e}"


# --- SERVER STARTUP ---

def start_server(root: Path, stdio: bool = True, http: bool = False, port: int = 8000, 
                 allow_write: bool = False, allow_mutate: bool = False, allow_private: bool = False):
    """Starts the MCP server with the specified configuration."""
    global WORKSPACE_PATH
    WORKSPACE_PATH = root
    
    MCP_FLAGS["allow_write"] = allow_write
    MCP_FLAGS["allow_mutate"] = allow_mutate
    MCP_FLAGS["allow_private"] = allow_private

    if stdio:
        mcp.run()
    elif http:
        # Note: FastMCP run currently wraps stdio, but can hook into ASGI/http if needed.
        # Anthropic standard favors stdio for local tools. 
        # For HTTP, we just print the intention or rely on internal FastMCP ASGI.
        print(f"Starting MCP on http://localhost:{port} (If supported by underlying FastMCP)")
        mcp.run()

def get_mcp_tools_schema(root: Path) -> str:
    """Returns the JSON schema of available tools."""
    tools = []
    
    # Try looking at ._tools or .tools if it's there
    tool_manager = getattr(mcp, "_tool_manager", None)
    tool_dict = getattr(tool_manager, "_tools", {})
    if not tool_dict:
        tool_dict = getattr(mcp, "_tools", getattr(mcp, "tools", {}))

    for t in getattr(tool_dict, "values", lambda: [])():
        tools.append({
            "name": t.name,
            "description": t.description
        })
    return json.dumps(tools, indent=2)
