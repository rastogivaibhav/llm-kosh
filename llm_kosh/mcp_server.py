import os
import json
from pathlib import Path
from functools import wraps
from typing import Dict, Any, List

try:
    from mcp.server.fastmcp import FastMCP  # type: ignore
    _HAS_MCP = True
except ModuleNotFoundError:  # pragma: no cover - exercised in minimal CI/sandbox
    _HAS_MCP = False
    class _FallbackTool:
        def __init__(self, name, func):
            self.name = name
            self.description = (func.__doc__ or "").strip()
            self.func = func

    class _FallbackToolManager:
        def __init__(self):
            self._tools = {}

    class FastMCP:  # minimal test/dev fallback when optional mcp package is absent
        def __init__(self, name: str, dependencies=None):
            self.name = name
            self.dependencies = dependencies or []
            self._tool_manager = _FallbackToolManager()

        def tool(self):
            def decorator(func):
                self._tool_manager._tools[func.__name__] = _FallbackTool(func.__name__, func)
                return func
            return decorator

        async def call_tool(self, name: str, arguments=None):
            arguments = arguments or {}
            tool = self._tool_manager._tools[name]
            return tool.func(**arguments)

        def run(self):
            return None

from llm_kosh.engine.search import query_memory, semantic_search, get_memory_map, get_project_context
from llm_kosh.engine.commands import verify_ledger
from llm_kosh.engine.compiler import pack_context
from llm_kosh.engine.intake import intake_scan, intake_list, processor_apply
from llm_kosh.core.utils import append_ledger, read_json
from llm_kosh.company_brain.context import compile_context as compile_brain_context
from llm_kosh.company_brain.models import (
    AccessPolicy, ContextRequest, EvidenceInput, EvidenceReference, MemoryInput, Principal,
)
from llm_kosh.company_brain.retrieval import search_memories as search_company_memories
from llm_kosh.company_brain.store import CompanyBrainStore
from llm_kosh.company_brain.understanding import understand_evidence

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
    res = intake_list(WORKSPACE_PATH, status=status)
    return json.dumps(res, indent=2)

@mcp.tool()
def get_daemon_status():
    """Verifies the cryptographic ledger of the Cartridge."""
    try:
        report = verify_ledger(WORKSPACE_PATH, quiet=True)
        return json.dumps(report, indent=2)
    except Exception as e:
        return f"Ledger verify failed: {e}"


def _json_list(value: str) -> List[str]:
    try:
        parsed = json.loads(value or "[]")
    except json.JSONDecodeError:
        parsed = []
    return [str(item) for item in parsed] if isinstance(parsed, list) else []


def _brain_principal(
    principal_id: str, tenant_id: str, groups_json: str,
    projects_json: str, clearance: str,
) -> Principal:
    return Principal(
        principal_id=principal_id,
        tenant_id=tenant_id,
        groups=_json_list(groups_json),
        projects=_json_list(projects_json),
        clearance=clearance,
    )


@mcp.tool()
def company_memory_search(
    query: str,
    principal_id: str = "local-user",
    tenant_id: str = "local",
    groups_json: str = "[]",
    projects_json: str = "[]",
    clearance: str = "restricted",
    project_id: str = "",
    memory_types_json: str = "[]",
    as_of: str = "",
    limit: int = 10,
    include_candidates: bool = False,
):
    """Permission-first hybrid search over atomic, evidence-backed company memory."""
    store = CompanyBrainStore(WORKSPACE_PATH)
    results = search_company_memories(
        store,
        query,
        _brain_principal(principal_id, tenant_id, groups_json, projects_json, clearance),
        project_id=project_id,
        memory_types=_json_list(memory_types_json) or None,
        as_of=as_of,
        limit=limit,
        include_candidates=include_candidates,
    )
    return json.dumps(results, indent=2)


@mcp.tool()
def company_context_compile(
    task: str,
    principal_id: str = "local-user",
    tenant_id: str = "local",
    groups_json: str = "[]",
    projects_json: str = "[]",
    clearance: str = "restricted",
    project_id: str = "",
    memory_types_json: str = "[]",
    as_of: str = "",
    token_budget: int = 8000,
    include_candidates: bool = False,
):
    """Compile structured, cited, token-budgeted context for an agent task."""
    principal = _brain_principal(
        principal_id, tenant_id, groups_json, projects_json, clearance
    )
    pack = compile_brain_context(
        CompanyBrainStore(WORKSPACE_PATH),
        ContextRequest(
            task=task,
            principal=principal,
            project_id=project_id,
            memory_types=_json_list(memory_types_json),
            as_of=as_of,
            token_budget=token_budget,
        ),
        include_candidates=include_candidates,
    )
    return json.dumps(pack, indent=2)


