"""Durable canonical store for evidence and atomic company memory."""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import tempfile
import uuid
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence

from llm_kosh.core.utils import now_iso

from .models import (
    CLASSIFICATION_RANK,
    AccessPolicy,
    EvidenceInput,
    EvidenceSegmentInput,
    EpisodeInput,
    MemoryInput,
    NormalizedEventInput,
    Principal,
    SessionInput,
)
from .artifacts import (
    ReferenceChangedError,
    ReferenceError,
    fingerprint_file,
    infer_artifact_type,
    inspect_artifact as inspect_artifact_path,
    path_from_locator,
    read_registered_bytes,
    verify_reference,
)


SCHEMA_VERSION = 3
ACTIVE_LIFECYCLES = ("reviewed", "verified", "active", "stale")
CURRENT_LIFECYCLES = ("reviewed", "verified", "active")
TRANSITIONS = {
    "candidate": {"reviewed", "verified", "rejected", "quarantined"},
    "reviewed": {"verified", "rejected", "quarantined"},
    "verified": {"active", "stale", "superseded", "retracted"},
    "active": {"stale", "superseded", "retracted"},
    "stale": {"active", "superseded", "retracted"},
    "quarantined": {"candidate", "rejected"},
    "rejected": set(),
    "superseded": set(),
    "retracted": set(),
}


def _json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def _json_load(value: str, default: Any) -> Any:
    if not value:
        return default
    try:
        return json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return default


