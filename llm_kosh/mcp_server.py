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


# --- REASONING TOOLS ---

@mcp.tool()
def reasoning_ingest(
    content: str,
    documented_at: str,
    valid_from: str,
    valid_until: str = "",
    confidence: float = 0.8,
    causal_edges: str = "[]",
):
    """
    Add a new fact to the Temporal Causal Reasoning Graph.
    documented_at and valid_from are ISO 8601 datetime strings.
    causal_edges: JSON array of {"target_id": str, "edge_type": str, "confidence": float}.
    Returns the new fact_id.
    """
    import json as _json
    from datetime import datetime, timezone
    from llm_kosh.engine.reasoning import ReasoningEngine

    def _parse(s: str) -> datetime:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))

    engine = ReasoningEngine(WORKSPACE_PATH)
    try:
        edges = _json.loads(causal_edges) if causal_edges else []
    except Exception:
        edges = []

    fact_id = engine.ingest(
        content=content,
        documented_at=_parse(documented_at),
        valid_from=_parse(valid_from),
        valid_until=_parse(valid_until) if valid_until else None,
        confidence=confidence,
        causal_edges=edges,
    )
    return _json.dumps({"fact_id": fact_id, "status": "ingested"})


@mcp.tool()
def reasoning_query(
    query: str,
    temporal_context: str = "",
    depth: int = 3,
):
    """
    Query the Temporal Causal Reasoning Graph.
    Returns a fiber bundle with stability score, escape metadata, and all causal paths.
    temporal_context: ISO 8601 datetime or Unix timestamp string (omit for now).
    """
    import json as _json
    from llm_kosh.engine.reasoning import ReasoningEngine

    engine = ReasoningEngine(WORKSPACE_PATH)
    result = engine.query(query, temporal_context=temporal_context or None, depth=depth)

    bundle_out = {}
    for fid, fiber in result.bundle.fibers.items():
        if fid == "__deep_instability__":
            continue
        bundle_out[fid] = {
            "fact": {
                "id": fiber.fact.id if fiber.fact else fid,
                "content": fiber.fact.content if fiber.fact else "",
                "valid_from": fiber.fact.valid_from.isoformat() if fiber.fact else "",
                "valid_until": fiber.fact.valid_until.isoformat() if (fiber.fact and fiber.fact.valid_until) else None,
                "confidence": fiber.fact.confidence if fiber.fact else 0.0,
            },
            "paths": [
                {
                    "edge_count": len(p.edges),
                    "confidence_product": p.confidence_product,
                    "temporal_consistency": p.temporal_consistency,
                }
                for p in fiber.paths
            ],
            "degeneracy": fiber.degeneracy,
            "max_confidence": fiber.max_confidence,
        }

    return _json.dumps({
        "anchors": result.anchors,
        "bundle": bundle_out,
        "stability": {
            "score": result.stability.score,
            "status": result.stability.status,
            "dimensions": result.stability.dimensions,
            "escape_triggered": result.escape_triggered,
            "escape_surfaced": result.escape_surfaced,
        },
    })


@mcp.tool()
def reasoning_critique(fact_ids: List[str]):
    """
    Run the Lyapunov critic on a specific list of fact IDs.
    Returns stability score, status, and per-dimension breakdown.
    """
    import json as _json
    from llm_kosh.engine.reasoning import ReasoningEngine

    engine = ReasoningEngine(WORKSPACE_PATH)
    result = engine.critique(fact_ids)
    return _json.dumps({
        "score": result.score,
        "status": result.status,
        "dimensions": result.dimensions,
        "implicated_facts": result.implicated_facts,
    })


@mcp.tool()
def reasoning_explore(from_fact_id: str, to_fact_id: str, max_hops: int = 5):
    """
    Enumerate all causal paths between two known facts.
    Returns the fiber bundle for that specific pair.
    """
    import json as _json
    from llm_kosh.engine.reasoning import ReasoningEngine

    engine = ReasoningEngine(WORKSPACE_PATH)
    bundle = engine.explore(from_fact_id, to_fact_id, max_hops=max_hops)

    fibers_out = {}
    for fid, fiber in bundle.fibers.items():
        fibers_out[fid] = {
            "paths": [
                {
                    "edges": [
                        {"source": e.source_id, "target": e.target_id,
                         "type": e.edge_type.value, "confidence": e.confidence}
                        for e in p.edges
                    ],
                    "confidence_product": p.confidence_product,
                    "temporal_consistency": p.temporal_consistency,
                }
                for p in fiber.paths
            ],
            "degeneracy": fiber.degeneracy,
            "max_confidence": fiber.max_confidence,
        }
    return _json.dumps({"fibers": fibers_out})


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
