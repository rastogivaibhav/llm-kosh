"""Explicit human review operations for Trusted Memory Runtime.

Review is intentionally separate from proposal admission. Ordinary approval uses
CompanyBrain lifecycle transitions. Supersession is a stronger operation that
updates the replacement and all replaced memories in one SQLite transaction.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from llm_kosh.company_brain.models import Principal
from llm_kosh.company_brain.store import CompanyBrainStore, TRANSITIONS
from llm_kosh.core.utils import now_iso

from .persistence import RuntimeStore


class TrustedMemoryReviewer:
    """Authorized, explicit lifecycle review for governed memory."""

    def __init__(self, root: Path):
        self.root = Path(root).expanduser().resolve()
        self.store = CompanyBrainStore(self.root)
        self.runtime_store = RuntimeStore(self.root)

    def _latest_assessment(self, memory_id: str) -> Dict[str, Any]:
        history = self.runtime_store.list_assessments(memory_id)
        if not history:
            raise ValueError("Memory has no trusted-runtime admission assessment")
        return history[-1]

    def review(
        self,
        memory_id: str,
        principal: Principal,
        *,
        action: str,
        reason: str,
        supersede_ids: Optional[Sequence[str]] = None,
    ) -> Dict[str, Any]:
        """Apply an explicit review action.

        Supported actions are ``approve``, ``quarantine``, ``reject`` and
        ``supersede``. Supersession is never inferred from a generic approval.
        """

        action = action.strip().lower()
        if action not in {"approve", "quarantine", "reject", "supersede"}:
            raise ValueError("action must be approve, quarantine, reject, or supersede")
        if not reason.strip():
            raise ValueError("review reason is required")

        memory = self.store.get_memory(memory_id, principal)
        assessment = self._latest_assessment(memory_id)

        if action == "approve":
            if assessment.get("conflict_state") in {
                "duplicate",
                "update",
                "potential_contradiction",
                "direct_contradiction",
                "supersession",
            }:
                raise ValueError(
                    "Conflicted memory cannot be generically approved; resolve or supersede explicitly"
                )
            return self.store.transition_memory(
                memory_id, "verified", principal, reason=reason.strip()
            )

        if action == "quarantine":
            return self.store.transition_memory(
                memory_id, "quarantined", principal, reason=reason.strip()
            )

        if action == "reject":
            return self.store.transition_memory(
                memory_id, "rejected", principal, reason=reason.strip()
            )

        targets = [str(item).strip() for item in (supersede_ids or []) if str(item).strip()]
        assessed_targets = [
            str(item).strip()
            for item in (assessment.get("conflicting_memory_ids") or [])
            if str(item).strip()
        ]
        conflict_state = str(assessment.get("conflict_state") or "")
        if conflict_state == "supersession" and not targets:
            targets = assessed_targets
        if conflict_state not in {"supersession", "direct_contradiction"}:
            raise ValueError("Memory assessment does not support supersession")
        if not targets:
            raise ValueError("supersede requires at least one assessed target memory")
        if not set(targets).issubset(set(assessed_targets)):
            raise ValueError("supersede target was not identified by the admission assessment")
        if memory["lifecycle"] not in {"candidate", "reviewed"}:
            raise ValueError("only candidate or reviewed memory can replace existing memory")

        return self._atomic_supersede(
            memory_id,
            targets,
            principal,
            reason=reason.strip(),
        )

    def _atomic_supersede(
        self,
        memory_id: str,
        old_ids: Sequence[str],
        principal: Principal,
        *,
        reason: str,
    ) -> Dict[str, Any]:
        """Verify authorization, then atomically promote new + supersede old."""

        # Authorization is checked through the public store API before entering
        # the write transaction. The transaction re-validates tenant/lifecycle.
        self.store.get_memory(memory_id, principal)
        for old_id in old_ids:
            self.store.get_memory(old_id, principal)

        updated_at = now_iso()
        unique_old_ids = list(dict.fromkeys(old_ids))
        with self.store.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            try:
                new_row = conn.execute(
                    "SELECT * FROM memories WHERE memory_id=? AND tenant_id=?",
                    (memory_id, principal.tenant_id),
                ).fetchone()
                if new_row is None:
                    raise ValueError(f"Replacement memory not found: {memory_id}")
                new_lifecycle = str(new_row["lifecycle"])
                if "verified" not in TRANSITIONS.get(new_lifecycle, set()):
                    raise ValueError(
                        f"Invalid replacement transition: {new_lifecycle} -> verified"
                    )

                old_rows: List[Any] = []
                for old_id in unique_old_ids:
                    old = conn.execute(
                        "SELECT * FROM memories WHERE memory_id=? AND tenant_id=?",
                        (old_id, principal.tenant_id),
                    ).fetchone()
                    if old is None:
                        raise ValueError(f"Superseded memory not found: {old_id}")
                    old_lifecycle = str(old["lifecycle"])
                    if "superseded" not in TRANSITIONS.get(old_lifecycle, set()):
                        raise ValueError(
                            f"Invalid supersession transition: {old_lifecycle} -> superseded"
                        )
                    old_rows.append(old)

                conn.execute(
                    "UPDATE memories SET lifecycle='verified', supersedes_json=?, updated_at=? "
                    "WHERE memory_id=?",
                    (
                        json.dumps(unique_old_ids, sort_keys=True, separators=(",", ":")),
                        updated_at,
                        memory_id,
                    ),
                )
                self.store._record_lifecycle_event(
                    conn,
                    principal.tenant_id,
                    memory_id,
                    new_lifecycle,
                    "verified",
                    reason,
                    principal.principal_id,
                    updated_at,
                )

                for old in old_rows:
                    old_id = str(old["memory_id"])
                    old_lifecycle = str(old["lifecycle"])
                    conn.execute(
                        "UPDATE memories SET lifecycle='superseded', updated_at=? WHERE memory_id=?",
                        (updated_at, old_id),
                    )
                    self.store._record_lifecycle_event(
                        conn,
                        principal.tenant_id,
                        old_id,
                        old_lifecycle,
                        "superseded",
                        f"{reason}; superseded by {memory_id}",
                        principal.principal_id,
                        updated_at,
                    )
                conn.commit()
            except Exception:
                conn.rollback()
                raise

        replacement = self.store.get_memory(memory_id, principal)
        return {
            "memory": replacement,
            "superseded_memory_ids": unique_old_ids,
            "action": "supersede",
        }