class CompanyBrainStore:
    """Local canonical brain store.

    The SQLite database is canonical metadata. Local evidence is reference-first;
    explicit snapshots and managed content use immutable content-addressed blobs.
    Search/vector/graph data remains a disposable derived projection.
    """

    def __init__(self, root: Path):
        self.root = Path(root).expanduser().resolve()
        self.brain_dir = self.root / "brain"
        self.db_path = self.brain_dir / "company_brain.sqlite"
        self.blob_dir = self.root / "evidence" / "blobs"

    def initialize(self) -> None:
        self.brain_dir.mkdir(parents=True, exist_ok=True)
        with self.connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS schema_meta (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS evidence (
                    evidence_id TEXT PRIMARY KEY,
                    tenant_id TEXT NOT NULL,
                    source_type TEXT NOT NULL,
                    source_locator TEXT NOT NULL,
                    source_native_id TEXT NOT NULL,
                    content_hash TEXT NOT NULL,
                    mime_type TEXT NOT NULL,
                    byte_length INTEGER NOT NULL,
                    observed_at TEXT NOT NULL,
                    source_modified_at TEXT NOT NULL,
                    classification TEXT NOT NULL,
                    access_policy_json TEXT NOT NULL,
                    retention_policy_id TEXT NOT NULL,
                    ingestion_run_id TEXT NOT NULL,
                    supersedes_evidence_id TEXT NOT NULL,
                    blob_path TEXT NOT NULL,
                    storage_mode TEXT NOT NULL DEFAULT 'snapshot',
                    artifact_type TEXT NOT NULL DEFAULT 'plain_text',
                    availability_status TEXT NOT NULL DEFAULT 'available',
                    source_identity_json TEXT NOT NULL DEFAULT '{}',
                    parser_json TEXT NOT NULL DEFAULT '{}',
                    last_verified_at TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    UNIQUE(tenant_id, source_type, source_native_id, content_hash)
                );
                CREATE INDEX IF NOT EXISTS idx_evidence_source
                    ON evidence(tenant_id, source_type, source_native_id);
                CREATE INDEX IF NOT EXISTS idx_evidence_hash ON evidence(content_hash);

                CREATE TABLE IF NOT EXISTS episodes (
                    episode_id TEXT PRIMARY KEY,
                    tenant_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    goal TEXT NOT NULL,
                    project_id TEXT NOT NULL,
                    participants_json TEXT NOT NULL,
                    started_at TEXT NOT NULL,
                    ended_at TEXT NOT NULL,
                    status TEXT NOT NULL,
                    outcome_summary TEXT NOT NULL,
                    session_ids_json TEXT NOT NULL,
                    evidence_ids_json TEXT NOT NULL,
                    confidence REAL NOT NULL,
                    classification TEXT NOT NULL,
                    access_policy_json TEXT NOT NULL,
                    phase_summary_json TEXT NOT NULL DEFAULT '{}',
                    boundary_signals_json TEXT NOT NULL DEFAULT '[]',
                    extraction_run_id TEXT NOT NULL DEFAULT '',
                    source_native_id TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id TEXT PRIMARY KEY,
                    tenant_id TEXT NOT NULL,
                    source_type TEXT NOT NULL,
                    source_native_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    project_id TEXT NOT NULL,
                    participants_json TEXT NOT NULL,
                    started_at TEXT NOT NULL,
                    ended_at TEXT NOT NULL,
                    status TEXT NOT NULL,
                    evidence_ids_json TEXT NOT NULL,
                    event_count INTEGER NOT NULL,
                    classification TEXT NOT NULL,
                    access_policy_json TEXT NOT NULL,
                    metadata_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE(tenant_id,source_type,source_native_id)
                );
                CREATE INDEX IF NOT EXISTS idx_sessions_scope
                    ON sessions(tenant_id,project_id,started_at);

                CREATE TABLE IF NOT EXISTS normalized_events (
                    event_id TEXT PRIMARY KEY,
                    tenant_id TEXT NOT NULL,
                    source_type TEXT NOT NULL,
                    source_native_id TEXT NOT NULL,
                    session_id TEXT NOT NULL REFERENCES sessions(session_id) ON DELETE CASCADE,
                    evidence_id TEXT NOT NULL REFERENCES evidence(evidence_id) ON DELETE RESTRICT,
                    segment_id TEXT NOT NULL DEFAULT '',
                    event_type TEXT NOT NULL,
                    actor_type TEXT NOT NULL,
                    actor_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    occurred_at TEXT NOT NULL,
                    native_locator_json TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    project_candidates_json TEXT NOT NULL,
                    entities_json TEXT NOT NULL,
                    classification TEXT NOT NULL,
                    access_policy_json TEXT NOT NULL,
                    ingestion_run_id TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    UNIQUE(tenant_id,source_type,source_native_id,evidence_id)
                );
                CREATE INDEX IF NOT EXISTS idx_events_session
                    ON normalized_events(session_id,occurred_at,event_id);
                CREATE INDEX IF NOT EXISTS idx_events_type
                    ON normalized_events(tenant_id,event_type,occurred_at);

                CREATE TABLE IF NOT EXISTS episode_events (
                    episode_id TEXT NOT NULL REFERENCES episodes(episode_id) ON DELETE CASCADE,
                    event_id TEXT NOT NULL REFERENCES normalized_events(event_id) ON DELETE CASCADE,
                    ordinal INTEGER NOT NULL,
                    phase TEXT NOT NULL,
                    PRIMARY KEY(episode_id,event_id)
                );

                CREATE TABLE IF NOT EXISTS extraction_runs (
                    run_id TEXT PRIMARY KEY,
                    tenant_id TEXT NOT NULL,
                    evidence_id TEXT NOT NULL,
                    pipeline_version TEXT NOT NULL,
                    status TEXT NOT NULL,
                    dry_run INTEGER NOT NULL,
                    input_hash TEXT NOT NULL,
                    metrics_json TEXT NOT NULL,
                    error TEXT NOT NULL,
                    started_at TEXT NOT NULL,
                    completed_at TEXT NOT NULL,
                    UNIQUE(tenant_id,evidence_id,pipeline_version,dry_run)
                );

                CREATE TABLE IF NOT EXISTS episode_memories (
                    episode_id TEXT NOT NULL REFERENCES episodes(episode_id) ON DELETE CASCADE,
                    memory_id TEXT NOT NULL REFERENCES memories(memory_id) ON DELETE CASCADE,
                    event_id TEXT NOT NULL REFERENCES normalized_events(event_id) ON DELETE CASCADE,
                    extraction_run_id TEXT NOT NULL,
                    PRIMARY KEY(episode_id,memory_id)
                );

                CREATE TABLE IF NOT EXISTS connector_checkpoints (
                    connector_id TEXT NOT NULL,
                    scope TEXT NOT NULL,
                    checkpoint_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY(connector_id,scope)
                );

                CREATE TABLE IF NOT EXISTS memories (
                    memory_id TEXT PRIMARY KEY,
                    tenant_id TEXT NOT NULL,
                    memory_type TEXT NOT NULL,
                    title TEXT NOT NULL,
                    statement TEXT NOT NULL,
                    rationale TEXT NOT NULL,
                    project_id TEXT NOT NULL,
                    owner_ids_json TEXT NOT NULL,
                    lifecycle TEXT NOT NULL,
                    confidence REAL NOT NULL,
                    importance REAL NOT NULL,
                    valid_from TEXT NOT NULL,
                    valid_to TEXT NOT NULL,
                    observed_at TEXT NOT NULL,
                    supersedes_json TEXT NOT NULL,
                    classification TEXT NOT NULL,
                    access_policy_json TEXT NOT NULL,
                    extractor_json TEXT NOT NULL,
                    source_native_id TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE(tenant_id, source_native_id)
                );
                CREATE INDEX IF NOT EXISTS idx_memories_scope
                    ON memories(tenant_id, project_id, lifecycle, memory_type);
                CREATE INDEX IF NOT EXISTS idx_memories_time
                    ON memories(valid_from, valid_to, observed_at);

                CREATE TABLE IF NOT EXISTS memory_evidence (
                    memory_id TEXT NOT NULL REFERENCES memories(memory_id) ON DELETE CASCADE,
                    evidence_id TEXT NOT NULL REFERENCES evidence(evidence_id) ON DELETE RESTRICT,
                    segment_id TEXT NOT NULL DEFAULT '',
                    locator TEXT NOT NULL,
                    support TEXT NOT NULL,
                    quote TEXT NOT NULL,
                    PRIMARY KEY(memory_id, evidence_id, segment_id, locator, support)
                );

                CREATE TABLE IF NOT EXISTS trusted_references (
                    evidence_id TEXT PRIMARY KEY REFERENCES evidence(evidence_id) ON DELETE CASCADE,
                    canonical_path TEXT NOT NULL,
                    source_identity_json TEXT NOT NULL,
                    registered_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS evidence_segments (
                    segment_id TEXT PRIMARY KEY,
                    evidence_id TEXT NOT NULL REFERENCES evidence(evidence_id) ON DELETE CASCADE,
                    native_locator_json TEXT NOT NULL,
                    text TEXT NOT NULL,
                    text_hash TEXT NOT NULL,
                    extractor_json TEXT NOT NULL,
                    confidence REAL NOT NULL,
                    created_at TEXT NOT NULL,
                    UNIQUE(evidence_id,native_locator_json,text_hash,extractor_json)
                );
                CREATE INDEX IF NOT EXISTS idx_segments_evidence
                    ON evidence_segments(evidence_id);

                CREATE TABLE IF NOT EXISTS entities (
                    entity_id TEXT PRIMARY KEY,
                    tenant_id TEXT NOT NULL,
                    entity_type TEXT NOT NULL,
                    canonical_name TEXT NOT NULL,
                    aliases_json TEXT NOT NULL,
                    classification TEXT NOT NULL,
                    access_policy_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE(tenant_id, entity_type, canonical_name)
                );

                CREATE TABLE IF NOT EXISTS memory_entities (
                    memory_id TEXT NOT NULL REFERENCES memories(memory_id) ON DELETE CASCADE,
                    entity_id TEXT NOT NULL REFERENCES entities(entity_id) ON DELETE CASCADE,
                    role TEXT NOT NULL,
                    PRIMARY KEY(memory_id, entity_id, role)
                );

                CREATE TABLE IF NOT EXISTS relations (
                    relation_id TEXT PRIMARY KEY,
                    tenant_id TEXT NOT NULL,
                    source_id TEXT NOT NULL,
                    target_id TEXT NOT NULL,
                    relation_type TEXT NOT NULL,
                    confidence REAL NOT NULL,
                    valid_from TEXT NOT NULL,
                    valid_to TEXT NOT NULL,
                    evidence_json TEXT NOT NULL,
                    classification TEXT NOT NULL,
                    access_policy_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    UNIQUE(tenant_id, source_id, target_id, relation_type, valid_from)
                );
                CREATE INDEX IF NOT EXISTS idx_relations_source ON relations(tenant_id, source_id);
                CREATE INDEX IF NOT EXISTS idx_relations_target ON relations(tenant_id, target_id);

                CREATE TABLE IF NOT EXISTS lifecycle_events (
                    event_id TEXT PRIMARY KEY,
                    tenant_id TEXT NOT NULL,
                    memory_id TEXT NOT NULL,
                    from_lifecycle TEXT NOT NULL,
                    to_lifecycle TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    actor TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE VIRTUAL TABLE IF NOT EXISTS memory_fts USING fts5(
                    memory_id UNINDEXED,
                    title,
                    statement,
                    rationale,
                    project_id,
                    memory_type,
                    tokenize='unicode61'
                );
                """
            )
            # Additive v1 -> v2 migration. SQLite preserves existing evidence
            # as snapshot-backed records; conversion to references is explicit.
            evidence_columns = {
                row[1] for row in conn.execute("PRAGMA table_info(evidence)")
            }
            for name, definition in {
                "storage_mode": "TEXT NOT NULL DEFAULT 'snapshot'",
                "artifact_type": "TEXT NOT NULL DEFAULT 'plain_text'",
                "availability_status": "TEXT NOT NULL DEFAULT 'available'",
                "source_identity_json": "TEXT NOT NULL DEFAULT '{}'",
                "parser_json": "TEXT NOT NULL DEFAULT '{}'",
                "last_verified_at": "TEXT NOT NULL DEFAULT ''",
            }.items():
                if name not in evidence_columns:
                    conn.execute(f"ALTER TABLE evidence ADD COLUMN {name} {definition}")
            memory_evidence_columns = {
                row[1] for row in conn.execute("PRAGMA table_info(memory_evidence)")
            }
            if "segment_id" not in memory_evidence_columns:
                conn.execute(
                    "ALTER TABLE memory_evidence ADD COLUMN segment_id TEXT NOT NULL DEFAULT ''"
                )
            pk_columns = [
                row[1] for row in sorted(
                    conn.execute("PRAGMA table_info(memory_evidence)"),
                    key=lambda row: row[5] or 999,
                ) if row[5]
            ]
            if "segment_id" not in pk_columns:
                conn.executescript(
                    """
                    CREATE TABLE memory_evidence_v2 (
                        memory_id TEXT NOT NULL REFERENCES memories(memory_id) ON DELETE CASCADE,
                        evidence_id TEXT NOT NULL REFERENCES evidence(evidence_id) ON DELETE RESTRICT,
                        segment_id TEXT NOT NULL DEFAULT '',
                        locator TEXT NOT NULL,
                        support TEXT NOT NULL,
                        quote TEXT NOT NULL,
                        PRIMARY KEY(memory_id,evidence_id,segment_id,locator,support)
                    );
                    INSERT INTO memory_evidence_v2(
                        memory_id,evidence_id,segment_id,locator,support,quote
                    ) SELECT memory_id,evidence_id,segment_id,locator,support,quote
                      FROM memory_evidence;
                    DROP TABLE memory_evidence;
                    ALTER TABLE memory_evidence_v2 RENAME TO memory_evidence;
                    """
                )
            episode_columns = {
                row[1] for row in conn.execute("PRAGMA table_info(episodes)")
            }
            for name, definition in {
                "phase_summary_json": "TEXT NOT NULL DEFAULT '{}'",
                "boundary_signals_json": "TEXT NOT NULL DEFAULT '[]'",
                "extraction_run_id": "TEXT NOT NULL DEFAULT ''",
                "source_native_id": "TEXT NOT NULL DEFAULT ''",
            }.items():
                if name not in episode_columns:
                    conn.execute(f"ALTER TABLE episodes ADD COLUMN {name} {definition}")
            conn.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS idx_episode_native "
                "ON episodes(tenant_id,source_native_id) WHERE source_native_id<>''"
            )
            conn.execute(
                "INSERT INTO schema_meta(key, value) VALUES('schema_version', ?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (str(SCHEMA_VERSION),),
            )
            conn.commit()

    def connect(self) -> sqlite3.Connection:
        self.brain_dir.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(self.db_path), timeout=15.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=15000")
        return conn

    def read_connect(self) -> sqlite3.Connection:
        """Open an existing canonical store without creating or mutating it."""
        if not self.db_path.exists():
            raise FileNotFoundError(f"Company brain is not initialized: {self.db_path}")
        uri = f"file:{self.db_path.as_posix()}?mode=ro"
        conn = sqlite3.connect(uri, uri=True, timeout=15.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA query_only=ON")
        conn.execute("PRAGMA busy_timeout=15000")
        return conn

    def _write_blob(self, digest: str, content: bytes) -> str:
        relative = Path(digest[:2]) / digest[2:4] / digest
        destination = self.blob_dir / relative
        if destination.exists():
            return relative.as_posix()
        destination.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile("wb", dir=str(destination.parent), delete=False) as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
            temporary = Path(handle.name)
        try:
            os.replace(str(temporary), str(destination))
        finally:
            if temporary.exists():
                temporary.unlink()
        return relative.as_posix()

    def put_evidence(self, item: EvidenceInput) -> str:
        self.initialize()
        created = now_iso()
        artifact_type = item.artifact_type
        availability = "available"
        source_identity: Dict[str, Any] = {}
        source_locator = item.source_locator
        source_modified_at = item.source_modified_at
        if item.storage_mode == "reference":
            path = path_from_locator(item.source_locator)
            fingerprint = fingerprint_file(path)
            digest = fingerprint["content_hash"].removeprefix("sha256:")
            byte_length = int(fingerprint["byte_length"])
            source_locator = fingerprint["canonical_path"]
            source_modified_at = fingerprint["source_modified_at"]
            source_identity = fingerprint["source_identity"]
            if artifact_type == "plain_text":
                artifact_type = infer_artifact_type(path, item.mime_type)
            blob_path = ""
        else:
            assert item.content is not None
            digest = hashlib.sha256(item.content).hexdigest()
            byte_length = len(item.content)
            blob_path = self._write_blob(digest, item.content)
        identity = "\x1f".join((item.tenant_id, item.source_type, item.source_native_id, digest))
        evidence_id = "ev_" + hashlib.sha256(identity.encode("utf-8")).hexdigest()[:24]
        with self.connect() as conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO evidence(
                    evidence_id, tenant_id, source_type, source_locator, source_native_id,
                    content_hash, mime_type, byte_length, observed_at, source_modified_at,
                    classification, access_policy_json, retention_policy_id,
                    ingestion_run_id, supersedes_evidence_id, blob_path, storage_mode,
                    artifact_type, availability_status, source_identity_json, parser_json,
                    last_verified_at, created_at
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    evidence_id, item.tenant_id, item.source_type, source_locator,
                    item.source_native_id, "sha256:" + digest, item.mime_type,
                    byte_length, item.observed_at or created,
                    source_modified_at, item.classification,
                    _json(item.access_policy.to_dict()), item.retention_policy_id,
                    item.ingestion_run_id, item.supersedes_evidence_id, blob_path,
                    item.storage_mode, artifact_type, availability,
                    _json(source_identity), _json(item.parser), created, created,
                ),
            )
            if item.storage_mode == "reference":
                conn.execute(
                    "INSERT OR REPLACE INTO trusted_references VALUES(?,?,?,?)",
                    (evidence_id, source_locator, _json(source_identity), created),
                )
            conn.commit()
        return evidence_id

    def read_evidence(self, evidence_id: str, principal: Principal) -> bytes:
        if not self.db_path.exists():
            raise KeyError(f"Evidence not found: {evidence_id}")
        with self.read_connect() as conn:
            row = conn.execute("SELECT * FROM evidence WHERE evidence_id=?", (evidence_id,)).fetchone()
        if row is None:
            raise KeyError(f"Evidence not found: {evidence_id}")
        if not self._row_authorized(row, principal):
            raise PermissionError("Evidence is outside the principal's effective access policy")
        if row["storage_mode"] == "reference":
            with self.read_connect() as conn:
                trusted = conn.execute(
                    "SELECT * FROM trusted_references WHERE evidence_id=?", (evidence_id,)
                ).fetchone()
            if trusted is None:
                raise PermissionError("Reference is not registered for local file access")
            expected = {
                "canonical_path": trusted["canonical_path"],
                "content_hash": row["content_hash"],
                "byte_length": row["byte_length"],
                "source_identity": _json_load(trusted["source_identity_json"], {}),
            }
            return read_registered_bytes(Path(trusted["canonical_path"]), expected)
        path = self.blob_dir / row["blob_path"]
        if not path.exists():
            raise FileNotFoundError(f"Evidence blob is unavailable: {evidence_id}")
        return path.read_bytes()

    def inspect_evidence(
        self,
        evidence_id: str,
        principal: Principal,
        *,
        strong: bool = True,
        native_locator: Optional[Dict[str, Any]] = None,
        include_preview: bool = False,
        max_text: int = 16_000,
    ) -> Dict[str, Any]:
        """Inspect authorized evidence and optionally parse a bounded native region."""
        if not self.db_path.exists():
            raise KeyError(f"Evidence not found: {evidence_id}")
        with self.read_connect() as conn:
            row = conn.execute("SELECT * FROM evidence WHERE evidence_id=?", (evidence_id,)).fetchone()
            if row is None:
                raise KeyError(f"Evidence not found: {evidence_id}")
            if not self._row_authorized(row, principal):
                raise PermissionError("Evidence is outside the principal's effective access policy")
            trusted = conn.execute(
                "SELECT * FROM trusted_references WHERE evidence_id=?", (evidence_id,)
            ).fetchone()
        result = dict(row)
        result["access_policy"] = _json_load(result.pop("access_policy_json", ""), {})
        result["source_identity"] = _json_load(result.pop("source_identity_json", ""), {})
        result["parser"] = _json_load(result.pop("parser_json", ""), {})
        path: Optional[Path] = None
        if row["storage_mode"] == "reference":
            if trusted is None:
                availability = {"status": "forbidden", "reason": "reference registration missing"}
            else:
                path = Path(trusted["canonical_path"])
                availability = verify_reference(path, {
                    "canonical_path": trusted["canonical_path"],
                    "content_hash": row["content_hash"],
                    "byte_length": row["byte_length"],
                    "source_identity": _json_load(trusted["source_identity_json"], {}),
                }, strong=strong)
        else:
            path = self.blob_dir / row["blob_path"]
            availability = {
                "status": "available" if path.exists() else "unavailable",
                "reason": "managed blob present" if path.exists() else "managed blob missing",
            }
        result["availability"] = availability
        if include_preview and availability["status"] == "available" and path is not None:
            result["inspection"] = inspect_artifact_path(
                path,
                artifact_type=row["artifact_type"],
                native_locator=native_locator,
                max_text=max_text,
            )
            # Never expose the content-addressed internal path as the source locator.
            result["inspection"]["source_locator"] = row["source_locator"]
        return result

    def materialize_snapshot(self, evidence_id: str, principal: Principal) -> str:
        """Explicitly create an immutable snapshot from authorized evidence."""
        metadata = self.inspect_evidence(evidence_id, principal, strong=True)
        content = self.read_evidence(evidence_id, principal)
        return self.put_evidence(EvidenceInput(
            tenant_id=metadata["tenant_id"],
            source_type=metadata["source_type"] + "_snapshot",
            source_locator=metadata["source_locator"],
            source_native_id=metadata["source_native_id"] + ":snapshot:" + metadata["content_hash"],
            content=content,
            mime_type=metadata["mime_type"],
            storage_mode="snapshot",
            artifact_type=metadata["artifact_type"],
            observed_at=metadata["observed_at"],
            source_modified_at=metadata["source_modified_at"],
            classification=metadata["classification"],
            access_policy=AccessPolicy.from_dict(metadata["access_policy"]),
            retention_policy_id=metadata["retention_policy_id"],
            ingestion_run_id="explicit-materialization-v1",
            supersedes_evidence_id=evidence_id,
            parser=metadata["parser"],
        ))

    def resolve_evidence_path(self, evidence_id: str, principal: Principal) -> Path:
        """Return the verified local backing path for an authorized evidence record."""
        metadata = self.inspect_evidence(evidence_id, principal, strong=True)
        if metadata["availability"]["status"] != "available":
            raise ReferenceError(metadata["availability"].get("reason", "evidence unavailable"))
        if metadata["storage_mode"] == "reference":
            with self.read_connect() as conn:
                trusted = conn.execute(
                    "SELECT canonical_path FROM trusted_references WHERE evidence_id=?",
                    (evidence_id,),
                ).fetchone()
            if trusted is None:
                raise PermissionError("Reference registration is missing")
            return Path(trusted["canonical_path"])
        return self.blob_dir / metadata["blob_path"]

    def add_segment(self, item: EvidenceSegmentInput) -> str:
        self.initialize()
        locator_json = _json(item.native_locator)
        text_hash = hashlib.sha256(item.text.encode("utf-8")).hexdigest()
        extractor_json = _json(item.extractor)
        identity = "\x1f".join((item.evidence_id, locator_json, text_hash, extractor_json))
        segment_id = "seg_" + hashlib.sha256(identity.encode("utf-8")).hexdigest()[:24]
        with self.connect() as conn:
            exists = conn.execute(
                "SELECT 1 FROM evidence WHERE evidence_id=?", (item.evidence_id,)
            ).fetchone()
            if not exists:
                raise ValueError(f"Unknown evidence: {item.evidence_id}")
            conn.execute(
                "INSERT OR IGNORE INTO evidence_segments VALUES(?,?,?,?,?,?,?,?)",
                (
                    segment_id, item.evidence_id, locator_json, item.text,
                    "sha256:" + text_hash, extractor_json, item.confidence, now_iso(),
                ),
            )
            conn.commit()
        return segment_id

    def segments_for_evidence(
        self, evidence_id: str, principal: Principal,
    ) -> List[Dict[str, Any]]:
        if not self.db_path.exists():
            return []
        self.inspect_evidence(evidence_id, principal, strong=False)
        with self.read_connect() as conn:
            rows = conn.execute(
                "SELECT * FROM evidence_segments WHERE evidence_id=? ORDER BY created_at,segment_id",
                (evidence_id,),
            ).fetchall()
        output = []
        for row in rows:
            value = dict(row)
            value["native_locator"] = _json_load(value.pop("native_locator_json", ""), {})
            value["extractor"] = _json_load(value.pop("extractor_json", ""), {})
            output.append(value)
        return output

    def inspect_and_segment(
        self,
        evidence_id: str,
        principal: Principal,
        *,
        native_locator: Optional[Dict[str, Any]] = None,
        max_text: int = 16_000,
    ) -> Dict[str, Any]:
        result = self.inspect_evidence(
            evidence_id, principal, strong=True, native_locator=native_locator,
            include_preview=True, max_text=max_text,
        )
        inspection = result.get("inspection") or {}
        segment_ids = []
        for segment in inspection.get("segments", []):
            segment_ids.append(self.add_segment(EvidenceSegmentInput(
                evidence_id=evidence_id,
                native_locator=segment["native_locator"],
                text=segment.get("text", ""),
                extractor=inspection.get("parser", {}),
                confidence=1.0,
            )))
        result["segment_ids"] = segment_ids
        return result

    @staticmethod
    def session_id_for(tenant_id: str, source_type: str, source_native_id: str) -> str:
        identity = "\x1f".join((tenant_id, source_type, source_native_id))
        return "ses_" + hashlib.sha256(identity.encode("utf-8")).hexdigest()[:24]

    @staticmethod
    def event_id_for(
        tenant_id: str, source_type: str, source_native_id: str, evidence_id: str,
    ) -> str:
        identity = "\x1f".join((tenant_id, source_type, source_native_id, evidence_id))
        return "nev_" + hashlib.sha256(identity.encode("utf-8")).hexdigest()[:24]

    def upsert_session(self, item: SessionInput) -> str:
        self.initialize()
        session_id = self.session_id_for(
            item.tenant_id, item.source_type, item.source_native_id
        )
        now = now_iso()
        with self.connect() as conn:
            conn.execute(
                """INSERT INTO sessions(
                    session_id,tenant_id,source_type,source_native_id,title,project_id,
                    participants_json,started_at,ended_at,status,evidence_ids_json,
                    event_count,classification,access_policy_json,metadata_json,
                    created_at,updated_at
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(tenant_id,source_type,source_native_id) DO UPDATE SET
                    title=excluded.title,project_id=excluded.project_id,
                    participants_json=excluded.participants_json,
                    started_at=excluded.started_at,ended_at=excluded.ended_at,
                    status=excluded.status,evidence_ids_json=excluded.evidence_ids_json,
                    event_count=excluded.event_count,classification=excluded.classification,
                    access_policy_json=excluded.access_policy_json,
                    metadata_json=excluded.metadata_json,updated_at=excluded.updated_at""",
                (
                    session_id, item.tenant_id, item.source_type, item.source_native_id,
                    item.title, item.project_id, _json(item.participants), item.started_at,
                    item.ended_at, item.status, _json(item.evidence_ids), item.event_count,
                    item.classification, _json(item.access_policy.to_dict()),
                    _json(item.metadata), now, now,
                ),
            )
            conn.commit()
        return session_id

    def add_normalized_event(self, item: NormalizedEventInput) -> str:
        self.initialize()
        session_id = self.session_id_for(
            item.tenant_id, item.source_type, item.session_native_id
        )
        event_id = self.event_id_for(
            item.tenant_id, item.source_type, item.source_native_id, item.evidence_id,
        )
        segment_id = item.segment_id
        if not segment_id:
            segment_id = self.add_segment(EvidenceSegmentInput(
                evidence_id=item.evidence_id,
                native_locator=item.native_locator,
                text=item.summary,
                extractor={"kind": "normalized_event", "version": "session-engine-v1"},
                confidence=1.0,
            ))
        with self.connect() as conn:
            if conn.execute(
                "SELECT 1 FROM sessions WHERE session_id=?", (session_id,)
            ).fetchone() is None:
                raise ValueError(f"Session must be stored before its events: {session_id}")
            conn.execute(
                """INSERT OR IGNORE INTO normalized_events(
                    event_id,tenant_id,source_type,source_native_id,session_id,evidence_id,
                    segment_id,event_type,actor_type,actor_id,role,occurred_at,
                    native_locator_json,summary,project_candidates_json,entities_json,
                    classification,access_policy_json,ingestion_run_id,created_at
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    event_id, item.tenant_id, item.source_type, item.source_native_id,
                    session_id, item.evidence_id, segment_id, item.event_type,
                    item.actor_type, item.actor_id, item.role, item.occurred_at,
                    _json(item.native_locator), item.summary, _json(item.project_candidates),
                    _json(item.entities), item.classification,
                    _json(item.access_policy.to_dict()), item.ingestion_run_id, now_iso(),
                ),
            )
            conn.commit()
        return event_id

    def list_session_events(
        self, session_id: str, principal: Principal,
    ) -> List[Dict[str, Any]]:
        if not self.db_path.exists():
            return []
        with self.read_connect() as conn:
            session = conn.execute(
                "SELECT * FROM sessions WHERE session_id=?", (session_id,)
            ).fetchone()
            if session is None:
                raise KeyError(f"Session not found: {session_id}")
            if not self._row_authorized(session, principal):
                raise PermissionError("Session is outside the principal's effective access policy")
            rows = conn.execute(
                "SELECT * FROM normalized_events WHERE session_id=? "
                "ORDER BY occurred_at,event_id", (session_id,),
            ).fetchall()
        return [self._event_dict(row) for row in rows if self._row_authorized(row, principal)]

    def list_sessions(
        self, principal: Principal, *, project_id: str = "", limit: int = 100,
    ) -> List[Dict[str, Any]]:
        if not self.db_path.exists():
            return []
        sql = "SELECT * FROM sessions WHERE tenant_id=?"
        params: List[Any] = [principal.tenant_id]
        if project_id:
            sql += " AND project_id=?"
            params.append(project_id)
        sql += " ORDER BY started_at DESC,session_id LIMIT ?"
        params.append(max(1, min(limit, 1000)))
        with self.read_connect() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [self._session_dict(row) for row in rows if self._row_authorized(row, principal)]

    def add_episode(self, item: EpisodeInput) -> str:
        self.initialize()
        seed = item.source_native_id or "\x1f".join(item.event_ids)
        episode_id = "ep_" + hashlib.sha256(
            f"{item.tenant_id}\x1f{seed}".encode("utf-8")
        ).hexdigest()[:24]
        now = now_iso()
        with self.connect() as conn:
            for table, column, identifiers in (
                ("sessions", "session_id", item.session_ids),
                ("evidence", "evidence_id", item.evidence_ids),
                ("normalized_events", "event_id", item.event_ids),
            ):
                placeholders = ",".join("?" for _ in identifiers)
                found = conn.execute(
                    f"SELECT COUNT(*) FROM {table} WHERE tenant_id=? AND {column} IN ({placeholders})",
                    (item.tenant_id, *identifiers),
                ).fetchone()[0]
                if found != len(set(identifiers)):
                    raise ValueError(f"Episode contains unknown or cross-tenant {column} values")
            conn.execute(
                """INSERT INTO episodes(
                    episode_id,tenant_id,title,goal,project_id,participants_json,
                    started_at,ended_at,status,outcome_summary,session_ids_json,
                    evidence_ids_json,confidence,classification,access_policy_json,
                    phase_summary_json,boundary_signals_json,extraction_run_id,
                    source_native_id,created_at,updated_at
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(tenant_id,source_native_id) WHERE source_native_id<>'' DO UPDATE SET
                    title=excluded.title,goal=excluded.goal,project_id=excluded.project_id,
                    participants_json=excluded.participants_json,started_at=excluded.started_at,
                    ended_at=excluded.ended_at,status=excluded.status,
                    outcome_summary=excluded.outcome_summary,
                    session_ids_json=excluded.session_ids_json,
                    evidence_ids_json=excluded.evidence_ids_json,confidence=excluded.confidence,
                    classification=excluded.classification,
                    access_policy_json=excluded.access_policy_json,
                    phase_summary_json=excluded.phase_summary_json,
                    boundary_signals_json=excluded.boundary_signals_json,
                    extraction_run_id=excluded.extraction_run_id,updated_at=excluded.updated_at""",
                (
                    episode_id, item.tenant_id, item.title, item.goal, item.project_id,
                    _json(item.participants), item.started_at, item.ended_at, item.status,
                    item.outcome_summary, _json(item.session_ids), _json(item.evidence_ids),
                    item.confidence, item.classification, _json(item.access_policy.to_dict()),
                    _json(item.phase_summary), _json(item.boundary_signals),
                    item.extraction_run_id, seed, now, now,
                ),
            )
            conn.execute("DELETE FROM episode_events WHERE episode_id=?", (episode_id,))
            phases = item.phase_summary.get("event_phases", {})
            for ordinal, event_id in enumerate(item.event_ids):
                conn.execute(
                    "INSERT INTO episode_events VALUES(?,?,?,?)",
                    (episode_id, event_id, ordinal, phases.get(event_id, "work")),
                )
            conn.commit()
        return episode_id

    def list_episodes(
        self, principal: Principal, *, project_id: str = "", limit: int = 100,
    ) -> List[Dict[str, Any]]:
        if not self.db_path.exists():
            return []
        sql = "SELECT * FROM episodes WHERE tenant_id=?"
        params: List[Any] = [principal.tenant_id]
        if project_id:
            sql += " AND project_id=?"
            params.append(project_id)
        sql += " ORDER BY started_at DESC,episode_id LIMIT ?"
        params.append(max(1, min(limit, 1000)))
        with self.read_connect() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [self._episode_dict(row) for row in rows if self._row_authorized(row, principal)]

    def get_episode(self, episode_id: str, principal: Principal) -> Dict[str, Any]:
        if not self.db_path.exists():
            raise KeyError(f"Episode not found: {episode_id}")
        with self.read_connect() as conn:
            row = conn.execute("SELECT * FROM episodes WHERE episode_id=?", (episode_id,)).fetchone()
            if row is None:
                raise KeyError(f"Episode not found: {episode_id}")
            if not self._row_authorized(row, principal):
                raise PermissionError("Episode is outside the principal's effective access policy")
            events = conn.execute(
                """SELECT e.*,ee.ordinal,ee.phase FROM episode_events ee
                   JOIN normalized_events e ON e.event_id=ee.event_id
                   WHERE ee.episode_id=? ORDER BY ee.ordinal""", (episode_id,),
            ).fetchall()
            memories = [
                dict(link) for link in conn.execute(
                    "SELECT * FROM episode_memories WHERE episode_id=?", (episode_id,)
                )
            ]
        result = self._episode_dict(row)
        result["events"] = [
            {**self._event_dict(event), "ordinal": event["ordinal"], "phase": event["phase"]}
            for event in events if self._row_authorized(event, principal)
        ]
        result["memory_links"] = memories
        return result

    def search_episodes(
        self, query: str, principal: Principal, *, project_id: str = "", limit: int = 10,
    ) -> List[Dict[str, Any]]:
        terms = [term.lower() for term in __import__("re").findall(r"[A-Za-z0-9_]+", query) if len(term) > 1]
        episodes = self.list_episodes(principal, project_id=project_id, limit=1000)
        for episode in episodes:
            text = " ".join((
                episode["title"], episode["goal"], episode["outcome_summary"],
                " ".join(episode["boundary_signals"]),
            )).lower()
            episode["score"] = round(
                sum(1 for term in set(terms) if term in text) / max(1, len(set(terms))), 6
            )
        episodes.sort(key=lambda item: (item["score"], item["confidence"], item["started_at"]), reverse=True)
        if terms:
            episodes = [episode for episode in episodes if episode["score"] > 0]
        return episodes[:max(1, limit)]

    def record_extraction_run(
        self, *, run_id: str, tenant_id: str, evidence_id: str,
        pipeline_version: str, status: str, dry_run: bool, input_hash: str,
        metrics: Dict[str, Any], error: str = "", started_at: str = "",
    ) -> None:
        self.initialize()
        completed = now_iso()
        with self.connect() as conn:
            conn.execute(
                """INSERT INTO extraction_runs VALUES(?,?,?,?,?,?,?,?,?,?,?)
                   ON CONFLICT(tenant_id,evidence_id,pipeline_version,dry_run) DO UPDATE SET
                   run_id=excluded.run_id,status=excluded.status,metrics_json=excluded.metrics_json,
                   error=excluded.error,started_at=excluded.started_at,
                   completed_at=excluded.completed_at""",
                (
                    run_id, tenant_id, evidence_id, pipeline_version, status,
                    int(dry_run), input_hash, _json(metrics), error,
                    started_at or completed, completed,
                ),
            )
            conn.commit()

    def link_episode_memory(
        self, episode_id: str, memory_id: str, event_id: str, extraction_run_id: str,
    ) -> None:
        with self.connect() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO episode_memories VALUES(?,?,?,?)",
                (episode_id, memory_id, event_id, extraction_run_id),
            )
            conn.commit()

    def set_checkpoint(self, connector_id: str, scope: str, checkpoint: Dict[str, Any]) -> None:
        self.initialize()
        with self.connect() as conn:
            conn.execute(
                "INSERT INTO connector_checkpoints VALUES(?,?,?,?) "
                "ON CONFLICT(connector_id,scope) DO UPDATE SET "
                "checkpoint_json=excluded.checkpoint_json,updated_at=excluded.updated_at",
                (connector_id, scope, _json(checkpoint), now_iso()),
            )
            conn.commit()

    def get_checkpoint(self, connector_id: str, scope: str) -> Dict[str, Any]:
        if not self.db_path.exists():
            return {}
        with self.read_connect() as conn:
            row = conn.execute(
                "SELECT checkpoint_json FROM connector_checkpoints WHERE connector_id=? AND scope=?",
                (connector_id, scope),
            ).fetchone()
        return _json_load(row[0], {}) if row else {}

    def add_memory(self, item: MemoryInput) -> str:
        self.initialize()
        seed = item.source_native_id or uuid.uuid4().hex
        memory_id = "mem_" + hashlib.sha256(
            f"{item.tenant_id}\x1f{seed}".encode("utf-8")
        ).hexdigest()[:24]
        created = now_iso()
        with self.connect() as conn:
            evidence_ids = [reference.evidence_id for reference in item.evidence]
            placeholders = ",".join("?" for _ in evidence_ids)
            found = {
                row[0] for row in conn.execute(
                    f"SELECT evidence_id FROM evidence WHERE tenant_id=? AND evidence_id IN ({placeholders})",
                    (item.tenant_id, *evidence_ids),
                )
            }
            missing = set(evidence_ids) - found
            if missing:
                raise ValueError(f"Unknown or cross-tenant evidence: {', '.join(sorted(missing))}")
            for reference in item.evidence:
                if reference.segment_id:
                    segment = conn.execute(
                        "SELECT evidence_id FROM evidence_segments WHERE segment_id=?",
                        (reference.segment_id,),
                    ).fetchone()
                    if segment is None or segment["evidence_id"] != reference.evidence_id:
                        raise ValueError(
                            f"Evidence segment does not belong to cited evidence: {reference.segment_id}"
                        )

            existing = conn.execute(
                "SELECT memory_id FROM memories WHERE memory_id=?", (memory_id,)
            ).fetchone()
            if existing:
                return memory_id

            conn.execute(
                """
                INSERT INTO memories(
                    memory_id, tenant_id, memory_type, title, statement, rationale,
                    project_id, owner_ids_json, lifecycle, confidence, importance,
                    valid_from, valid_to, observed_at, supersedes_json, classification,
                    access_policy_json, extractor_json, source_native_id, created_at, updated_at
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    memory_id, item.tenant_id, item.memory_type, item.title,
                    item.statement, item.rationale, item.project_id,
                    _json(item.owner_ids), item.lifecycle, item.confidence, item.importance,
                    item.valid_from, item.valid_to, item.observed_at or created,
                    _json(item.supersedes), item.classification,
                    _json(item.access_policy.to_dict()), _json(item.extractor),
                    item.source_native_id or seed, created, created,
                ),
            )
            for reference in item.evidence:
                conn.execute(
                    "INSERT INTO memory_evidence(memory_id,evidence_id,segment_id,locator,support,quote) "
                    "VALUES(?,?,?,?,?,?)",
                    (
                        memory_id, reference.evidence_id, reference.segment_id, reference.locator,
                        reference.support, reference.quote,
                    ),
                )
            conn.execute(
                "INSERT INTO memory_fts(memory_id,title,statement,rationale,project_id,memory_type) "
                "VALUES(?,?,?,?,?,?)",
                (
                    memory_id, item.title, item.statement, item.rationale,
                    item.project_id, item.memory_type,
                ),
            )
            for entity_id in item.entity_ids:
                entity = conn.execute(
                    "SELECT tenant_id FROM entities WHERE entity_id=?", (entity_id,)
                ).fetchone()
                if entity is None or entity["tenant_id"] != item.tenant_id:
                    raise ValueError(f"Unknown or cross-tenant entity: {entity_id}")
                conn.execute(
                    "INSERT OR IGNORE INTO memory_entities VALUES(?,?,?)",
                    (memory_id, entity_id, "ABOUT"),
                )
            for old_id in item.supersedes:
                old = conn.execute(
                    "SELECT lifecycle FROM memories WHERE memory_id=? AND tenant_id=?",
                    (old_id, item.tenant_id),
                ).fetchone()
                if old and old["lifecycle"] not in {"superseded", "retracted"}:
                    conn.execute(
                        "UPDATE memories SET lifecycle='superseded', updated_at=? WHERE memory_id=?",
                        (created, old_id),
                    )
                    self._record_lifecycle_event(
                        conn, item.tenant_id, old_id, old["lifecycle"], "superseded",
                        f"Superseded by {memory_id}", "system", created,
                    )
            conn.commit()
        return memory_id

    def upsert_entity(
        self, *, tenant_id: str, entity_type: str, canonical_name: str,
        aliases: Optional[Sequence[str]] = None, classification: str = "restricted",
        access_policy: Optional[AccessPolicy] = None,
    ) -> str:
        self.initialize()
        normalized_name = " ".join(canonical_name.split()).strip()
        if not normalized_name:
            raise ValueError("canonical entity name is required")
        normalized_type = entity_type.strip().lower()
        identity = f"{tenant_id}\x1f{normalized_type}\x1f{normalized_name.lower()}"
        entity_id = "ent_" + hashlib.sha256(identity.encode("utf-8")).hexdigest()[:24]
        now = now_iso()
        policy = access_policy or AccessPolicy()
        with self.connect() as conn:
            conn.execute(
                """INSERT INTO entities VALUES(?,?,?,?,?,?,?,?,?)
                   ON CONFLICT(entity_id) DO UPDATE SET
                   aliases_json=excluded.aliases_json,classification=excluded.classification,
                   access_policy_json=excluded.access_policy_json,updated_at=excluded.updated_at""",
                (
                    entity_id, tenant_id, normalized_type, normalized_name,
                    _json(sorted(set(aliases or []))), classification,
                    _json(policy.to_dict()), now, now,
                ),
            )
            conn.commit()
        return entity_id

    def _record_lifecycle_event(
        self, conn: sqlite3.Connection, tenant_id: str, memory_id: str,
        from_lifecycle: str, to_lifecycle: str, reason: str, actor: str,
        created_at: Optional[str] = None,
    ) -> None:
        conn.execute(
            "INSERT INTO lifecycle_events VALUES(?,?,?,?,?,?,?,?)",
            (
                "lev_" + uuid.uuid4().hex[:24], tenant_id, memory_id,
                from_lifecycle, to_lifecycle, reason, actor, created_at or now_iso(),
            ),
        )

    def transition_memory(
        self, memory_id: str, to_lifecycle: str, principal: Principal,
        reason: str = "",
    ) -> Dict[str, Any]:
        self.initialize()
        to_lifecycle = to_lifecycle.strip().lower()
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM memories WHERE memory_id=?", (memory_id,)).fetchone()
            if row is None:
                raise KeyError(f"Memory not found: {memory_id}")
            if not self._row_authorized(row, principal):
                raise PermissionError("Memory is outside the principal's effective access policy")
            if not self.evidence_for_memories([memory_id], principal).get(memory_id):
                raise PermissionError("Memory evidence is outside the principal's effective access policy")
            current = row["lifecycle"]
            if to_lifecycle not in TRANSITIONS.get(current, set()):
                raise ValueError(f"Invalid memory transition: {current} -> {to_lifecycle}")
            updated = now_iso()
            conn.execute(
                "UPDATE memories SET lifecycle=?, updated_at=? WHERE memory_id=?",
                (to_lifecycle, updated, memory_id),
            )
            self._record_lifecycle_event(
                conn, row["tenant_id"], memory_id, current, to_lifecycle,
                reason, principal.principal_id, updated,
            )
            conn.commit()
        return self.get_memory(memory_id, principal)

    def get_memory(self, memory_id: str, principal: Principal) -> Dict[str, Any]:
        if not self.db_path.exists():
            raise KeyError(f"Memory not found: {memory_id}")
        with self.read_connect() as conn:
            row = conn.execute("SELECT * FROM memories WHERE memory_id=?", (memory_id,)).fetchone()
            if row is None:
                raise KeyError(f"Memory not found: {memory_id}")
            if not self._row_authorized(row, principal):
                raise PermissionError("Memory is outside the principal's effective access policy")
        evidence = self.evidence_for_memories([memory_id], principal).get(memory_id, [])
        if not evidence:
            raise PermissionError("Memory evidence is outside the principal's effective access policy")
        result = self._memory_dict(row)
        result["evidence"] = evidence
        return result

    def list_accessible_memories(
        self,
        principal: Principal,
        project_id: str = "",
        memory_types: Optional[Sequence[str]] = None,
        as_of: str = "",
        include_candidates: bool = False,
        include_stale: bool = True,
        limit: int = 50_000,
    ) -> List[Dict[str, Any]]:
        if not self.db_path.exists():
            return []
        lifecycles = list(ACTIVE_LIFECYCLES if include_stale else CURRENT_LIFECYCLES)
        if include_candidates:
            lifecycles.extend(("candidate", "reviewed"))
        clauses = ["tenant_id=?", "lifecycle IN (" + ",".join("?" for _ in lifecycles) + ")"]
        params: List[Any] = [principal.tenant_id, *lifecycles]
        if project_id:
            clauses.append("project_id=?")
            params.append(project_id)
        if memory_types:
            clauses.append("memory_type IN (" + ",".join("?" for _ in memory_types) + ")")
            params.extend(memory_types)
        if as_of:
            clauses.append("(valid_from='' OR valid_from<=?)")
            clauses.append("(valid_to='' OR valid_to>?)")
            params.extend((as_of, as_of))
        sql = "SELECT * FROM memories WHERE " + " AND ".join(clauses) + " ORDER BY updated_at DESC LIMIT ?"
        params.append(limit)
        with self.read_connect() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [self._memory_dict(row) for row in rows if self._row_authorized(row, principal)]

    def fts_ranks(self, query: str, allowed_ids: Iterable[str]) -> Dict[str, float]:
        """Return FTS ranks only for IDs authorized before retrieval."""
        if not self.db_path.exists():
            return {}
        identifiers = list(dict.fromkeys(allowed_ids))
        if not identifiers or not query.strip():
            return {}
        tokens = [token for token in __import__("re").findall(r"[A-Za-z0-9_]+", query) if len(token) > 1]
        if not tokens:
            return {}
        expression = " OR ".join('"' + token.replace('"', '') + '"' for token in tokens)
        ranks: Dict[str, float] = {}
        with self.read_connect() as conn:
            for offset in range(0, len(identifiers), 500):
                chunk = identifiers[offset:offset + 500]
                placeholders = ",".join("?" for _ in chunk)
                try:
                    rows = conn.execute(
                        f"SELECT memory_id,bm25(memory_fts) rank FROM memory_fts "
                        f"WHERE memory_fts MATCH ? AND memory_id IN ({placeholders})",
                        (expression, *chunk),
                    ).fetchall()
                except sqlite3.OperationalError:
                    rows = []
                for row in rows:
                    ranks[row["memory_id"]] = float(row["rank"])
        return ranks

    def evidence_for_memories(
        self, memory_ids: Sequence[str], principal: Principal,
    ) -> Dict[str, List[Dict[str, Any]]]:
        if not memory_ids or not self.db_path.exists():
            return {}
        output: Dict[str, List[Dict[str, Any]]] = {memory_id: [] for memory_id in memory_ids}
        with self.read_connect() as conn:
            for offset in range(0, len(memory_ids), 500):
                chunk = list(memory_ids[offset:offset + 500])
                placeholders = ",".join("?" for _ in chunk)
                rows = conn.execute(
                    f"""
                    SELECT me.memory_id,me.evidence_id,me.locator,me.support,me.quote,
                           me.segment_id,
                           e.tenant_id,e.classification,e.access_policy_json,e.source_locator,
                           e.source_type,e.observed_at,e.storage_mode,e.artifact_type,
                           e.mime_type,e.content_hash,e.byte_length,e.availability_status,
                           es.native_locator_json
                    FROM memory_evidence me JOIN evidence e ON e.evidence_id=me.evidence_id
                    LEFT JOIN evidence_segments es ON es.segment_id=me.segment_id
                    WHERE me.memory_id IN ({placeholders})
                    """,
                    chunk,
                ).fetchall()
                for row in rows:
                    if self._row_authorized(row, principal):
                        output[row["memory_id"]].append({
                            "evidence_id": row["evidence_id"],
                            "segment_id": row["segment_id"],
                            "locator": row["locator"],
                            "native_locator": _json_load(row["native_locator_json"], {}),
                            "support": row["support"],
                            "quote": row["quote"],
                            "source_locator": row["source_locator"],
                            "source_type": row["source_type"],
                            "observed_at": row["observed_at"],
                            "storage_mode": row["storage_mode"],
                            "artifact_type": row["artifact_type"],
                            "mime_type": row["mime_type"],
                            "content_hash": row["content_hash"],
                            "byte_length": row["byte_length"],
                            "availability_status": row["availability_status"],
                        })
        return output

    def related_conflicts(self, memory_ids: Sequence[str], principal: Principal) -> List[Dict[str, Any]]:
        if not memory_ids or not self.db_path.exists():
            return []
        output: List[Dict[str, Any]] = []
        with self.read_connect() as conn:
            for offset in range(0, len(memory_ids), 500):
                chunk = list(memory_ids[offset:offset + 500])
                placeholders = ",".join("?" for _ in chunk)
                rows = conn.execute(
                    f"SELECT * FROM relations WHERE tenant_id=? AND relation_type='CONTRADICTS' "
                    f"AND (source_id IN ({placeholders}) OR target_id IN ({placeholders}))",
                    (principal.tenant_id, *chunk, *chunk),
                ).fetchall()
                output.extend(dict(row) for row in rows if self._row_authorized(row, principal))
        return output

    def health(self) -> Dict[str, Any]:
        if not self.db_path.exists():
            return {
                "schema_version": SCHEMA_VERSION,
                "database": str(self.db_path),
                "integrity": "not_initialized",
                "evidence": 0,
                "memories": 0,
                "sessions": 0,
                "normalized_events": 0,
                "episodes": 0,
                "extraction_runs": 0,
                "memory_fts": 0,
                "lifecycle": {},
                "orphan_evidence_references": 0,
                "missing_blobs": [],
                "references": 0,
                "reference_issues": [],
                "snapshot_bytes": 0,
                "managed_bytes": 0,
                "reference_source_bytes": 0,
                "healthy": False,
            }
        with self.read_connect() as conn:
            memories = conn.execute("SELECT COUNT(*) FROM memories").fetchone()[0]
            evidence = conn.execute("SELECT COUNT(*) FROM evidence").fetchone()[0]
            fts = conn.execute("SELECT COUNT(*) FROM memory_fts").fetchone()[0]
            sessions = conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
            normalized_events = conn.execute("SELECT COUNT(*) FROM normalized_events").fetchone()[0]
            episodes = conn.execute("SELECT COUNT(*) FROM episodes").fetchone()[0]
            extraction_runs = conn.execute("SELECT COUNT(*) FROM extraction_runs").fetchone()[0]
            lifecycle = {
                row[0]: row[1]
                for row in conn.execute("SELECT lifecycle,COUNT(*) FROM memories GROUP BY lifecycle")
            }
            orphan_refs = conn.execute(
                """SELECT COUNT(*) FROM memory_evidence me
                   LEFT JOIN evidence e ON e.evidence_id=me.evidence_id
                   WHERE e.evidence_id IS NULL"""
            ).fetchone()[0]
            evidence_rows = conn.execute(
                "SELECT evidence_id,blob_path,storage_mode,byte_length,content_hash,"
                "source_identity_json,source_locator FROM evidence"
            ).fetchall()
            trusted_rows = {
                row["evidence_id"]: row for row in conn.execute("SELECT * FROM trusted_references")
            }
            integrity = conn.execute("PRAGMA quick_check").fetchone()[0]
        missing_blobs = [
            row["evidence_id"] for row in evidence_rows
            if row["storage_mode"] != "reference"
            and (not row["blob_path"] or not (self.blob_dir / row["blob_path"]).exists())
        ]
        reference_issues = []
        reference_source_bytes = 0
        snapshot_bytes = 0
        managed_bytes = 0
        for row in evidence_rows:
            if row["storage_mode"] == "reference":
                reference_source_bytes += row["byte_length"]
                trusted = trusted_rows.get(row["evidence_id"])
                if trusted is None:
                    reference_issues.append({"evidence_id": row["evidence_id"], "status": "forbidden"})
                    continue
                check = verify_reference(Path(trusted["canonical_path"]), {
                    "canonical_path": trusted["canonical_path"],
                    "content_hash": row["content_hash"],
                    "byte_length": row["byte_length"],
                    "source_identity": _json_load(trusted["source_identity_json"], {}),
                }, strong=True)
                if check["status"] != "available":
                    reference_issues.append({
                        "evidence_id": row["evidence_id"], "status": check["status"],
                        "reason": check["reason"],
                    })
            elif row["storage_mode"] == "snapshot":
                snapshot_bytes += row["byte_length"]
            else:
                managed_bytes += row["byte_length"]
        return {
            "schema_version": SCHEMA_VERSION,
            "database": str(self.db_path),
            "integrity": integrity,
            "evidence": evidence,
            "memories": memories,
            "sessions": sessions,
            "normalized_events": normalized_events,
            "episodes": episodes,
            "extraction_runs": extraction_runs,
            "memory_fts": fts,
            "lifecycle": lifecycle,
            "orphan_evidence_references": orphan_refs,
            "missing_blobs": missing_blobs,
            "references": sum(1 for row in evidence_rows if row["storage_mode"] == "reference"),
            "reference_issues": reference_issues,
            "reference_source_bytes": reference_source_bytes,
            "snapshot_bytes": snapshot_bytes,
            "managed_bytes": managed_bytes,
            "copied_source_bytes": snapshot_bytes,
            "reference_copy_amplification": (
                round(snapshot_bytes / reference_source_bytes, 6) if reference_source_bytes else 0.0
            ),
            "healthy": (
                integrity == "ok" and not orphan_refs and not missing_blobs
                and not reference_issues and fts == memories
            ),
        }

    def evaluate(self) -> Dict[str, Any]:
        """Run storage, provenance, and projection acceptance checks."""
        health = self.health()
        if not self.db_path.exists():
            return {"passed": False, "health": health, "checks": {"initialized": False}}
        with self.read_connect() as conn:
            segments = conn.execute("SELECT COUNT(*) FROM evidence_segments").fetchone()[0]
            cited_memories = conn.execute(
                "SELECT COUNT(DISTINCT memory_id) FROM memory_evidence"
            ).fetchone()[0]
            reference_blob_rows = conn.execute(
                "SELECT COUNT(*) FROM evidence WHERE storage_mode='reference' AND blob_path<>''"
            ).fetchone()[0]
            broken_segments = conn.execute(
                """SELECT COUNT(*) FROM memory_evidence me
                   LEFT JOIN evidence_segments es ON es.segment_id=me.segment_id
                   WHERE me.segment_id<>'' AND es.segment_id IS NULL"""
            ).fetchone()[0]
            by_artifact_type = {
                row[0]: row[1] for row in conn.execute(
                    "SELECT artifact_type,COUNT(*) FROM evidence GROUP BY artifact_type"
                )
            }
            orphan_episode_events = conn.execute(
                """SELECT COUNT(*) FROM episode_events ee
                   LEFT JOIN episodes ep ON ep.episode_id=ee.episode_id
                   LEFT JOIN normalized_events ne ON ne.event_id=ee.event_id
                   WHERE ep.episode_id IS NULL OR ne.event_id IS NULL"""
            ).fetchone()[0]
            uncited_episode_memories = conn.execute(
                """SELECT COUNT(*) FROM episode_memories em
                   LEFT JOIN memory_evidence me ON me.memory_id=em.memory_id
                   WHERE me.memory_id IS NULL"""
            ).fetchone()[0]
            events_without_segments = conn.execute(
                "SELECT COUNT(*) FROM normalized_events WHERE segment_id=''"
            ).fetchone()[0]
            failed_runs = conn.execute(
                "SELECT COUNT(*) FROM extraction_runs WHERE status='failed'"
            ).fetchone()[0]
        checks = {
            "initialized": True,
            "database_integrity": health["integrity"] == "ok",
            "projection_cardinality": health["memory_fts"] == health["memories"],
            "citation_integrity": (
                health["orphan_evidence_references"] == 0 and broken_segments == 0
            ),
            "reference_mode_copied_bytes_zero": reference_blob_rows == 0,
            "registered_references_available": not health["reference_issues"],
            "managed_blobs_available": not health["missing_blobs"],
            "episode_membership_integrity": orphan_episode_events == 0,
            "episode_memory_citations": uncited_episode_memories == 0,
            "normalized_events_are_citable": events_without_segments == 0,
        }
        return {
            "passed": all(checks.values()),
            "checks": checks,
            "metrics": {
                "evidence": health["evidence"],
                "memories": health["memories"],
                "cited_memories": cited_memories,
                "segments": segments,
                "artifact_types": by_artifact_type,
                "reference_source_bytes": health["reference_source_bytes"],
                "reference_mode_copied_bytes": 0 if reference_blob_rows == 0 else None,
                "explicit_snapshot_bytes": health["snapshot_bytes"],
                "managed_bytes": health["managed_bytes"],
                "broken_segment_citations": broken_segments,
                "sessions": health["sessions"],
                "normalized_events": health["normalized_events"],
                "episodes": health["episodes"],
                "extraction_runs": health["extraction_runs"],
                "failed_extraction_runs": failed_runs,
                "orphan_episode_events": orphan_episode_events,
                "uncited_episode_memories": uncited_episode_memories,
                "events_without_segments": events_without_segments,
            },
            "health": health,
        }

    def _session_dict(self, row: sqlite3.Row) -> Dict[str, Any]:
        value = dict(row)
        value["participants"] = _json_load(value.pop("participants_json", ""), [])
        value["evidence_ids"] = _json_load(value.pop("evidence_ids_json", ""), [])
        value["access_policy"] = _json_load(value.pop("access_policy_json", ""), {})
        value["metadata"] = _json_load(value.pop("metadata_json", ""), {})
        return value

    def _event_dict(self, row: sqlite3.Row) -> Dict[str, Any]:
        value = dict(row)
        value["native_locator"] = _json_load(value.pop("native_locator_json", ""), {})
        value["project_candidates"] = _json_load(value.pop("project_candidates_json", ""), [])
        value["entities"] = _json_load(value.pop("entities_json", ""), [])
        value["access_policy"] = _json_load(value.pop("access_policy_json", ""), {})
        return value

    def _episode_dict(self, row: sqlite3.Row) -> Dict[str, Any]:
        value = dict(row)
        value["participants"] = _json_load(value.pop("participants_json", ""), [])
        value["session_ids"] = _json_load(value.pop("session_ids_json", ""), [])
        value["evidence_ids"] = _json_load(value.pop("evidence_ids_json", ""), [])
        value["access_policy"] = _json_load(value.pop("access_policy_json", ""), {})
        value["phase_summary"] = _json_load(value.pop("phase_summary_json", ""), {})
        value["boundary_signals"] = _json_load(value.pop("boundary_signals_json", ""), [])
        return value

    def _memory_dict(self, row: sqlite3.Row) -> Dict[str, Any]:
        value = dict(row)
        value["owner_ids"] = _json_load(value.pop("owner_ids_json", ""), [])
        value["supersedes"] = _json_load(value.pop("supersedes_json", ""), [])
        value["access_policy"] = _json_load(value.pop("access_policy_json", ""), {})
        value["extractor"] = _json_load(value.pop("extractor_json", ""), {})
        return value

    def _row_authorized(self, row: sqlite3.Row, principal: Principal) -> bool:
        if row["tenant_id"] != principal.tenant_id:
            return False
        classification = row["classification"] or "restricted"
        if CLASSIFICATION_RANK.get(classification, 999) > CLASSIFICATION_RANK[principal.clearance]:
            return False
        policy = AccessPolicy.from_dict(_json_load(row["access_policy_json"], {}))
        groups = set(principal.groups)
        projects = set(principal.projects)
        if principal.principal_id in policy.denied_principals or groups.intersection(policy.denied_groups):
            return False
        grants_present = bool(
            policy.allowed_principals or policy.allowed_groups or policy.allowed_projects
        )
        if not grants_present:
            return True
        return bool(
            principal.principal_id in policy.allowed_principals
            or groups.intersection(policy.allowed_groups)
            or projects.intersection(policy.allowed_projects)
        )
