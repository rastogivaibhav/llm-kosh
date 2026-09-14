"""MCP composition that adds governed Trusted Memory tools to Kosh Verify.

The module deliberately composes the existing MCP server and Kosh Verify surface
rather than copying transport or permission logic. Read operations remain
read-only. Proposals require the existing ``write`` capability and explicit
lifecycle review requires the existing ``mutate`` capability.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Dict, List, Optional, Sequence

from llm_kosh import mcp_server as _base
from llm_kosh import mcp_verify_server as _verify
from llm_kosh.company_brain.models import AccessPolicy, EvidenceInput, Principal
from llm_kosh.company_brain.store import CompanyBrainStore
from llm_kosh.runtime.models import MemoryProposal, MemorySource, RetrievalMode
from llm_kosh.runtime.persistence import RuntimeStore
from llm_kosh.runtime.review import TrustedMemoryReviewer
from llm_kosh.runtime.service import TrustedMemoryRuntime

mcp = _verify.mcp
start_server = _verify.start_server
get_mcp_tools_schema = _verify.get_mcp_tools_schema


def _json_list(value: str, *, field_name: str) -> List[str]:
    try:
        parsed = json.loads(value or "[]")
    except json.JSONDecodeError as exc:
        raise ValueError(f"{field_name} must be a JSON array") from exc
    if not isinstance(parsed, list):
        raise ValueError(f"{field_name} must be a JSON array")
    return [str(item).strip() for item in parsed if str(item).strip()]


def _principal(
    principal_id: str,
    tenant_id: str,
    groups_json: str,
    projects_json: str,
    clearance: str,
    *,
    project_id: str = "",
) -> Principal:
    projects = _json_list(projects_json, field_name="projects_json")
    if project_id and project_id not in projects:
        projects.append(project_id)
    return Principal(
        principal_id=principal_id,
        tenant_id=tenant_id,
        groups=_json_list(groups_json, field_name="groups_json"),
        projects=projects,
        clearance=clearance,
    )


def _with_latest_assessment(items: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    runtime_store = RuntimeStore(_base.WORKSPACE_PATH)
    enriched: List[Dict[str, Any]] = []
    for original in items:
        item = dict(original)
        history = runtime_store.list_assessments(str(item["memory_id"]))
        latest = history[-1] if history else {}
        item["conflict_state"] = latest.get("conflict_state") or "none"
        item["conflicting_memory_ids"] = list(latest.get("conflicting_memory_ids") or [])
        item["admission_reasons"] = list(latest.get("reasons") or [])
        enriched.append(item)
    return enriched


def _proposal_evidence(
    *,
    principal: Principal,
    evidence_id: str,
    title: str,
    statement: str,
    classification: str,
    observed_at: str,
    source_native_id: str,
) -> tuple[str, str, str]:
    """Return evidence id, recorded source type, and native source id.

    Existing evidence is authoritative for its own source metadata. A client
    cannot relabel a stored web/document/tool source as direct user evidence.
    When no evidence id is supplied, MCP-created evidence is deliberately marked
    as ``agent_observation`` and therefore cannot inherit user-direct authority.
    """

    store = CompanyBrainStore(_base.WORKSPACE_PATH)
    if evidence_id:
        inspection = store.inspect_evidence(evidence_id, principal, strong=True)
        if inspection["tenant_id"] != principal.tenant_id:
            raise PermissionError("Evidence tenant does not match the proposing principal")
        return (
            evidence_id,
            str(inspection.get("source_type") or MemorySource.UNKNOWN.value),
            source_native_id.strip() or str(inspection.get("source_native_id") or ""),
        )

    payload = f"{title.strip()}\n\n{statement.strip()}\n".encode("utf-8")
    if source_native_id.strip():
        native_id = source_native_id.strip()
    else:
        canonical = "\x1f".join(
            (
                principal.tenant_id,
                principal.principal_id,
                title.strip(),
                statement.strip(),
            )
        )
        native_id = "mcp-agent:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:24]

    created_id = store.put_evidence(
        EvidenceInput(
            tenant_id=principal.tenant_id,
            source_type=MemorySource.AGENT_OBSERVATION.value,
            source_locator="mcp://trusted-memory/proposal",
            source_native_id=native_id,
            content=payload,
            mime_type="text/plain",
            storage_mode="managed",
            artifact_type="plain_text",
            observed_at=observed_at,
            classification=classification,
            access_policy=AccessPolicy(allowed_principals=[principal.principal_id]),
        )
    )
    return created_id, MemorySource.AGENT_OBSERVATION.value, native_id


@mcp.tool()
def trusted_memory_recall(
    query: str = "",
    principal_id: str = "local-user",
    tenant_id: str = "local",
    groups_json: str = "[]",
    projects_json: str = "[]",
    clearance: str = "restricted",
    project_id: str = "",
    memory_types_json: str = "[]",
    as_of: str = "",
    mode: str = "normal",
    limit: int = 10,
):
    """Recall governed memory with admission and lifecycle policy enforced."""
    principal = _principal(
        principal_id,
        tenant_id,
        groups_json,
        projects_json,
        clearance,
        project_id=project_id,
    )
    retrieval_mode = RetrievalMode(mode.strip().lower())
    items = TrustedMemoryRuntime(_base.WORKSPACE_PATH).recall(
        query,
        principal,
        project_id=project_id,
        memory_types=_json_list(memory_types_json, field_name="memory_types_json") or None,
        as_of=as_of,
        mode=retrieval_mode,
        limit=limit,
    )
    return json.dumps(items, indent=2)


@mcp.tool()
def trusted_memory_inbox(
    query: str = "",
    principal_id: str = "local-user",
    tenant_id: str = "local",
    groups_json: str = "[]",
    projects_json: str = "[]",
    clearance: str = "restricted",
    project_id: str = "",
    limit: int = 50,
):
    """List authorized candidate and quarantined Trusted Memory items."""
    principal = _principal(
        principal_id,
        tenant_id,
        groups_json,
        projects_json,
        clearance,
        project_id=project_id,
    )
    items = TrustedMemoryRuntime(_base.WORKSPACE_PATH).recall(
        query,
        principal,
        project_id=project_id,
        mode=RetrievalMode.CANDIDATE,
        limit=limit,
    )
    return json.dumps(_with_latest_assessment(items), indent=2)


@mcp.tool()
def trusted_memory_conflicts(
    query: str = "",
    principal_id: str = "local-user",
    tenant_id: str = "local",
    groups_json: str = "[]",
    projects_json: str = "[]",
    clearance: str = "restricted",
    project_id: str = "",
    limit: int = 100,
):
    """List unresolved authorized Trusted Memory conflicts."""
    principal = _principal(
        principal_id,
        tenant_id,
        groups_json,
        projects_json,
        clearance,
        project_id=project_id,
    )
    items = TrustedMemoryRuntime(_base.WORKSPACE_PATH).recall(
        query,
        principal,
        project_id=project_id,
        mode=RetrievalMode.CANDIDATE,
        limit=limit,
    )
    enriched = _with_latest_assessment(items)
    return json.dumps(
        [item for item in enriched if item.get("conflict_state") != "none"],
        indent=2,
    )


@mcp.tool()
def trusted_memory_explain(
    memory_id: str,
    principal_id: str = "local-user",
    tenant_id: str = "local",
    groups_json: str = "[]",
    projects_json: str = "[]",
    clearance: str = "restricted",
):
    """Explain one authorized memory with evidence and admission history."""
    principal = _principal(
        principal_id,
        tenant_id,
        groups_json,
        projects_json,
        clearance,
    )
    result = TrustedMemoryRuntime(_base.WORKSPACE_PATH).explain(memory_id, principal)
    return json.dumps(result, indent=2)


@mcp.tool()
@_base.require_capability("write")
def trusted_memory_propose(
    memory_type: str,
    title: str,
    statement: str,
    principal_id: str = "local-user",
    tenant_id: str = "local",
    groups_json: str = "[]",
    projects_json: str = "[]",
    clearance: str = "restricted",
    project_id: str = "",
    classification: str = "restricted",
    evidence_id: str = "",
    observed_at: str = "",
    confidence: Optional[float] = None,
    source_native_id: str = "",
    subject: str = "",
    predicate: str = "",
    object_value: str = "",
    supersedes_json: str = "[]",
):
    """Propose governed memory. Requires MCP write capability.

    If ``evidence_id`` is omitted, the proposal is persisted as an
    ``agent_observation``. Agents cannot self-label new MCP evidence as
    ``user_direct``. To preserve a stronger or different source type, register
    evidence first and pass its existing id.
    """
    principal = _principal(
        principal_id,
        tenant_id,
        groups_json,
        projects_json,
        clearance,
        project_id=project_id,
    )
    actual_evidence_id, source_type, native_id = _proposal_evidence(
        principal=principal,
        evidence_id=evidence_id.strip(),
        title=title,
        statement=statement,
        classification=classification,
        observed_at=observed_at,
        source_native_id=source_native_id,
    )
    supersedes = _json_list(supersedes_json, field_name="supersedes_json")
    metadata: Dict[str, Any] = {}
    if supersedes:
        metadata["supersedes"] = list(dict.fromkeys(supersedes))

    result = TrustedMemoryRuntime(_base.WORKSPACE_PATH).propose(
        MemoryProposal(
            memory_type=memory_type,
            title=title,
            statement=statement,
            evidence_ids=[actual_evidence_id],
            source_type=source_type,
            project_id=project_id,
            observed_at=observed_at,
            confidence=confidence,
            classification=classification,
            principal_id=principal.principal_id,
            source_native_id=native_id,
            subject=subject,
            predicate=predicate,
            object_value=object_value,
            metadata=metadata,
        ),
        principal,
    )
    return json.dumps(
        {
            **result,
            "evidence_id": actual_evidence_id,
            "evidence_source_type": source_type,
        },
        indent=2,
    )


@mcp.tool()
@_base.require_capability("mutate")
def trusted_memory_review(
    memory_id: str,
    action: str,
    reason: str,
    principal_id: str = "local-user",
    tenant_id: str = "local",
    groups_json: str = "[]",
    projects_json: str = "[]",
    clearance: str = "restricted",
    supersede_ids_json: str = "[]",
):
    """Explicitly approve, quarantine, reject, or supersede governed memory.

    Requires the existing MCP mutate capability. Conflict resolution is never
    inferred from a generic approval.
    """
    principal = _principal(
        principal_id,
        tenant_id,
        groups_json,
        projects_json,
        clearance,
    )
    result = TrustedMemoryReviewer(_base.WORKSPACE_PATH).review(
        memory_id,
        principal,
        action=action,
        reason=reason,
        supersede_ids=_json_list(supersede_ids_json, field_name="supersede_ids_json"),
    )
    return json.dumps(result, indent=2)


def main() -> None:
    """Run the composed MCP server with Kosh Verify and Trusted Memory tools."""
    _verify.main()


if __name__ == "__main__":
    main()
