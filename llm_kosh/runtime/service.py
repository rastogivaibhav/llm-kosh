"""High-level Trusted Memory Runtime facade.

The facade turns an evidence-backed proposal into a governed candidate, records
its deterministic admission assessment, and applies only single-memory lifecycle
decisions. Conflicting/superseding proposals never mutate existing memories
implicitly.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from llm_kosh.company_brain.models import (
    CLASSIFICATION_RANK,
    AccessPolicy,
    EvidenceReference,
    MemoryInput,
    Principal,
)
from llm_kosh.company_brain.store import CompanyBrainStore

from .admission import AdmissionEngine, EvidenceSignals, proposal_id_for
from .conflicts import ConflictCandidate, ConflictDetector
from .models import AdmissionDecision, MemoryProposal, RetrievalMode
from .persistence import RuntimeStore
from .policy import AdmissionPolicy, load_admission_policy
from .retrieval import TrustedRetrieval


_CURRENT_CONFLICT_LIFECYCLES = ("reviewed", "verified", "active", "stale")


class TrustedMemoryRuntime:
    """Small policy-first API for proposing, recalling and explaining memory."""

    def __init__(self, root: Path, policy: Optional[AdmissionPolicy] = None):
        self.root = Path(root).expanduser().resolve()
        self.store = CompanyBrainStore(self.root)
        self.runtime_store = RuntimeStore(self.root)
        self.policy = policy or load_admission_policy(self.root)
        self.admission = AdmissionEngine(self.policy)
        self.conflicts = ConflictDetector()
        self.retrieval = TrustedRetrieval(self.root)

    def _inspect_evidence(
        self,
        proposal: MemoryProposal,
        principal: Principal,
    ) -> tuple[List[Dict[str, Any]], EvidenceSignals]:
        inspections: List[Dict[str, Any]] = []
        available = 0
        changed = 0
        for evidence_id in proposal.evidence_ids:
            inspection = self.store.inspect_evidence(evidence_id, principal, strong=False)
            if inspection["tenant_id"] != principal.tenant_id:
                raise PermissionError("Evidence tenant does not match the proposing principal")
            status = str((inspection.get("availability") or {}).get("status") or "unavailable")
            if status == "available":
                available += 1
            elif status == "changed":
                changed += 1
            inspections.append(inspection)
        return inspections, EvidenceSignals(
            total=len(inspections),
            available=available,
            changed=changed,
        )

    def _conflict_candidates(
        self,
        proposal: MemoryProposal,
        principal: Principal,
    ) -> List[ConflictCandidate]:
        if not self.store.db_path.exists():
            return []
        clauses = [
            "tenant_id=?",
            "lifecycle IN (" + ",".join("?" for _ in _CURRENT_CONFLICT_LIFECYCLES) + ")",
        ]
        params: List[Any] = [principal.tenant_id, *_CURRENT_CONFLICT_LIFECYCLES]
        if proposal.project_id:
            clauses.append("project_id=?")
            params.append(proposal.project_id)
        if proposal.memory_type != "correction":
            clauses.append("memory_type=?")
            params.append(proposal.memory_type)
        with self.store.read_connect() as conn:
            ids = [
                row[0]
                for row in conn.execute(
                    "SELECT memory_id FROM memories WHERE " + " AND ".join(clauses),
                    params,
                ).fetchall()
            ]

        candidates: List[ConflictCandidate] = []
        for memory_id in ids:
            try:
                item = self.store.get_memory(memory_id, principal)
            except (KeyError, PermissionError):
                continue
            candidates.append(
                ConflictCandidate(
                    memory_id=item["memory_id"],
                    memory_type=item["memory_type"],
                    title=item["title"],
                    statement=item["statement"],
                    project_id=item.get("project_id", ""),
                    lifecycle=item.get("lifecycle", "active"),
                    subject=item.get("subject", ""),
                    predicate=item.get("predicate", ""),
                    object_value=item.get("object_value", ""),
                    valid_from=item.get("valid_from", ""),
                    valid_to=item.get("valid_to", ""),
                )
            )
        return candidates

    @staticmethod
    def _effective_classification(
        proposal: MemoryProposal,
        inspections: Sequence[Dict[str, Any]],
    ) -> str:
        values = [proposal.classification]
        values.extend(str(item.get("classification") or "restricted") for item in inspections)
        return max(values, key=lambda value: CLASSIFICATION_RANK.get(value, 999))

    def _existing_assessed_result(
        self,
        proposal_id: str,
        principal: Principal,
    ) -> Optional[Dict[str, Any]]:
        """Return the previously governed result for an identical proposal."""

        if not self.store.db_path.exists():
            return None
        with self.store.read_connect() as conn:
            row = conn.execute(
                "SELECT memory_id FROM memories WHERE tenant_id=? AND source_native_id=?",
                (principal.tenant_id, proposal_id),
            ).fetchone()
        if row is None:
            return None
        memory_id = str(row[0])
        memory = self.store.get_memory(memory_id, principal)
        history = self.runtime_store.list_assessments(memory_id)
        matching = [item for item in history if item.get("proposal_id") == proposal_id]
        if not matching:
            # A previous attempt may have stopped after storing a fail-closed
            # candidate. Resume assessment rather than inventing prior state.
            return None
        latest = matching[-1]
        return {
            "memory_id": memory_id,
            "proposal_id": proposal_id,
            "decision": latest["decision"],
            "lifecycle": memory["lifecycle"],
            "authority": latest["authority"],
            "risk_tier": latest["risk_tier"],
            "conflict_state": latest["conflict_state"],
            "conflicting_memory_ids": list(latest.get("conflicting_memory_ids") or []),
            "reasons": list(latest.get("reasons") or []),
            "idempotent": True,
        }

    def propose(
        self,
        proposal: MemoryProposal,
        principal: Principal,
    ) -> Dict[str, Any]:
        """Evaluate and persist a proposal without silently replacing old memory.

        The stored row starts as ``candidate``. Assessment is written before any
        automatic lifecycle transition, so interruptions fail closed: an
        incomplete operation can leave a candidate pending but cannot make it
        appear in normal trusted recall.
        """

        if proposal.principal_id != principal.principal_id:
            raise PermissionError("Proposal principal_id must match the authenticated principal")

        proposal_id = proposal_id_for(proposal)
        existing = self._existing_assessed_result(proposal_id, principal)
        if existing is not None:
            return existing

        inspections, evidence_signals = self._inspect_evidence(proposal, principal)
        conflict_signals = self.conflicts.detect(
            proposal,
            self._conflict_candidates(proposal, principal),
        )
        assessment = self.admission.assess(
            proposal,
            evidence=evidence_signals,
            conflicts=conflict_signals,
        )
        references = [
            EvidenceReference(
                evidence_id=item["evidence_id"],
                locator=str(item.get("source_locator") or ""),
                support="context",
            )
            for item in inspections
        ]
        memory_id = self.store.add_memory(
            MemoryInput(
                memory_type=proposal.memory_type,
                title=proposal.title,
                statement=proposal.statement,
                evidence=references,
                tenant_id=principal.tenant_id,
                rationale="Trusted Memory Runtime proposal; authority is governed by admission policy.",
                project_id=proposal.project_id,
                owner_ids=[principal.principal_id],
                lifecycle="candidate",
                confidence=proposal.confidence if proposal.confidence is not None else 0.5,
                importance=0.5,
                observed_at=proposal.observed_at,
                # Deliberately empty. Explicit supersession is a review action;
                # CompanyBrain.add_memory would otherwise mutate old lifecycle now.
                supersedes=[],
                classification=self._effective_classification(proposal, inspections),
                # Fail closed rather than widening the evidence's audience. A
                # later explicit sharing workflow can broaden this deliberately.
                access_policy=AccessPolicy(allowed_principals=[principal.principal_id]),
                extractor={"kind": "trusted_memory_runtime", "policy": assessment.policy_version},
                source_native_id=proposal_id,
            )
        )

        prior = self.runtime_store.list_assessments(memory_id)
        if not any(item.get("proposal_id") == assessment.proposal_id for item in prior):
            self.runtime_store.record_assessment(memory_id, proposal, assessment)

        current = self.store.get_memory(memory_id, principal)
        if current["lifecycle"] == "candidate":
            if assessment.decision is AdmissionDecision.ADMIT:
                self.store.transition_memory(
                    memory_id,
                    "verified",
                    principal,
                    reason="Trusted Memory Runtime auto-admit policy",
                )
            elif assessment.decision is AdmissionDecision.QUARANTINE:
                self.store.transition_memory(
                    memory_id,
                    "quarantined",
                    principal,
                    reason="Trusted Memory Runtime admission quarantine",
                )
            elif assessment.decision is AdmissionDecision.REJECT:
                self.store.transition_memory(
                    memory_id,
                    "rejected",
                    principal,
                    reason="Trusted Memory Runtime admission rejection",
                )

        memory = self.store.get_memory(memory_id, principal)
        return {
            "memory_id": memory_id,
            "proposal_id": assessment.proposal_id,
            "decision": assessment.decision.value,
            "lifecycle": memory["lifecycle"],
            "authority": assessment.authority.value,
            "risk_tier": assessment.risk_tier.value,
            "conflict_state": assessment.conflict_state.value,
            "conflicting_memory_ids": list(assessment.conflicting_memory_ids),
            "reasons": list(assessment.reasons),
            "idempotent": False,
        }

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
        return self.retrieval.recall(
            query,
            principal,
            project_id=project_id,
            memory_types=memory_types,
            as_of=as_of,
            mode=mode,
            limit=limit,
        )

    def explain(self, memory_id: str, principal: Principal) -> Dict[str, Any]:
        """Return authorized memory, evidence and admission history."""

        memory = self.store.get_memory(memory_id, principal)
        try:
            runtime_metadata = self.runtime_store.runtime_metadata(memory_id)
        except RuntimeError:
            runtime_metadata = {}
        return {
            "memory": memory,
            "runtime": runtime_metadata,
            "admission_history": self.runtime_store.list_assessments(memory_id),
        }