@mcp.tool()
def company_memory_get(
    memory_id: str,
    principal_id: str = "local-user",
    tenant_id: str = "local",
    groups_json: str = "[]",
    projects_json: str = "[]",
    clearance: str = "restricted",
):
    """Get one authorized memory with its evidence references and lifecycle."""
    memory = CompanyBrainStore(WORKSPACE_PATH).get_memory(
        memory_id,
        _brain_principal(principal_id, tenant_id, groups_json, projects_json, clearance),
    )
    return json.dumps(memory, indent=2)


@mcp.tool()
def company_brain_health():
    """Validate canonical company-brain storage and projection consistency."""
    return json.dumps(CompanyBrainStore(WORKSPACE_PATH).health(), indent=2)


@mcp.tool()
def company_brain_evaluate():
    """Run reference storage, citation, and projection acceptance checks."""
    return json.dumps(CompanyBrainStore(WORKSPACE_PATH).evaluate(), indent=2)


@mcp.tool()
@require_capability("write")
def company_session_understand(
    evidence_id: str,
    principal_id: str = "local-user",
    tenant_id: str = "local",
    groups_json: str = "[]",
    projects_json: str = "[]",
    clearance: str = "restricted",
    dry_run: bool = False,
    source_type: str = "session_jsonl",
    session_native_id: str = "",
    project_id: str = "",
    max_events: int = 100000,
):
    """Build normalized sessions, episodes, and cited candidates from JSONL evidence."""
    result = understand_evidence(
        CompanyBrainStore(WORKSPACE_PATH), evidence_id,
        _brain_principal(principal_id, tenant_id, groups_json, projects_json, clearance),
        dry_run=dry_run, source_type=source_type,
        session_native_id=session_native_id, project_id=project_id,
        max_events=max_events,
    )
    return json.dumps(result, indent=2)


@mcp.tool()
def company_sessions_list(
    principal_id: str = "local-user",
    tenant_id: str = "local",
    groups_json: str = "[]",
    projects_json: str = "[]",
    clearance: str = "restricted",
    project_id: str = "",
    limit: int = 100,
):
    """List authorized normalized source sessions."""
    result = CompanyBrainStore(WORKSPACE_PATH).list_sessions(
        _brain_principal(principal_id, tenant_id, groups_json, projects_json, clearance),
        project_id=project_id, limit=limit,
    )
    return json.dumps(result, indent=2)


@mcp.tool()
def company_episodes_search(
    query: str = "",
    principal_id: str = "local-user",
    tenant_id: str = "local",
    groups_json: str = "[]",
    projects_json: str = "[]",
    clearance: str = "restricted",
    project_id: str = "",
    limit: int = 20,
):
    """Search authorized goal-oriented work episodes and observed outcomes."""
    store = CompanyBrainStore(WORKSPACE_PATH)
    principal = _brain_principal(
        principal_id, tenant_id, groups_json, projects_json, clearance,
    )
    result = (
        store.search_episodes(query, principal, project_id=project_id, limit=limit)
        if query else store.list_episodes(principal, project_id=project_id, limit=limit)
    )
    return json.dumps(result, indent=2)


@mcp.tool()
def company_episode_get(
    episode_id: str,
    principal_id: str = "local-user",
    tenant_id: str = "local",
    groups_json: str = "[]",
    projects_json: str = "[]",
    clearance: str = "restricted",
):
    """Get one authorized episode with ordered event and candidate provenance."""
    result = CompanyBrainStore(WORKSPACE_PATH).get_episode(
        episode_id,
        _brain_principal(principal_id, tenant_id, groups_json, projects_json, clearance),
    )
    return json.dumps(result, indent=2)


@mcp.tool()
@require_capability("write")
def company_artifact_register(
    file_path: str,
    artifact_type: str = "",
    source_native_id: str = "",
    classification: str = "restricted",
    tenant_id: str = "local",
):
    """Register an existing local artifact by fingerprint without copying its bytes."""
    import mimetypes as _mimetypes
    from llm_kosh.company_brain.artifacts import infer_artifact_type
    path = Path(file_path).expanduser().resolve(strict=True)
    mime_type = _mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    evidence_id = CompanyBrainStore(WORKSPACE_PATH).put_evidence(EvidenceInput(
        tenant_id=tenant_id,
        source_type="local_file",
        source_locator=str(path),
        source_native_id=source_native_id or str(path),
        storage_mode="reference",
        artifact_type=artifact_type or infer_artifact_type(path, mime_type),
        mime_type=mime_type,
        classification=classification,
    ))
    return json.dumps({
        "evidence_id": evidence_id,
        "storage_mode": "reference",
        "copied_source_bytes": 0,
    })


