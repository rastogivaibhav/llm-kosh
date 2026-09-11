"""Typed, dependency-light contracts for the Trusted Memory Runtime."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from llm_kosh.company_brain.models import CLASSIFICATION_RANK, MEMORY_TYPES


class _ValueEnum(str, Enum):
    def __str__(self) -> str:
        return self.value


class AdmissionDecision(_ValueEnum):
    ADMIT = "admit"
    REVIEW = "review"
    QUARANTINE = "quarantine"
    REJECT = "reject"


class Authority(_ValueEnum):
    AUTHORITATIVE = "authoritative"
    TRUSTED = "trusted"
    CONTEXTUAL = "contextual"
    UNTRUSTED = "untrusted"
    UNKNOWN = "unknown"


class RiskTier(_ValueEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ConflictState(_ValueEnum):
    NONE = "none"
    DUPLICATE = "duplicate"
    UPDATE = "update"
    POTENTIAL_CONTRADICTION = "potential_contradiction"
    DIRECT_CONTRADICTION = "direct_contradiction"
    SUPERSESSION = "supersession"


class RetrievalMode(_ValueEnum):
    NORMAL = "normal"
    STRICT = "strict"
    HISTORICAL = "historical"
    CANDIDATE = "candidate"


class MemorySource(_ValueEnum):
    USER_DIRECT = "user_direct"
    LOCAL_FILE = "local_file"
    AGENT_OBSERVATION = "agent_observation"
    TOOL_RESULT = "tool_result"
    REPOSITORY = "repository"
    SESSION_TRANSCRIPT = "session_transcript"
    IMPORTED_DOCUMENT = "imported_document"
    WEB_CONTENT = "web_content"
    AGENT_INFERENCE = "agent_inference"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class MemoryProposal:
    """A non-authoritative request to turn evidence into durable memory.

    A proposal is never equivalent to admitted memory. It names the evidence and
    source context needed by the admission engine to make that decision later.
    """

    memory_type: str
    title: str
    statement: str
    evidence_ids: List[str]
    source_type: str
    project_id: str = ""
    observed_at: str = ""
    confidence: Optional[float] = None
    classification: str = "restricted"
    principal_id: str = "local-user"
    source_native_id: str = ""
    subject: str = ""
    predicate: str = ""
    object_value: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        memory_type = self.memory_type.strip().lower()
        title = self.title.strip()
        statement = self.statement.strip()
        source_type = self.source_type.strip().lower() or MemorySource.UNKNOWN.value
        classification = self.classification.strip().lower()

        if memory_type not in MEMORY_TYPES:
            raise ValueError(f"Unsupported memory type: {self.memory_type}")
        if not title:
            raise ValueError("title is required")
        if len(title) > 180:
            raise ValueError("title must not exceed 180 characters")
        if len(statement) < 10 or len(statement) > 4_000:
            raise ValueError("statement must contain 10 to 4,000 characters")
        evidence_ids = [item.strip() for item in self.evidence_ids if item and item.strip()]
        if not evidence_ids:
            raise ValueError("at least one evidence_id is required")
        if classification not in CLASSIFICATION_RANK:
            raise ValueError(f"Unsupported classification: {self.classification}")
        if self.confidence is not None and not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be between 0 and 1 when supplied")
        if not self.principal_id.strip():
            raise ValueError("principal_id is required")

        structured = [self.subject.strip(), self.predicate.strip(), self.object_value.strip()]
        if any(structured) and not all(structured):
            raise ValueError("subject, predicate, and object_value must be supplied together")

        object.__setattr__(self, "memory_type", memory_type)
        object.__setattr__(self, "title", title)
        object.__setattr__(self, "statement", statement)
        object.__setattr__(self, "evidence_ids", evidence_ids)
        object.__setattr__(self, "source_type", source_type)
        object.__setattr__(self, "classification", classification)
        object.__setattr__(self, "principal_id", self.principal_id.strip())
        object.__setattr__(self, "subject", structured[0])
        object.__setattr__(self, "predicate", structured[1])
        object.__setattr__(self, "object_value", structured[2])

    @property
    def has_structured_claim(self) -> bool:
        return bool(self.subject and self.predicate and self.object_value)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "memory_type": self.memory_type,
            "title": self.title,
            "statement": self.statement,
            "evidence_ids": list(self.evidence_ids),
            "source_type": self.source_type,
            "project_id": self.project_id,
            "observed_at": self.observed_at,
            "confidence": self.confidence,
            "classification": self.classification,
            "principal_id": self.principal_id,
            "source_native_id": self.source_native_id,
            "subject": self.subject,
            "predicate": self.predicate,
            "object_value": self.object_value,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class AdmissionAssessment:
    """Explainable output of one deterministic admission evaluation."""

    proposal_id: str
    decision: AdmissionDecision
    authority: Authority
    risk_tier: RiskTier
    conflict_state: ConflictState = ConflictState.NONE
    evidence_strength: Optional[float] = None
    reasons: List[str] = field(default_factory=list)
    conflicting_memory_ids: List[str] = field(default_factory=list)
    recommended_lifecycle: str = "candidate"
    policy_version: str = "trusted-memory-v1"
    evaluated_at: str = ""

    def __post_init__(self) -> None:
        if not self.proposal_id.strip():
            raise ValueError("proposal_id is required")
        if self.evidence_strength is not None and not 0.0 <= self.evidence_strength <= 1.0:
            raise ValueError("evidence_strength must be between 0 and 1 when supplied")
        if not self.policy_version.strip():
            raise ValueError("policy_version is required")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "proposal_id": self.proposal_id,
            "decision": self.decision.value,
            "authority": self.authority.value,
            "risk_tier": self.risk_tier.value,
            "conflict_state": self.conflict_state.value,
            "evidence_strength": self.evidence_strength,
            "reasons": list(self.reasons),
            "conflicting_memory_ids": list(self.conflicting_memory_ids),
            "recommended_lifecycle": self.recommended_lifecycle,
            "policy_version": self.policy_version,
            "evaluated_at": self.evaluated_at,
        }
