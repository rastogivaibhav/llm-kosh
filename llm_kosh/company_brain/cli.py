"""CLI parser and dispatch for company-brain capabilities."""

from __future__ import annotations

import json
import mimetypes
from pathlib import Path
from typing import Any

from llm_kosh.core.memory import ensure_root

from .context import compile_context
from .migration import migrate_legacy_cartridge
from .models import (
    CLASSIFICATIONS,
    ARTIFACT_TYPES,
    LIFECYCLES,
    MEMORY_TYPES,
    ContextRequest,
    EvidenceInput,
    EvidenceReference,
    MemoryInput,
    Principal,
)
from .artifacts import infer_artifact_type
from .retrieval import search_memories
from .store import CompanyBrainStore
from .understanding import understand_evidence


def add_brain_parser(subparsers: Any) -> None:
    parser = subparsers.add_parser(
        "brain", help="Canonical evidence, governed memory, and structured context"
    )
    actions = parser.add_subparsers(dest="brain_action", required=True)
    actions.add_parser("init", help="Initialise canonical company-brain storage")

    register = actions.add_parser("register", help="Register an existing file without copying it")
    register.add_argument("path")
    register.add_argument("--artifact-type", choices=sorted(ARTIFACT_TYPES), default="")
    register.add_argument("--source-native-id", default="")
    register.add_argument("--classification", choices=CLASSIFICATIONS, default="restricted")
    register.add_argument("--tenant", default="local")

    inspect = actions.add_parser("inspect", help="Inspect an authorized artifact and native region")
    inspect.add_argument("evidence_id")
    _principal_arguments(inspect)
    inspect.add_argument("--locator", default="{}", help="Native locator JSON")
    inspect.add_argument("--max-text", type=int, default=16_000)
    inspect.add_argument("--metadata-only", action="store_true")

    segment = actions.add_parser("segment", help="Inspect and persist bounded derived segments")
    segment.add_argument("evidence_id")
    _principal_arguments(segment)
    segment.add_argument("--locator", default="{}", help="Native locator JSON")
    segment.add_argument("--max-text", type=int, default=16_000)

    snapshot = actions.add_parser("snapshot", help="Explicitly copy evidence into immutable storage")
    snapshot.add_argument("evidence_id")
    _principal_arguments(snapshot)

    migrate = actions.add_parser("migrate", help="Import the legacy cartridge idempotently")
    migrate.add_argument("--dry-run", action="store_true")
    migrate.add_argument("--include-superseded-memories", action="store_true")
    migrate.add_argument("--tenant", default="local")

    health = actions.add_parser("health", help="Validate canonical brain storage")
    health.add_argument("--json", action="store_true", default=True)
    actions.add_parser("evaluate", help="Run storage, citation, and integrity acceptance checks")

    search = actions.add_parser("search", help="Permission-first hybrid memory search")
    search.add_argument("query")
    _principal_arguments(search)
    search.add_argument("--project", default="")
    search.add_argument("--type", action="append", choices=sorted(MEMORY_TYPES), default=[])
    search.add_argument("--as-of", default="")
    search.add_argument("--limit", type=int, default=10)
    search.add_argument("--include-candidates", action="store_true")
    search.add_argument("--no-stale", action="store_true")
    search.add_argument("--json", action="store_true")

    context = actions.add_parser("context", help="Compile structured, cited context")
    context.add_argument("task")
    _principal_arguments(context)
    context.add_argument("--project", default="")
    context.add_argument("--type", action="append", choices=sorted(MEMORY_TYPES), default=[])
    context.add_argument("--as-of", default="")
    context.add_argument("--tokens", type=int, default=8_000)
    context.add_argument("--limit", type=int, default=40)
    context.add_argument("--include-candidates", action="store_true")
    context.add_argument("--out", default="")

    remember = actions.add_parser("remember", help="Create evidence-backed candidate memory")
    remember.add_argument("--type", required=True, choices=sorted(MEMORY_TYPES))
    remember.add_argument("--title", required=True)
    remember.add_argument("--statement", required=True)
    remember.add_argument("--rationale", default="")
    remember.add_argument("--project", default="")
    remember.add_argument("--classification", choices=CLASSIFICATIONS, default="restricted")
    remember.add_argument("--evidence-file", default="")
    remember.add_argument("--evidence-id", default="", help="Use already registered evidence")
    remember.add_argument("--segment-id", default="", help="Cite a persisted evidence segment")
    remember.add_argument("--evidence-locator", default="", help="Native locator or source label")
    remember.add_argument(
        "--snapshot-evidence", action="store_true",
        help="Explicitly copy the evidence file instead of registering a reference",
    )
    remember.add_argument("--source-native-id", default="")
    _principal_arguments(remember)

    review = actions.add_parser("review", help="Transition a memory through its lifecycle")
    review.add_argument("memory_id")
    review.add_argument("--to", required=True, choices=sorted(LIFECYCLES))
    review.add_argument("--reason", default="")
    _principal_arguments(review)

    understand = actions.add_parser(
        "understand", help="Build sessions, episodes, and cited candidates from JSONL evidence"
    )
    understand.add_argument("evidence_id")
    _principal_arguments(understand)
    understand.add_argument("--dry-run", action="store_true")
    understand.add_argument("--source-type", default="session_jsonl")
    understand.add_argument("--session-id", default="")
    understand.add_argument("--project", default="")
    understand.add_argument("--max-events", type=int, default=100_000)

    sessions = actions.add_parser("sessions", help="List authorized normalized sessions")
    _principal_arguments(sessions)
    sessions.add_argument("--project", default="")
    sessions.add_argument("--limit", type=int, default=100)

    episodes = actions.add_parser("episodes", help="List or search authorized work episodes")
    _principal_arguments(episodes)
    episodes.add_argument("--query", default="")
    episodes.add_argument("--project", default="")
    episodes.add_argument("--limit", type=int, default=100)

    episode = actions.add_parser("episode", help="Get an episode with events and candidate links")
    episode.add_argument("episode_id")
    _principal_arguments(episode)