@mcp.tool()
def company_artifact_inspect(
    evidence_id: str,
    principal_id: str = "local-user",
    tenant_id: str = "local",
    groups_json: str = "[]",
    projects_json: str = "[]",
    clearance: str = "restricted",
    native_locator_json: str = "{}",
    max_text: int = 16000,
    metadata_only: bool = False,
):
    """Verify and inspect a bounded region of an authorized registered artifact."""
    try:
        locator = json.loads(native_locator_json or "{}")
    except json.JSONDecodeError as exc:
        raise ValueError("native_locator_json must be a JSON object") from exc
    if not isinstance(locator, dict):
        raise ValueError("native_locator_json must be a JSON object")
    result = CompanyBrainStore(WORKSPACE_PATH).inspect_evidence(
        evidence_id,
        _brain_principal(principal_id, tenant_id, groups_json, projects_json, clearance),
        strong=True,
        native_locator=locator,
        include_preview=not metadata_only,
        max_text=max_text,
    )
    return json.dumps(result, indent=2)


@mcp.tool()
@require_capability("write")
def company_artifact_segment(
    evidence_id: str,
    principal_id: str = "local-user",
    tenant_id: str = "local",
    groups_json: str = "[]",
    projects_json: str = "[]",
    clearance: str = "restricted",
    native_locator_json: str = "{}",
    max_text: int = 16000,
):
    """Inspect an artifact and persist bounded derived segments with native citations."""
    try:
        locator = json.loads(native_locator_json or "{}")
    except json.JSONDecodeError as exc:
        raise ValueError("native_locator_json must be a JSON object") from exc
    if not isinstance(locator, dict):
        raise ValueError("native_locator_json must be a JSON object")
    result = CompanyBrainStore(WORKSPACE_PATH).inspect_and_segment(
        evidence_id,
        _brain_principal(principal_id, tenant_id, groups_json, projects_json, clearance),
        native_locator=locator,
        max_text=max_text,
    )
    return json.dumps(result, indent=2)


@mcp.tool()
@require_capability("write")
def company_artifact_snapshot(
    evidence_id: str,
    principal_id: str = "local-user",
    tenant_id: str = "local",
    groups_json: str = "[]",
    projects_json: str = "[]",
    clearance: str = "restricted",
):
    """Explicitly materialize an authorized artifact into immutable snapshot storage."""
    snapshot_id = CompanyBrainStore(WORKSPACE_PATH).materialize_snapshot(
        evidence_id,
        _brain_principal(principal_id, tenant_id, groups_json, projects_json, clearance),
    )
    return json.dumps({
        "source_evidence_id": evidence_id,
        "snapshot_evidence_id": snapshot_id,
        "storage_mode": "snapshot",
    })


@mcp.tool()
@require_capability("write")
def company_memory_propose(
    memory_type: str,
    title: str,
    statement: str,
    evidence_content: str,
    rationale: str = "",
    project_id: str = "",
    classification: str = "restricted",
    tenant_id: str = "local",
    source_locator: str = "mcp://proposal",
    source_native_id: str = "",
):
    """Create immutable evidence and a non-authoritative candidate memory."""
    import uuid as _uuid
    store = CompanyBrainStore(WORKSPACE_PATH)
    native_id = source_native_id or _uuid.uuid4().hex
    evidence_id = store.put_evidence(EvidenceInput(
        tenant_id=tenant_id,
        source_type="mcp_proposal",
        source_locator=source_locator,
        source_native_id=native_id,
        content=evidence_content.encode("utf-8"),
        classification=classification,
    ))
    memory_id = store.add_memory(MemoryInput(
        tenant_id=tenant_id,
        memory_type=memory_type,
        title=title,
        statement=statement,
        rationale=rationale,
        project_id=project_id,
        lifecycle="candidate",
        confidence=0.5,
        importance=0.5,
        classification=classification,
        evidence=[EvidenceReference(evidence_id=evidence_id, locator=source_locator)],
        extractor={"kind": "mcp_proposal", "version": "company-brain-v1"},
        source_native_id="mcp:" + native_id,
    ))
    return json.dumps({"memory_id": memory_id, "evidence_id": evidence_id, "lifecycle": "candidate"})


