"""Additive persistence for Trusted Memory Runtime metadata.

This module extends the existing CompanyBrain SQLite database in place. It does
not introduce a second database and it does not alter lifecycle state. Runtime
schema versioning is tracked separately so the existing CompanyBrain schema can
continue to evolve independently.
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any, Dict, List

from llm_kosh.company_brain.store import CompanyBrainStore
from llm_kosh.core.utils import now_iso

from .models import AdmissionAssessment, MemoryProposal


RUNTIME_SCHEMA_VERSION = 1

_MEMORY_COLUMNS = {
    "authority": "TEXT NOT NULL DEFAULT ''",
    "risk_tier": "TEXT NOT NULL DEFAULT ''",
    "subject": "TEXT NOT NULL DEFAULT ''",
    "predicate": "TEXT NOT NULL DEFAULT ''",
    "object_value": "TEXT NOT NULL DEFAULT ''",
    "admission_decision": "TEXT NOT NULL DEFAULT ''",
    "admission_policy_version": "TEXT NOT NULL DEFAULT ''",
}


class RuntimeStore:
    """Trusted-memory metadata stored inside the canonical CompanyBrain DB."""

    def __init__(self, root: Path):
        self.root = Path(root).expanduser().resolve()
        self.base = CompanyBrainStore(self.root)

    @property
    def db_path(self) -> Path:
        return self.base.db_path

    def migration_plan(self) -> Dict[str, Any]:
        """Describe additive changes without writing anything."""

        if not self.db_path.exists():
            return {
                "runtime_schema_version": RUNTIME_SCHEMA_VERSION,
                "database_exists": False,
                "existing_memories": 0,
                "actions": [
                    "initialize CompanyBrain database",
                    *[f"add memories.{name}" for name in _MEMORY_COLUMNS],
                    "create admission_assessments table",
                    "record runtime schema version",
                ],
            }

        with self.base.read_connect() as conn:
            columns = {row[1] for row in conn.execute("PRAGMA table_info(memories)")}
            existing_memories = int(conn.execute("SELECT COUNT(*) FROM memories").fetchone()[0])
            table_exists = bool(
                conn.execute(
                    "SELECT 1 FROM sqlite_master WHERE type='table' AND name='admission_assessments'"
                ).fetchone()
            )
            version_row = conn.execute(
                "SELECT value FROM schema_meta WHERE key='trusted_memory_runtime_schema_version'"
            ).fetchone()

        actions = [
            f"add memories.{name}" for name in _MEMORY_COLUMNS if name not in columns
        ]
        if not table_exists:
            actions.append("create admission_assessments table")
        if not version_row or str(version_row[0]) != str(RUNTIME_SCHEMA_VERSION):
            actions.append("record runtime schema version")
        return {
            "runtime_schema_version": RUNTIME_SCHEMA_VERSION,
            "database_exists": True,
            "existing_memories": existing_memories,
            "actions": actions,
        }

    def migrate(self, *, dry_run: bool = False) -> Dict[str, Any]:
        """Apply the additive trusted-memory schema, or return a dry-run plan."""

        plan = self.migration_plan()
        if dry_run:
            return {**plan, "dry_run": True, "applied": False}

        self.base.initialize()
        with self.base.connect() as conn:
            columns = {row[1] for row in conn.execute("PRAGMA table_info(memories)")}
            for name, definition in _MEMORY_COLUMNS.items():
                if name not in columns:
                    conn.execute(f"ALTER TABLE memories ADD COLUMN {name} {definition}")

            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS admission_assessments (
                    assessment_id TEXT PRIMARY KEY,
                    memory_id TEXT NOT NULL REFERENCES memories(memory_id) ON DELETE CASCADE,
                    proposal_id TEXT NOT NULL,
                    decision TEXT NOT NULL,
                    authority TEXT NOT NULL,
                    risk_tier TEXT NOT NULL,
                    conflict_state TEXT NOT NULL,
                    evidence_strength REAL,
                    reasons_json TEXT NOT NULL,
                    conflicting_memory_ids_json TEXT NOT NULL,
                    recommended_lifecycle TEXT NOT NULL,
                    policy_version TEXT NOT NULL,
                    evaluated_at TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_admission_memory "
                "ON admission_assessments(memory_id, created_at)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_admission_proposal "
                "ON admission_assessments(proposal_id)"
            )
            conn.execute(
                "INSERT INTO schema_meta(key, value) VALUES(?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                ("trusted_memory_runtime_schema_version", str(RUNTIME_SCHEMA_VERSION)),
            )
            conn.commit()

        return {**self.migration_plan(), "dry_run": False, "applied": True}

    def record_assessment(
        self,
        memory_id: str,
        proposal: MemoryProposal,
        assessment: AdmissionAssessment,
    ) -> str:
        """Persist one assessment and annotate its candidate memory atomically."""

        self.migrate()
        assessment_id = "assessment_" + uuid.uuid4().hex[:24]
        created_at = now_iso()
        with self.base.connect() as conn:
            row = conn.execute(
                "SELECT lifecycle FROM memories WHERE memory_id=?",
                (memory_id,),
            ).fetchone()
            if row is None:
                raise ValueError(f"Unknown memory_id: {memory_id}")

            updated = conn.execute(
                """
                UPDATE memories
                   SET authority=?, risk_tier=?, subject=?, predicate=?, object_value=?,
                       admission_decision=?, admission_policy_version=?, updated_at=?
                 WHERE memory_id=?
                """,
                (
                    assessment.authority.value,
                    assessment.risk_tier.value,
                    proposal.subject,
                    proposal.predicate,
                    proposal.object_value,
                    assessment.decision.value,
                    assessment.policy_version,
                    created_at,
                    memory_id,
                ),
            )
            if updated.rowcount != 1:
                raise RuntimeError(f"Failed to annotate memory {memory_id}")

            conn.execute(
                """
                INSERT INTO admission_assessments(
                    assessment_id, memory_id, proposal_id, decision, authority,
                    risk_tier, conflict_state, evidence_strength, reasons_json,
                    conflicting_memory_ids_json, recommended_lifecycle,
                    policy_version, evaluated_at, created_at
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    assessment_id,
                    memory_id,
                    assessment.proposal_id,
                    assessment.decision.value,
                    assessment.authority.value,
                    assessment.risk_tier.value,
                    assessment.conflict_state.value,
                    assessment.evidence_strength,
                    json.dumps(assessment.reasons, ensure_ascii=False),
                    json.dumps(assessment.conflicting_memory_ids, ensure_ascii=False),
                    assessment.recommended_lifecycle,
                    assessment.policy_version,
                    assessment.evaluated_at,
                    created_at,
                ),
            )
            conn.commit()
        return assessment_id

    def _has_runtime_table(self) -> bool:
        if not self.db_path.exists():
            return False
        with self.base.read_connect() as conn:
            return bool(
                conn.execute(
                    "SELECT 1 FROM sqlite_master WHERE type='table' AND name='admission_assessments'"
                ).fetchone()
            )

    def list_assessments(self, memory_id: str) -> List[Dict[str, Any]]:
        """Return admission history without initializing or migrating storage."""

        if not self._has_runtime_table():
            return []
        with self.base.read_connect() as conn:
            rows = conn.execute(
                "SELECT * FROM admission_assessments WHERE memory_id=? "
                "ORDER BY created_at, assessment_id",
                (memory_id,),
            ).fetchall()
        result: List[Dict[str, Any]] = []
        for row in rows:
            item = dict(row)
            item["reasons"] = json.loads(item.pop("reasons_json") or "[]")
            item["conflicting_memory_ids"] = json.loads(
                item.pop("conflicting_memory_ids_json") or "[]"
            )
            result.append(item)
        return result

    def runtime_metadata(self, memory_id: str) -> Dict[str, Any]:
        """Read runtime annotations without any schema or storage side effects."""

        if not self.db_path.exists():
            raise FileNotFoundError(f"Company brain is not initialized: {self.db_path}")
        with self.base.read_connect() as conn:
            columns = {row[1] for row in conn.execute("PRAGMA table_info(memories)")}
            if not set(_MEMORY_COLUMNS).issubset(columns):
                raise RuntimeError("Trusted Memory Runtime schema is not initialized")
            row = conn.execute(
                """
                SELECT authority, risk_tier, subject, predicate, object_value,
                       admission_decision, admission_policy_version
                  FROM memories WHERE memory_id=?
                """,
                (memory_id,),
            ).fetchone()
        if row is None:
            raise ValueError(f"Unknown memory_id: {memory_id}")
        return dict(row)