def _principal_arguments(parser: Any) -> None:
    parser.add_argument("--principal", default="local-user")
    parser.add_argument("--tenant", default="local")
    parser.add_argument("--group", action="append", default=[])
    parser.add_argument("--principal-project", action="append", default=[])
    parser.add_argument("--clearance", choices=CLASSIFICATIONS, default="restricted")


def _principal(args: Any) -> Principal:
    return Principal(
        principal_id=args.principal,
        tenant_id=args.tenant,
        groups=list(args.group),
        projects=list(args.principal_project),
        clearance=args.clearance,
    )


def run_brain_command(root: Path, args: Any) -> None:
    ensure_root(root)
    store = CompanyBrainStore(root)
    action = args.brain_action
    if action == "init":
        store.initialize()
        print(json.dumps(store.health(), indent=2))
    elif action == "migrate":
        print(json.dumps(migrate_legacy_cartridge(
            root,
            dry_run=args.dry_run,
            include_superseded_memories=args.include_superseded_memories,
            tenant_id=args.tenant,
        ), indent=2))
    elif action == "health":
        print(json.dumps(store.health(), indent=2))
    elif action == "evaluate":
        print(json.dumps(store.evaluate(), indent=2))
    elif action == "register":
        evidence_path = Path(args.path).expanduser().resolve(strict=True)
        mime_type = mimetypes.guess_type(evidence_path.name)[0] or "application/octet-stream"
        evidence_id = store.put_evidence(EvidenceInput(
            tenant_id=args.tenant,
            source_type="local_file",
            source_locator=str(evidence_path),
            source_native_id=args.source_native_id or str(evidence_path),
            storage_mode="reference",
            artifact_type=args.artifact_type or infer_artifact_type(evidence_path, mime_type),
            mime_type=mime_type,
            classification=args.classification,
        ))
        print(json.dumps({
            "evidence_id": evidence_id, "storage_mode": "reference",
            "copied_source_bytes": 0,
        }, indent=2))
    elif action == "inspect":
        locator = json.loads(args.locator)
        print(json.dumps(store.inspect_evidence(
            args.evidence_id, _principal(args), strong=True,
            native_locator=locator, include_preview=not args.metadata_only,
            max_text=args.max_text,
        ), indent=2))
    elif action == "segment":
        locator = json.loads(args.locator)
        print(json.dumps(store.inspect_and_segment(
            args.evidence_id, _principal(args),
            native_locator=locator, max_text=args.max_text,
        ), indent=2))
    elif action == "snapshot":
        snapshot_id = store.materialize_snapshot(args.evidence_id, _principal(args))
        print(json.dumps({
            "source_evidence_id": args.evidence_id,
            "snapshot_evidence_id": snapshot_id,
            "storage_mode": "snapshot",
        }, indent=2))
    elif action == "search":
        results = search_memories(
            store,
            args.query,
            _principal(args),
            project_id=args.project,
            memory_types=args.type or None,
            as_of=args.as_of,
            limit=args.limit,
            include_candidates=args.include_candidates,
            include_stale=not args.no_stale,
        )
        if args.json:
            print(json.dumps(results, indent=2))
        elif not results:
            print("No authorized memory matched.")
        else:
            for result in results:
                print(
                    f"[{result['memory_type'].upper()}:{result['lifecycle']}] "
                    f"{result['title']}  score={result['score']:.3f}\n"
                    f"{result['statement']}\n{result['memory_id']}\n"
                )
    elif action == "context":
        pack = compile_context(
            store,
            ContextRequest(
                task=args.task,
                principal=_principal(args),
                project_id=args.project,
                memory_types=args.type,
                as_of=args.as_of,
                token_budget=args.tokens,
                limit=args.limit,
            ),
            include_candidates=args.include_candidates,
        )
        rendered = json.dumps(pack, indent=2)
        if args.out:
            destination = Path(args.out).expanduser().resolve()
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text(rendered + "\n", encoding="utf-8")
            print(f"Wrote structured context pack: {destination}")
        else:
            print(rendered)
    elif action == "remember":
        if args.evidence_id and args.evidence_file:
            raise SystemExit("Use either --evidence-id or --evidence-file, not both")
        if args.evidence_id:
            store.inspect_evidence(args.evidence_id, _principal(args), strong=True)
            evidence_id = args.evidence_id
            locator = args.evidence_locator
            native_id = args.source_native_id or args.title
        elif args.evidence_file:
            evidence_path = Path(args.evidence_file).expanduser().resolve()
            locator = str(evidence_path)
            native_id = args.source_native_id or str(evidence_path)
            mime_type = mimetypes.guess_type(evidence_path.name)[0] or "application/octet-stream"
            storage_mode = "snapshot" if args.snapshot_evidence else "reference"
            content = evidence_path.read_bytes() if args.snapshot_evidence else None
            artifact_type = infer_artifact_type(evidence_path, mime_type)
        else:
            content = (args.statement + "\n\n" + args.rationale).encode("utf-8")
            locator = "manual://cli"
            native_id = args.source_native_id or args.title
            mime_type = "text/plain"
            storage_mode = "managed"
            artifact_type = "plain_text"
        if not args.evidence_id:
            evidence_id = store.put_evidence(EvidenceInput(
                tenant_id=args.tenant,
                source_type="manual_cli",
                source_locator=locator,
                source_native_id=native_id,
                content=content,
                mime_type=mime_type,
                storage_mode=storage_mode,
                artifact_type=artifact_type,
                classification=args.classification,
            ))
        memory_id = store.add_memory(MemoryInput(
            tenant_id=args.tenant,
            memory_type=args.type,
            title=args.title,
            statement=args.statement,
            rationale=args.rationale,
            project_id=args.project,
            lifecycle="candidate",
            confidence=0.6,
            importance=0.5,
            classification=args.classification,
            evidence=[EvidenceReference(
                evidence_id=evidence_id,
                segment_id=args.segment_id,
                locator=locator,
            )],
            extractor={"kind": "manual_cli", "version": "company-brain-v1"},
            source_native_id="manual:" + native_id,
        ))
        print(json.dumps({"memory_id": memory_id, "evidence_id": evidence_id, "lifecycle": "candidate"}, indent=2))
    elif action == "review":
        print(json.dumps(store.transition_memory(
            args.memory_id, args.to, _principal(args), reason=args.reason
        ), indent=2))
    elif action == "understand":
        print(json.dumps(understand_evidence(
            store, args.evidence_id, _principal(args), dry_run=args.dry_run,
            source_type=args.source_type, session_native_id=args.session_id,
            project_id=args.project, max_events=args.max_events,
        ), indent=2))
    elif action == "sessions":
        print(json.dumps(store.list_sessions(
            _principal(args), project_id=args.project, limit=args.limit,
        ), indent=2))
    elif action == "episodes":
        if args.query:
            result = store.search_episodes(
                args.query, _principal(args), project_id=args.project, limit=args.limit,
            )
        else:
            result = store.list_episodes(
                _principal(args), project_id=args.project, limit=args.limit,
            )
        print(json.dumps(result, indent=2))
    elif action == "episode":
        print(json.dumps(store.get_episode(args.episode_id, _principal(args)), indent=2))