@mcp.tool()
@require_capability("write")
def company_memory_propose_from_evidence(
    evidence_id: str,
    memory_type: str,
    title: str,
    statement: str,
    segment_id: str = "",
    native_locator: str = "",
    rationale: str = "",
    project_id: str = "",
    principal_id: str = "local-user",
    tenant_id: str = "local",
    groups_json: str = "[]",
    projects_json: str = "[]",
    clearance: str = "restricted",
    source_native_id: str = "",
):
    """Create a candidate semantic memory citing an existing registered artifact."""
    import uuid as _uuid
    store = CompanyBrainStore(WORKSPACE_PATH)
    principal = _brain_principal(
        principal_id, tenant_id, groups_json, projects_json, clearance
    )
    evidence = store.inspect_evidence(evidence_id, principal, strong=True)
    if evidence["availability"]["status"] != "available":
        raise ValueError("Evidence is not currently available and unchanged")
    memory_id = store.add_memory(MemoryInput(
        tenant_id=tenant_id,
        memory_type=memory_type,
        title=title,
        statement=statement,
        rationale=rationale,
        project_id=project_id,
        lifecycle="candidate",
        confidence=0.5,
        importance=0.5,
        classification=evidence["classification"],
        access_policy=AccessPolicy.from_dict(evidence["access_policy"]),
        evidence=[EvidenceReference(
            evidence_id=evidence_id,
            segment_id=segment_id,
            locator=native_locator,
        )],
        extractor={"kind": "mcp_existing_evidence", "version": "company-brain-v2"},
        source_native_id=source_native_id or "mcp-evidence:" + _uuid.uuid4().hex,
    ))
    return json.dumps({
        "memory_id": memory_id,
        "evidence_id": evidence_id,
        "segment_id": segment_id,
        "lifecycle": "candidate",
    })


@mcp.tool()
@require_capability("mutate")
def company_memory_review(
    memory_id: str,
    to_lifecycle: str,
    reason: str,
    principal_id: str = "local-reviewer",
    tenant_id: str = "local",
    groups_json: str = "[]",
    projects_json: str = "[]",
    clearance: str = "restricted",
):
    """Apply a governed lifecycle transition to an authorized memory."""
    result = CompanyBrainStore(WORKSPACE_PATH).transition_memory(
        memory_id,
        to_lifecycle,
        _brain_principal(principal_id, tenant_id, groups_json, projects_json, clearance),
        reason=reason,
    )
    return json.dumps(result, indent=2)

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
@require_capability("write")
def reasoning_ingest(
    content: str,
    documented_at: str,
    valid_from: str,
    valid_until: str = "",
    confidence: float = 0.8,
    causal_edges: str = "[]",
):
    """
    Add a bounded atomic fact to the Temporal Causal Reasoning Graph.
    This is a write operation and requires --allow-write.
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
    narrative: bool = True,
):
    """
    Query the Temporal Causal Reasoning Graph.
    By default returns a human-readable causal narrative (narrative=True).
    Set narrative=False to get raw JSON with full fiber bundle details.
    temporal_context: ISO 8601 datetime or Unix timestamp string (omit for now).
    """
    import json as _json
    from llm_kosh.engine.reasoning import ReasoningEngine
    from llm_kosh.engine.reasoning.formatter import format_narrative

    engine = ReasoningEngine(WORKSPACE_PATH)
    result = engine.query(query, temporal_context=temporal_context or None, depth=depth)

    if narrative:
        return format_narrative(result, query)

    # Raw JSON fallback (narrative=False)
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
    WORKSPACE_PATH = root.expanduser().resolve()
    
    MCP_FLAGS["allow_write"] = allow_write
    MCP_FLAGS["allow_mutate"] = allow_mutate
    MCP_FLAGS["allow_private"] = allow_private

    # stdio=False/http=False is intentionally supported as a configuration-only
    # mode for embedding and tests.
    if not stdio and not http:
        return

    if not _HAS_MCP:
        raise RuntimeError("MCP runtime is not installed. Reinstall with `pip install -U llm-kosh`.")

    from llm_kosh.core.utils import ensure_root
    ensure_root(WORKSPACE_PATH)

    if stdio:
        mcp.run(transport="stdio")
    elif http:
        mcp.settings.host = "127.0.0.1"
        mcp.settings.port = port
        print(f"MCP streamable HTTP listening on http://127.0.0.1:{port}/mcp")
        mcp.run(transport="streamable-http")

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


def main() -> None:
    """Run the MCP server directly with ``python -m llm_kosh.mcp_server``."""
    import argparse

    parser = argparse.ArgumentParser(description="llm-kosh MCP server")
    parser.add_argument(
        "--root",
        default=os.environ.get("CARTRIDGE_WORKSPACE", "."),
        help="Cartridge root (or set CARTRIDGE_WORKSPACE)",
    )
    transport = parser.add_mutually_exclusive_group()
    transport.add_argument("--stdio", action="store_true", help="Use stdio transport (default)")
    transport.add_argument("--http", action="store_true", help="Use streamable HTTP transport")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--allow-write", action="store_true")
    parser.add_argument("--allow-mutate", action="store_true")
    parser.add_argument("--allow-private", action="store_true")
    args = parser.parse_args()
    start_server(
        Path(args.root),
        stdio=not args.http,
        http=args.http,
        port=args.port,
        allow_write=args.allow_write,
        allow_mutate=args.allow_mutate,
        allow_private=args.allow_private,
    )


if __name__ == "__main__":
    main()
