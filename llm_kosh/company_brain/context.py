"""Structured, token-budgeted context compilation."""

from __future__ import annotations

import hashlib
from typing import Any, Dict, List

from llm_kosh.core.utils import now_iso

from .models import ContextRequest
from .retrieval import search_evidence, search_memories
from .store import CompanyBrainStore


SECTION_BY_TYPE = {
    "decision": "decisions",
    "constraint": "constraints",
    "task": "open_work",
    "question": "open_questions",
    "risk": "risks",
    "outcome": "outcomes",
    "procedure": "procedures",
}


def _tokens(value: str) -> int:
    return max(1, (len(value) + 3) // 4)


def _memory_cost(item: Dict[str, Any]) -> int:
    return _tokens(" ".join((item["title"], item["statement"], item["rationale"]))) + 32


def _episode_cost(item: Dict[str, Any]) -> int:
    return _tokens(" ".join((item["title"], item["goal"], item["outcome_summary"]))) + 40


def compile_context(
    store: CompanyBrainStore,
    request: ContextRequest,
    *,
    include_candidates: bool = False,
) -> Dict[str, Any]:
    candidates = search_memories(
        store,
        request.task,
        request.principal,
        project_id=request.project_id,
        memory_types=request.memory_types or None,
        as_of=request.as_of,
        limit=request.limit,
        include_candidates=include_candidates,
    )
    reserve = min(800, max(200, request.token_budget // 10))
    available = request.token_budget - reserve
    selected: List[Dict[str, Any]] = []
    used = 0
    for item in candidates:
        cost = _memory_cost(item)
        if used + cost > available:
            continue
        selected.append(item)
        used += cost

    evidence = store.evidence_for_memories(
        [item["memory_id"] for item in selected], request.principal
    )
    sections: Dict[str, List[Dict[str, Any]]] = {
        "current_state": [],
        "decisions": [],
        "constraints": [],
        "open_work": [],
        "open_questions": [],
        "risks": [],
        "outcomes": [],
        "procedures": [],
    }
    source_index: Dict[str, Dict[str, Any]] = {}
    artifact_attachments: Dict[str, Dict[str, Any]] = {}
    warnings: List[str] = []

    verified_evidence: Dict[str, Dict[str, Any]] = {}
    for references in evidence.values():
        for reference in references:
            evidence_id = reference["evidence_id"]
            if evidence_id in verified_evidence:
                continue
            try:
                verified_evidence[evidence_id] = store.inspect_evidence(
                    evidence_id, request.principal, strong=True
                )
            except (KeyError, PermissionError, OSError) as exc:
                verified_evidence[evidence_id] = {
                    "availability": {"status": "unavailable", "reason": str(exc)}
                }

    usable: List[Dict[str, Any]] = []
    for item in selected:
        refs = evidence.get(item["memory_id"], [])
        available_refs = [
            reference for reference in refs
            if verified_evidence.get(reference["evidence_id"], {}).get(
                "availability", {}
            ).get("status") == "available"
        ]
        if not available_refs:
            warnings.append(
                f"{item['memory_id']} was omitted because none of its authorized evidence is currently available and unchanged."
            )
            continue
        usable.append(item)
        card = {
            "memory_id": item["memory_id"],
            "type": item["memory_type"],
            "title": item["title"],
            "statement": item["statement"],
            "rationale": item["rationale"],
            "project_id": item["project_id"],
            "lifecycle": item["lifecycle"],
            "confidence": item["confidence"],
            "valid_from": item["valid_from"],
            "valid_to": item["valid_to"],
            "score": item["score"],
            "why_matched": item["why_matched"],
            "evidence_refs": [reference["evidence_id"] for reference in available_refs],
        }
        section = SECTION_BY_TYPE.get(item["memory_type"], "current_state")
        sections[section].append(card)
        if item["lifecycle"] in {"candidate", "reviewed", "stale"}:
            warnings.append(
                f"{item['memory_id']} is {item['lifecycle']} and must not be treated as verified current truth."
            )
        for reference in refs:
            evidence_id = reference["evidence_id"]
            status = verified_evidence.get(evidence_id, {}).get("availability", {})
            source = dict(reference)
            source["availability"] = status
            source_index[evidence_id] = source
            if status.get("status") != "available":
                warnings.append(
                    f"Evidence {evidence_id} is {status.get('status', 'unavailable')}: {status.get('reason', '')}"
                )
                continue
            attachment_key = evidence_id + "\x1f" + reference.get("segment_id", "")
            artifact_attachments[attachment_key] = {
                "evidence_id": evidence_id,
                "segment_id": reference.get("segment_id", ""),
                "artifact_type": reference.get("artifact_type", "plain_text"),
                "mime_type": reference.get("mime_type", "application/octet-stream"),
                "storage_mode": reference.get("storage_mode", "managed"),
                "source_locator": reference.get("source_locator", ""),
                "native_locator": reference.get("native_locator") or reference.get("locator", ""),
                "availability": status,
                "delivery": "reference",
            }

    selected = usable
    used = sum(_memory_cost(item) for item in selected)

    # Company Brain may have fresh reference evidence that has not yet become
    # a reviewed atomic memory. Surface bounded, cited source excerpts without
    # copying the source bytes or weakening memory lifecycle rules.
    direct_evidence: List[Dict[str, Any]] = []
    for evidence_item in search_evidence(
        store, request.task, request.principal, limit=min(8, request.limit),
    ):
        if evidence_item["evidence_id"] in source_index:
            continue
        cost = _tokens(evidence_item.get("quote", "")) + 40
        if used + cost > available:
            continue
        direct_evidence.append(evidence_item)
        used += cost
        source_index[evidence_item["evidence_id"]] = {
            "evidence_id": evidence_item["evidence_id"],
            "source_locator": evidence_item["source_locator"],
            "source_type": evidence_item["source_type"],
            "artifact_type": evidence_item["artifact_type"],
            "mime_type": evidence_item["mime_type"],
            "storage_mode": evidence_item["storage_mode"],
            "native_locator": evidence_item["native_locator"],
            "quote": evidence_item["quote"],
            "availability": evidence_item["availability"],
            "delivery": "reference",
        }
        artifact_attachments[evidence_item["evidence_id"]] = {
            "evidence_id": evidence_item["evidence_id"],
            "artifact_type": evidence_item["artifact_type"],
            "mime_type": evidence_item["mime_type"],
            "storage_mode": evidence_item["storage_mode"],
            "source_locator": evidence_item["source_locator"],
            "native_locator": evidence_item["native_locator"],
            "availability": evidence_item["availability"],
            "delivery": "reference",
        }

    # Episodes are observed work narratives, not verified organizational truth.
    # They complement atomic memory while retaining evidence IDs and ACLs.
    episode_context: List[Dict[str, Any]] = []
    episode_candidates = store.search_episodes(
        request.task, request.principal, project_id=request.project_id, limit=8,
    )
    for episode in episode_candidates:
        cost = _episode_cost(episode)
        if used + cost > available:
            continue
        evidence_refs: List[str] = []
        evidence_available = True
        for evidence_id in episode["evidence_ids"]:
            try:
                inspection = store.inspect_evidence(
                    evidence_id, request.principal, strong=True,
                )
                if inspection["availability"]["status"] != "available":
                    evidence_available = False
                    break
                evidence_refs.append(evidence_id)
            except (KeyError, PermissionError, OSError):
                evidence_available = False
                break
        if not evidence_available:
            warnings.append(
                f"Episode {episode['episode_id']} was omitted because its evidence is unavailable or changed."
            )
            continue
        episode_context.append({
            "episode_id": episode["episode_id"],
            "title": episode["title"],
            "goal": episode["goal"],
            "outcome_summary": episode["outcome_summary"],
            "project_id": episode["project_id"],
            "status": episode["status"],
            "started_at": episode["started_at"],
            "ended_at": episode["ended_at"],
            "confidence": episode["confidence"],
            "score": episode["score"],
            "boundary_signals": episode["boundary_signals"],
            "evidence_refs": evidence_refs,
            "authority": "observed_activity",
        })
        used += cost

    conflicts = store.related_conflicts(
        [item["memory_id"] for item in selected], request.principal
    )
    if conflicts:
        warnings.append(f"{len(conflicts)} explicit contradiction relation(s) affect this context.")

    brief_parts = [item["statement"] for item in selected[:3]]
    if not brief_parts:
        brief_parts = [
            item["outcome_summary"] or item["goal"] for item in episode_context[:2]
        ]
    if not brief_parts:
        brief_parts = [item["quote"] for item in direct_evidence[:2] if item.get("quote")]
    if not brief_parts:
        brief = "No authorized, current memory or source evidence supports this task."
    else:
        brief = " ".join(brief_parts)

    identity = "\x1f".join((
        request.principal.tenant_id,
        request.principal.principal_id,
        request.task,
        request.project_id,
        request.as_of,
        ",".join(item["memory_id"] for item in selected),
        ",".join(item["episode_id"] for item in episode_context),
        ",".join(item["evidence_id"] for item in direct_evidence),
    ))
    context_id = "ctx_" + hashlib.sha256(identity.encode("utf-8")).hexdigest()[:24]

    return {
        "context_pack_id": context_id,
        "created_at": now_iso(),
        "task": request.task,
        "scope": {
            "tenant_id": request.principal.tenant_id,
            "principal_id": request.principal.principal_id,
            "project_id": request.project_id,
            "as_of": request.as_of or "now",
        },
        "executive_brief": brief,
        **sections,
        "conflicts": conflicts,
        "warnings": warnings,
        "source_index": list(source_index.values()),
        "artifact_attachments": list(artifact_attachments.values()),
        "direct_evidence": direct_evidence,
        "episode_context": episode_context,
        "token_budget": request.token_budget,
        "estimated_tokens": used + _tokens(brief),
        "selected_items": len(selected),
        "selected_evidence": len(direct_evidence),
        "omitted_relevant_items": max(0, len(candidates) - len(selected)),
        "retrieval_build": "company-brain-v3-memory-evidence-episode-hybrid",
    }
