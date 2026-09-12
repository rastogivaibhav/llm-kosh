"""Standalone CLI for the Trusted Memory Runtime.

This module deliberately keeps product-facing memory operations on top of the
runtime facade/reviewer instead of duplicating admission, retrieval, or review
logic in argparse handlers.
"""

from __future__ import annotations

import argparse
import json
import mimetypes
import os
from pathlib import Path
from typing import Any, Sequence

from llm_kosh.company_brain.artifacts import infer_artifact_type
from llm_kosh.company_brain.models import (
    CLASSIFICATIONS,
    MEMORY_TYPES,
    AccessPolicy,
    EvidenceInput,
    Principal,
)
from llm_kosh.company_brain.store import CompanyBrainStore
from llm_kosh.core.constants import DEFAULT_ROOT_NAME
from llm_kosh.core.memory import ensure_root

from .models import MemoryProposal, MemorySource, RetrievalMode
from .review import TrustedMemoryReviewer
from .service import TrustedMemoryRuntime


def _default_root() -> str:
    try:
        from llm_kosh.global_config import get_default_cartridge_root

        return str(get_default_cartridge_root())
    except Exception:
        return str(Path.cwd() / DEFAULT_ROOT_NAME)


def _principal_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--principal", default="local-user")
    parser.add_argument("--tenant", default="local")
    parser.add_argument("--group", action="append", default=[])
    parser.add_argument("--principal-project", action="append", default=[])
    parser.add_argument("--clearance", choices=CLASSIFICATIONS, default="restricted")


def _principal(args: argparse.Namespace) -> Principal:
    projects = list(args.principal_project)
    project = getattr(args, "project", "")
    if project and project not in projects:
        projects.append(project)
    return Principal(
        principal_id=args.principal,
        tenant_id=args.tenant,
        groups=list(args.group),
        projects=projects,
        clearance=args.clearance,
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="llm-kosh-memory",
        description="Trusted local memory: propose, recall, inspect, and review evidence-backed memory.",
    )
    parser.add_argument("--root", default=_default_root(), help="Cartridge root folder")
    actions = parser.add_subparsers(dest="action", required=True)

    propose = actions.add_parser("propose", help="Propose evidence-backed memory for admission")
    propose.add_argument("--type", required=True, choices=sorted(MEMORY_TYPES))
    propose.add_argument("--title", required=True)
    propose.add_argument("--statement", required=True)
    propose.add_argument(
        "--source-type",
        default=MemorySource.USER_DIRECT.value,
        choices=[item.value for item in MemorySource],
        help="Origin of the claim; defaults to direct CLI user input",
    )
    propose.add_argument("--project", default="")
    propose.add_argument("--classification", choices=CLASSIFICATIONS, default="restricted")
    propose.add_argument("--evidence-id", default="")
    propose.add_argument("--evidence-file", default="")
    propose.add_argument(
        "--snapshot-evidence",
        action="store_true",
        help="Copy evidence file into immutable local blob storage instead of referencing it",
    )
    propose.add_argument("--source-native-id", default="")
    propose.add_argument("--observed-at", default="")
    propose.add_argument("--confidence", type=float, default=None)
    propose.add_argument("--subject", default="")
    propose.add_argument("--predicate", default="")
    propose.add_argument("--object", dest="object_value", default="")
    propose.add_argument("--supersedes", action="append", default=[])
    _principal_arguments(propose)

    recall = actions.add_parser("recall", help="Recall governed memory")
    recall.add_argument("query", nargs="?", default="")
    recall.add_argument("--mode", choices=[item.value for item in RetrievalMode], default="normal")
    recall.add_argument("--project", default="")
    recall.add_argument("--type", action="append", choices=sorted(MEMORY_TYPES), default=[])
    recall.add_argument("--as-of", default="")
    recall.add_argument("--limit", type=int, default=10)
    recall.add_argument("--json", action="store_true")
    _principal_arguments(recall)

    inbox = actions.add_parser("inbox", help="List candidate and quarantined governed memory")
    inbox.add_argument("query", nargs="?", default="")
    inbox.add_argument("--project", default="")
    inbox.add_argument("--limit", type=int, default=50)
    inbox.add_argument("--json", action="store_true")
    _principal_arguments(inbox)

    conflicts = actions.add_parser("conflicts", help="List unresolved governed-memory conflicts")
    conflicts.add_argument("query", nargs="?", default="")
    conflicts.add_argument("--project", default="")
    conflicts.add_argument("--limit", type=int, default=100)
    conflicts.add_argument("--json", action="store_true")
    _principal_arguments(conflicts)

    explain = actions.add_parser("explain", help="Show evidence and admission history for a memory")
    explain.add_argument("memory_id")
    explain.add_argument("--json", action="store_true")
    _principal_arguments(explain)

    review = actions.add_parser("review", help="Explicitly review or supersede governed memory")
    review.add_argument("memory_id")
    review.add_argument(
        "--action",
        required=True,
        choices=["approve", "quarantine", "reject", "supersede"],
    )
    review.add_argument("--reason", required=True)
    review.add_argument("--supersede-id", action="append", default=[])
    review.add_argument("--json", action="store_true")
    _principal_arguments(review)

    return parser


