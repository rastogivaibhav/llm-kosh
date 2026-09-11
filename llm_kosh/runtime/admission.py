"""Deterministic Trusted Memory Runtime admission engine.

The engine is intentionally pure: it evaluates a proposal against explicit
policy, evidence signals, and conflict signals. It does not write memory,
change lifecycle state, call a model, or infer trust from prompt content.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import List, Optional

from llm_kosh.core.utils import now_iso

from .models import (
    AdmissionAssessment,
    AdmissionDecision,
    Authority,
    ConflictState,
    MemoryProposal,
    RiskTier,
)
from .policy import AdmissionPolicy


@dataclass(frozen=True)
class EvidenceSignals:
    """Observed evidence properties supplied by a storage/evidence adapter."""

    total: int
    available: int
    direct: int = 0
    corroborating: int = 0
    contradicting: int = 0
    changed: int = 0

    def __post_init__(self) -> None:
        values = {
            "total": self.total,
            "available": self.available,
            "direct": self.direct,
            "corroborating": self.corroborating,
            "contradicting": self.contradicting,
            "changed": self.changed,
        }
        if any(value < 0 for value in values.values()):
            raise ValueError("evidence signal counts must be non-negative")
        if self.available > self.total:
            raise ValueError("available evidence cannot exceed total evidence")
        if self.direct > self.total or self.corroborating > self.total:
            raise ValueError("evidence support counts cannot exceed total evidence")
        if self.contradicting > self.total or self.changed > self.total:
            raise ValueError("evidence conflict counts cannot exceed total evidence")

    @property
    def all_available(self) -> bool:
        return self.total > 0 and self.available == self.total and self.changed == 0

    def strength(self) -> Optional[float]:
        """Return a reproducible support score, or None when evidence is absent.

        This is not model confidence. It is only a bounded summary of evidence
        availability/support signals used for admission policy and explanation.
        """

        if self.total <= 0:
            return None
        availability = self.available / self.total
        direct = self.direct / self.total
        corroboration = min(self.corroborating, 2) / 2.0
        contradiction = self.contradicting / self.total
        changed = self.changed / self.total
        score = (
            0.45 * availability
            + 0.35 * direct
            + 0.20 * corroboration
            - 0.45 * contradiction
            - 0.35 * changed
        )
        return round(max(0.0, min(1.0, score)), 3)


@dataclass(frozen=True)
class ConflictSignals:
    state: ConflictState = ConflictState.NONE
    memory_ids: List[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "memory_ids",
            [item.strip() for item in self.memory_ids if item and item.strip()],
        )


_LOW_RISK_TYPES = {"preference", "question"}
_HIGH_RISK_TYPES = {"constraint", "procedure", "risk", "correction", "incident"}
_CRITICAL_TERMS = (
    "credential",
    "secret",
    "api key",
    "production delete",
    "delete production",
    "disable mfa",
    "without mfa",
    "authentication disabled",
    "authorization disabled",
    "financial transfer",
    "wire transfer",
    "legal approval",
    "compliance exemption",
)


def infer_risk_tier(proposal: MemoryProposal) -> RiskTier:
    """Classify consequence-of-error risk using deterministic local rules.

    A valid explicit ``metadata['risk_tier']`` wins. Otherwise critical risk is
    reserved for a small set of high-consequence phrases, followed by a
    memory-type baseline. This intentionally prefers review over cleverness.
    """

    explicit = str(proposal.metadata.get("risk_tier") or "").strip().lower()
    if explicit:
        try:
            return RiskTier(explicit)
        except ValueError as exc:
            allowed = ", ".join(item.value for item in RiskTier)
            raise ValueError(f"Unsupported risk_tier {explicit!r}; expected: {allowed}") from exc

    text = f"{proposal.title} {proposal.statement}".lower()
    if any(term in text for term in _CRITICAL_TERMS):
        return RiskTier.CRITICAL
    if proposal.memory_type in _LOW_RISK_TYPES:
        return RiskTier.LOW
    if proposal.memory_type in _HIGH_RISK_TYPES:
        return RiskTier.HIGH
    return RiskTier.MEDIUM


def proposal_id_for(proposal: MemoryProposal) -> str:
    """Create a stable content-derived ID for one normalized proposal."""

    canonical = json.dumps(
        proposal.to_dict(), sort_keys=True, ensure_ascii=False, separators=(",", ":")
    )
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:24]
    return f"proposal_{digest}"


def _more_conservative(
    current: AdmissionDecision, minimum: AdmissionDecision
) -> AdmissionDecision:
    order = {
        AdmissionDecision.ADMIT: 0,
        AdmissionDecision.REVIEW: 1,
        AdmissionDecision.QUARANTINE: 2,
        AdmissionDecision.REJECT: 3,
    }
    return minimum if order[minimum] > order[current] else current


class AdmissionEngine:
    """Evaluate memory proposals without mutating storage."""

    def __init__(self, policy: Optional[AdmissionPolicy] = None):
        self.policy = policy or AdmissionPolicy()

    def assess(
        self,
        proposal: MemoryProposal,
        *,
        evidence: Optional[EvidenceSignals] = None,
        conflicts: Optional[ConflictSignals] = None,
        evaluated_at: str = "",
    ) -> AdmissionAssessment:
        authority = self.policy.authority_for(proposal.source_type)
        risk = infer_risk_tier(proposal)
        conflicts = conflicts or ConflictSignals()
        reasons: List[str] = [
            f"source '{proposal.source_type}' maps to {authority.value} authority",
            f"memory type/rules classify consequence risk as {risk.value}",
        ]

        decision = self.policy.decision_for(authority, risk)
        strength = evidence.strength() if evidence is not None else None

        if evidence is None:
            reasons.append("evidence support signals were not supplied; no strength score inferred")
        else:
            reasons.append(
                f"evidence availability {evidence.available}/{evidence.total}; support score {strength}"
            )
            if evidence.total == 0 or evidence.available == 0:
                decision = _more_conservative(decision, AdmissionDecision.QUARANTINE)
                reasons.append("no available evidence; quarantine required")
            elif not evidence.all_available:
                decision = _more_conservative(decision, AdmissionDecision.REVIEW)
                reasons.append("some evidence is unavailable, changed, or unverifiable")
            if evidence.contradicting:
                decision = _more_conservative(decision, AdmissionDecision.REVIEW)
                reasons.append("evidence set contains contradicting references")
            if strength is not None and strength < 0.35:
                decision = _more_conservative(decision, AdmissionDecision.QUARANTINE)
                reasons.append("evidence support score is below the quarantine threshold")

        if conflicts.state is ConflictState.POTENTIAL_CONTRADICTION:
            decision = _more_conservative(decision, AdmissionDecision.REVIEW)
            reasons.append("potential contradiction requires review")
        elif conflicts.state is ConflictState.DIRECT_CONTRADICTION:
            minimum = (
                AdmissionDecision.REVIEW
                if authority is Authority.AUTHORITATIVE
                else AdmissionDecision.QUARANTINE
            )
            decision = _more_conservative(decision, minimum)
            reasons.append("direct contradiction prevents silent replacement")
        elif conflicts.state is ConflictState.SUPERSESSION:
            decision = _more_conservative(decision, AdmissionDecision.REVIEW)
            reasons.append("supersession requires an explicit lifecycle transition")
        elif conflicts.state is ConflictState.DUPLICATE:
            decision = _more_conservative(decision, AdmissionDecision.REVIEW)
            reasons.append("duplicate candidate should be consolidated rather than re-admitted")

        lifecycle = {
            AdmissionDecision.ADMIT: "verified",
            AdmissionDecision.REVIEW: "candidate",
            AdmissionDecision.QUARANTINE: "quarantined",
            AdmissionDecision.REJECT: "rejected",
        }[decision]

        return AdmissionAssessment(
            proposal_id=proposal_id_for(proposal),
            decision=decision,
            authority=authority,
            risk_tier=risk,
            conflict_state=conflicts.state,
            evidence_strength=strength,
            reasons=reasons,
            conflicting_memory_ids=list(conflicts.memory_ids),
            recommended_lifecycle=lifecycle,
            policy_version=self.policy.version,
            evaluated_at=evaluated_at or now_iso(),
        )
