"""Idempotent migration from legacy cartridge files into canonical brain data."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from llm_kosh.core.utils import parse_frontmatter

from .models import EvidenceInput, EvidenceReference, MemoryInput
from .artifacts import infer_artifact_type
from .store import CompanyBrainStore


CLASSIFICATION_MAP = {
    "public": "public",
    "shareable": "internal",
    "internal": "internal",
    "confidential": "confidential",
    "private": "restricted",
    "blocked": "restricted",
    "quarantine": "restricted",
}
TYPE_MAP = {
    "decision": "decision",
    "preference": "preference",
    "project": "fact",
    "gap": "question",
    "correction": "correction",
    "note": "fact",
    "suggestion": "hypothesis",
}


def _first_paragraph(body: str) -> str:
    useful = []
    for line in body.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            if useful:
                break
            continue
        useful.append(line)
    return " ".join(useful).strip()


def _task_from_body(body: str) -> Optional[Tuple[str, str, str]]:
    start = body.find("{")
    if start < 0:
        return None
    try:
        value, _ = json.JSONDecoder().raw_decode(body[start:])
    except (json.JSONDecodeError, TypeError):
        return None
    if not isinstance(value, dict):
        return None
    title = str(value.get("subject") or "").strip()
    description = str(value.get("description") or "").strip()
    status = str(value.get("status") or "").strip().lower()
    if not title or not description:
        return None
    memory_type = "outcome" if status in {"completed", "done", "closed", "verified"} else "task"
    statement = ("Completed: " if memory_type == "outcome" else "Planned work: ") + description
    return memory_type, title, statement


def _canonical_candidate(meta: Dict[str, Any], body: str) -> Optional[Tuple[str, str, str, str]]:
    legacy_type = str(meta.get("type") or "note").lower()
    if legacy_type == "file":
        task = _task_from_body(body)
        if task:
            memory_type, title, statement = task
            return memory_type, title, statement, ""
        return None
    memory_type = TYPE_MAP.get(legacy_type)
    if not memory_type:
        return None
    title = str(meta.get("title") or "").strip()
    statement = _first_paragraph(body)
    if len(statement) < 10:
        return None
    rationale = body.strip() if memory_type == "decision" and len(body.strip()) <= 8_000 else ""
    return memory_type, title, statement[:4_000], rationale


def migrate_legacy_cartridge(
    root: Path,
    *,
    dry_run: bool = False,
    include_superseded_memories: bool = False,
    tenant_id: str = "local",
) -> Dict[str, Any]:
    root = Path(root).expanduser().resolve()
    source = root / "source"
    store = CompanyBrainStore(root)
    if not dry_run:
        store.initialize()

    report: Dict[str, Any] = {
        "dry_run": dry_run,
        "source_files": 0,
        "evidence_created": 0,
        "reference_evidence": 0,
        "copied_source_bytes": 0,
        "memory_candidates_created": 0,
        "superseded_evidence_only": 0,
        "raw_evidence_only": 0,
        "rejected_candidates": 0,
        "by_memory_type": {},
        "warnings": [],
    }

    for path in sorted(source.rglob("*.md")) if source.exists() else []:
        report["source_files"] += 1
        # read_text performs universal-newline normalization on Windows; the
        # legacy frontmatter parser expects LF delimiters.
        text = path.read_text(encoding="utf-8", errors="replace")
        meta, body = parse_frontmatter(text)
        legacy_id = str(meta.get("id") or path.relative_to(root).as_posix())
        status = str(meta.get("status") or "active").lower()
        classification = CLASSIFICATION_MAP.get(
            str(meta.get("visibility") or "private").lower(), "restricted"
        )
        candidate = _canonical_candidate(meta, body)

        if dry_run:
            evidence_id = "dry-run"
            report["evidence_created"] += 1
            report["reference_evidence"] += 1
        else:
            evidence_id = store.put_evidence(EvidenceInput(
                tenant_id=tenant_id,
                source_type="legacy_cartridge",
                source_locator=str(path.resolve()),
                source_native_id=legacy_id,
                mime_type="text/markdown",
                storage_mode="reference",
                artifact_type=infer_artifact_type(path, "text/markdown"),
                observed_at=str(meta.get("created") or ""),
                source_modified_at="",
                classification=classification,
                ingestion_run_id="legacy-company-brain-v1",
            ))
            report["evidence_created"] += 1
            report["reference_evidence"] += 1

        if status == "superseded" and not include_superseded_memories:
            report["superseded_evidence_only"] += 1
            continue
        if candidate is None:
            report["raw_evidence_only"] += 1
            continue

        memory_type, title, statement, rationale = candidate
        if not title or re.fullmatch(r"\d+|[0-9a-f-]{24,}|rollout[-_].*|agent[-_].*", title, re.I):
            report["rejected_candidates"] += 1
            continue
        report["by_memory_type"][memory_type] = report["by_memory_type"].get(memory_type, 0) + 1
        if dry_run:
            report["memory_candidates_created"] += 1
            continue
        try:
            store.add_memory(MemoryInput(
                tenant_id=tenant_id,
                memory_type=memory_type,
                title=title,
                statement=statement,
                rationale=rationale,
                project_id=str(meta.get("project") or ""),
                lifecycle="candidate",
                confidence=0.65 if memory_type in {"task", "outcome"} else 0.75,
                importance=0.6,
                valid_from=str(meta.get("created") or ""),
                observed_at=str(meta.get("created") or ""),
                classification=classification,
                evidence=[EvidenceReference(
                    evidence_id=evidence_id,
                    locator=path.relative_to(root).as_posix(),
                    support="direct",
                    quote=statement[:500],
                )],
                extractor={
                    "kind": "deterministic_legacy_migration",
                    "version": "company-brain-v1",
                },
                source_native_id="legacy:" + legacy_id,
            ))
            report["memory_candidates_created"] += 1
        except ValueError as exc:
            report["rejected_candidates"] += 1
            if len(report["warnings"]) < 50:
                report["warnings"].append({"source": legacy_id, "reason": str(exc)})

    if not dry_run:
        report["health"] = store.health()
    return report
