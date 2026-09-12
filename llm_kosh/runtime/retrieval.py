"""Lifecycle-, admission-, and authority-aware retrieval for Trusted Memory Runtime."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence

from llm_kosh.company_brain.models import Principal
from llm_kosh.company_brain.retrieval import search_memories
from llm_kosh.company_brain.store import CompanyBrainStore

from .models import Authority, RetrievalMode
from .persistence import RuntimeStore


_TOKEN_RE = re.compile(r"[a-z0-9][a-z0-9_\-]+", re.IGNORECASE)
_CURRENT_LIFECYCLES = {"reviewed", "verified", "active"}
_STRICT_LIFECYCLES = {"verified", "active"}
_STRICT_AUTHORITIES = {Authority.AUTHORITATIVE.value, Authority.TRUSTED.value}
_BLOCKING_ADMISSION_DECISIONS = {"quarantine", "reject"}


def _tokens(value: str) -> set[str]:
    return {match.group(0).lower() for match in _TOKEN_RE.finditer(value or "")}


def _query_score(query: str, item: Dict[str, Any]) -> float:
    query_tokens = _tokens(query)
    if not query_tokens:
        return 1.0
    document_tokens = _tokens(
        " ".join(
            (
                str(item.get("title", "")),
                str(item.get("statement", "")),
                str(item.get("rationale", "")),
                str(item.get("project_id", "")),
            )
        )
    )
    if not document_tokens:
        return 0.0
    return len(query_tokens & document_tokens) / len(query_tokens)


class TrustedRetrieval:
    """Read-only retrieval gate layered on CompanyBrain authorization.

    CompanyBrain remains responsible for access policy and evidence visibility.
    This layer adds runtime lifecycle/admission/authority semantics and structured
    output. It never migrates storage while serving a read.
    """

    def __init__(self, root: Path):
        self.root = Path(root).expanduser().resolve()
        self.store = CompanyBrainStore(self.root)
        self.runtime = RuntimeStore(self.root)

    def _runtime_metadata(self, memory_id: str) -> Dict[str, Any]:
        try:
            return self.runtime.runtime_metadata(memory_id)
        except (FileNotFoundError, RuntimeError, ValueError):
            return {
                "authority": "",
                "risk_tier": "",
                "subject": "",
                "predicate": "",
                "object_value": "",
                "admission_decision": "",
                "admission_policy_version": "",
            }

    def _enrich(
        self,
        items: Iterable[Dict[str, Any]],
        principal: Principal,
    ) -> List[Dict[str, Any]]:
        rows = [dict(item) for item in items]
        if not rows:
            return []
        evidence = self.store.evidence_for_memories(
            [item["memory_id"] for item in rows], principal
        )
        output: List[Dict[str, Any]] = []
        for item in rows:
            metadata = self._runtime_metadata(item["memory_id"])
            refs = evidence.get(item["memory_id"], [])
            output.append(
                {
                    **item,
                    **metadata,
                    "evidence": refs,
                    "trusted_runtime": bool(metadata.get("authority")),
                }
            )
        return output

    @staticmethod
    def _passes_normal_runtime_gate(item: Dict[str, Any]) -> bool:
        if item.get("lifecycle") not in _CURRENT_LIFECYCLES:
            return False
        if item.get("admission_decision") in _BLOCKING_ADMISSION_DECISIONS:
            return False
        return True

    @staticmethod
    def _passes_strict_runtime_gate(item: Dict[str, Any]) -> bool:
        if item.get("lifecycle") not in _STRICT_LIFECYCLES:
            return False
        if item.get("admission_decision") in _BLOCKING_ADMISSION_DECISIONS:
            return False
        if item.get("authority") not in _STRICT_AUTHORITIES:
            return False
        return bool(item.get("evidence"))

    def _authorized_by_lifecycle(
        self,
        principal: Principal,
        lifecycles: Sequence[str],
        *,
        project_id: str = "",
        memory_types: Optional[Sequence[str]] = None,
        as_of: str = "",
        query: str = "",
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """Enumerate IDs by scope, then authorize each memory before reading it."""

        if not self.store.db_path.exists():
            return []
        clauses = [
            "tenant_id=?",
            "lifecycle IN (" + ",".join("?" for _ in lifecycles) + ")",
        ]
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
        sql = (
            "SELECT memory_id FROM memories WHERE "
            + " AND ".join(clauses)
            + " ORDER BY updated_at DESC LIMIT ?"
        )
        params.append(max(50, limit * 10))
        with self.store.read_connect() as conn:
            ids = [row[0] for row in conn.execute(sql, params).fetchall()]

        authorized: List[Dict[str, Any]] = []
        for memory_id in ids:
            try:
                item = self.store.get_memory(memory_id, principal)
            except (KeyError, PermissionError):
                continue
            score = _query_score(query, item)
            if query.strip() and score <= 0:
                continue
            item = dict(item)
            item["score"] = round(score, 6)
            authorized.append(item)

        authorized.sort(
            key=lambda item: (item.get("score", 0.0), item.get("updated_at", "")),
            reverse=True,
        )
        return authorized[: max(1, limit)]

    def recall(
        self,
        query: str,
        principal: Principal,
        *,
        project_id: str = "",
        memory_types: Optional[Sequence[str]] = None,
        as_of: str = "",
        mode: RetrievalMode | str = RetrievalMode.NORMAL,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """Retrieve memory according to explicit trusted-memory semantics."""

        if isinstance(mode, str):
            mode = RetrievalMode(mode.strip().lower())
        limit = max(1, min(int(limit), 100))

        if mode in {RetrievalMode.NORMAL, RetrievalMode.STRICT}:
            base_results = search_memories(
                self.store,
                query,
                principal,
                project_id=project_id,
                memory_types=memory_types,
                as_of=as_of,
                limit=min(500, max(limit * 5, limit)),
                include_candidates=False,
                include_stale=False,
            )
            results = self._enrich(base_results, principal)
            results = [item for item in results if self._passes_normal_runtime_gate(item)]
            if mode is RetrievalMode.STRICT:
                results = [item for item in results if self._passes_strict_runtime_gate(item)]
            return results[:limit]

        if mode is RetrievalMode.CANDIDATE:
            rows = self._authorized_by_lifecycle(
                principal,
                ("candidate", "quarantined"),
                project_id=project_id,
                memory_types=memory_types,
                as_of=as_of,
                query=query,
                limit=limit,
            )
            return self._enrich(rows, principal)

        rows = self._authorized_by_lifecycle(
            principal,
            ("stale", "superseded", "retracted"),
            project_id=project_id,
            memory_types=memory_types,
            as_of=as_of,
            query=query,
            limit=limit,
        )
        return self._enrich(rows, principal)