def _create_or_validate_evidence(
    root: Path,
    args: argparse.Namespace,
    principal: Principal,
) -> str:
    if args.evidence_id and args.evidence_file:
        raise SystemExit("Use either --evidence-id or --evidence-file, not both")

    store = CompanyBrainStore(root)
    if args.evidence_id:
        store.inspect_evidence(args.evidence_id, principal, strong=True)
        return args.evidence_id

    policy = AccessPolicy(allowed_principals=[principal.principal_id])
    native_id = args.source_native_id.strip()
    if args.evidence_file:
        evidence_path = Path(args.evidence_file).expanduser().resolve(strict=True)
        mime_type = mimetypes.guess_type(evidence_path.name)[0] or "application/octet-stream"
        storage_mode = "snapshot" if args.snapshot_evidence else "reference"
        content = evidence_path.read_bytes() if args.snapshot_evidence else None
        return store.put_evidence(
            EvidenceInput(
                tenant_id=principal.tenant_id,
                source_type=args.source_type,
                source_locator=str(evidence_path),
                source_native_id=native_id or str(evidence_path),
                content=content,
                mime_type=mime_type,
                storage_mode=storage_mode,
                artifact_type=infer_artifact_type(evidence_path, mime_type),
                classification=args.classification,
                access_policy=policy,
            )
        )

    evidence_text = f"{args.title}\n\n{args.statement}\n"
    return store.put_evidence(
        EvidenceInput(
            tenant_id=principal.tenant_id,
            source_type=args.source_type,
            source_locator="manual://trusted-memory-cli",
            source_native_id=native_id or f"cli:{args.title}",
            content=evidence_text.encode("utf-8"),
            mime_type="text/plain",
            storage_mode="managed",
            artifact_type="plain_text",
            classification=args.classification,
            access_policy=policy,
        )
    )


def _render_recall(items: Sequence[dict[str, Any]]) -> None:
    if not items:
        print("No governed memory matched.")
        return
    for item in items:
        authority = item.get("authority") or "legacy/unassessed"
        decision = item.get("admission_decision") or "unassessed"
        print(
            f"[{item['memory_type'].upper()}:{item['lifecycle']}] "
            f"authority={authority} admission={decision}\n"
            f"{item['title']}\n{item['statement']}\n{item['memory_id']}\n"
        )


def _render_inbox(items: Sequence[dict[str, Any]]) -> None:
    if not items:
        print("Trusted Memory inbox is empty.")
        return
    for item in items:
        print(
            f"[{item['lifecycle'].upper()}] {item['title']}\n"
            f"decision={item.get('admission_decision') or 'unassessed'} "
            f"conflict={item.get('conflict_state') or 'none'} "
            f"authority={item.get('authority') or 'unknown'}\n"
            f"{item['statement']}\n{item['memory_id']}\n"
        )


def run_memory_command(root: Path, args: argparse.Namespace) -> None:
    ensure_root(root)
    principal = _principal(args)

    if args.action == "propose":
        evidence_id = _create_or_validate_evidence(root, args, principal)
        metadata = {}
        if args.supersedes:
            metadata["supersedes"] = list(dict.fromkeys(args.supersedes))
        proposal = MemoryProposal(
            memory_type=args.type,
            title=args.title,
            statement=args.statement,
            evidence_ids=[evidence_id],
            source_type=args.source_type,
            project_id=args.project,
            observed_at=args.observed_at,
            confidence=args.confidence,
            classification=args.classification,
            principal_id=principal.principal_id,
            source_native_id=args.source_native_id,
            subject=args.subject,
            predicate=args.predicate,
            object_value=args.object_value,
            metadata=metadata,
        )
        result = TrustedMemoryRuntime(root).propose(proposal, principal)
        print(json.dumps({**result, "evidence_id": evidence_id}, indent=2))
        return

    if args.action in {"recall", "inbox", "conflicts"}:
        mode = RetrievalMode.CANDIDATE if args.action in {"inbox", "conflicts"} else args.mode
        items = TrustedMemoryRuntime(root).recall(
            args.query,
            principal,
            project_id=args.project,
            memory_types=getattr(args, "type", None) or None,
            as_of=getattr(args, "as_of", ""),
            mode=mode,
            limit=args.limit,
        )
        if args.action == "conflicts":
            items = [item for item in items if (item.get("conflict_state") or "none") != "none"]
        if args.json:
            print(json.dumps(items, indent=2))
        elif args.action == "recall":
            _render_recall(items)
        else:
            _render_inbox(items)
        return

    if args.action == "explain":
        result = TrustedMemoryRuntime(root).explain(args.memory_id, principal)
        if args.json:
            print(json.dumps(result, indent=2))
        else:
            memory = result["memory"]
            runtime = result.get("runtime") or {}
            print(f"{memory['title']}\n{memory['statement']}\n")
            print(f"Memory: {memory['memory_id']}  lifecycle={memory['lifecycle']}")
            print(
                f"Authority: {runtime.get('authority') or 'unassessed'}  "
                f"admission={runtime.get('admission_decision') or 'unassessed'}"
            )
            print(f"Evidence: {len(memory.get('evidence') or [])}")
            print(f"Admission assessments: {len(result.get('admission_history') or [])}")
        return

    if args.action == "review":
        result = TrustedMemoryReviewer(root).review(
            args.memory_id,
            principal,
            action=args.action,
            reason=args.reason,
            supersede_ids=args.supersede_id,
        )
        print(json.dumps(result, indent=2))
        return

    raise SystemExit(f"Unsupported memory action: {args.action}")


def main(argv: Sequence[str] | None = None) -> None:
    args = _parser().parse_args(argv)
    root = Path(args.root).expanduser().resolve()
    run_memory_command(root, args)


if __name__ == "__main__":
    main()
