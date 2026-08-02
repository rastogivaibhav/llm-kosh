"""Typed contracts for the canonical company-brain layer."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional


MEMORY_TYPES = {
    "fact", "decision", "preference", "constraint", "task", "outcome",
    "procedure", "risk", "goal", "metric", "hypothesis", "correction",
    "question", "incident",
}
STORAGE_MODES = {"reference", "snapshot", "managed"}
ARTIFACT_TYPES = {
    "screenshot", "image", "document", "pdf", "worksheet", "csv",
    "html", "web_read", "presentation", "email", "chat", "transcript",
    "audio", "video", "source_code", "structured_data", "plain_text",
    "binary",
}
AVAILABILITY_STATES = {"available", "changed", "moved", "unavailable", "forbidden", "invalid"}
EVENT_TYPES = {
    "message", "tool_call", "tool_result", "file_change", "commit",
    "ticket_change", "document_change", "handoff", "checkpoint", "system",
    "other",
}
SESSION_STATUSES = {"active", "completed", "partial", "abandoned", "blocked"}
EPISODE_STATUSES = {"completed", "partial", "abandoned", "blocked"}
LIFECYCLES = {
    "candidate", "reviewed", "verified", "active", "stale", "superseded",
    "retracted", "rejected", "quarantined",
}
CLASSIFICATIONS = ("public", "internal", "confidential", "restricted")
CLASSIFICATION_RANK = {name: rank for rank, name in enumerate(CLASSIFICATIONS)}
SUPPORT_TYPES = {"direct", "corroborating", "contradicting", "context"}

_NON_SEMANTIC_TITLE = re.compile(
    r"^(?:\d+|[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}|"
    r"rollout[-_].*|agent[-_][0-9a-f]+)$",
    re.IGNORECASE,
)


def _classification(value: str) -> str:
    normalized = (value or "restricted").strip().lower()
    if normalized not in CLASSIFICATION_RANK:
        raise ValueError(f"Unsupported classification: {value}")
    return normalized


@dataclass(frozen=True)
class AccessPolicy:
    """Small local-edition ABAC policy attached to evidence and memory."""

    allowed_principals: List[str] = field(default_factory=list)
    allowed_groups: List[str] = field(default_factory=list)
    allowed_projects: List[str] = field(default_factory=list)
    denied_principals: List[str] = field(default_factory=list)
    denied_groups: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: Optional[Dict[str, Any]]) -> "AccessPolicy":
        value = value or {}
        return cls(**{
            field_name: list(value.get(field_name) or [])
            for field_name in cls.__dataclass_fields__
        })


@dataclass(frozen=True)
class Principal:
    principal_id: str
    tenant_id: str = "local"
    groups: List[str] = field(default_factory=list)
    projects: List[str] = field(default_factory=list)
    clearance: str = "restricted"

    def __post_init__(self) -> None:
        if not self.principal_id.strip():
            raise ValueError("principal_id is required")
        object.__setattr__(self, "clearance", _classification(self.clearance))


@dataclass(frozen=True)
class EvidenceInput:
    source_type: str
    source_locator: str
    source_native_id: str
    content: Optional[bytes] = None
    mime_type: str = "text/plain"
    storage_mode: str = "managed"
    artifact_type: str = "plain_text"
    tenant_id: str = "local"
    observed_at: str = ""
    source_modified_at: str = ""
    classification: str = "restricted"
    access_policy: AccessPolicy = field(default_factory=AccessPolicy)
    retention_policy_id: str = ""
    ingestion_run_id: str = ""
    supersedes_evidence_id: str = ""
    parser: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.source_type.strip():
            raise ValueError("source_type is required")
        if not self.source_native_id.strip():
            raise ValueError("source_native_id is required")
        storage_mode = self.storage_mode.strip().lower()
        artifact_type = self.artifact_type.strip().lower()
        if storage_mode not in STORAGE_MODES:
            raise ValueError(f"Unsupported storage mode: {self.storage_mode}")
        if artifact_type not in ARTIFACT_TYPES:
            raise ValueError(f"Unsupported artifact type: {self.artifact_type}")
        if storage_mode == "reference" and self.content is not None:
            raise ValueError("reference evidence must not include copied content")
        if storage_mode in {"snapshot", "managed"} and not isinstance(self.content, bytes):
            raise TypeError(f"{storage_mode} evidence content must be bytes")
        object.__setattr__(self, "storage_mode", storage_mode)
        object.__setattr__(self, "artifact_type", artifact_type)
        object.__setattr__(self, "classification", _classification(self.classification))


@dataclass(frozen=True)
class EvidenceSegmentInput:
    evidence_id: str
    native_locator: Dict[str, Any]
    text: str = ""
    extractor: Dict[str, Any] = field(default_factory=dict)
    confidence: float = 1.0

    def __post_init__(self) -> None:
        if not self.evidence_id.strip():
            raise ValueError("evidence_id is required")
        if not self.native_locator:
            raise ValueError("native_locator is required")
        if len(self.text) > 32_000:
            raise ValueError("segment text must not exceed 32,000 characters")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("segment confidence must be between 0 and 1")


@dataclass(frozen=True)
class NormalizedEventInput:
    source_type: str
    source_native_id: str
    session_native_id: str
    evidence_id: str
    native_locator: Dict[str, Any]
    summary: str
    tenant_id: str = "local"
    segment_id: str = ""
    event_type: str = "other"
    actor_type: str = "agent"
    actor_id: str = ""
    role: str = ""
    occurred_at: str = ""
    project_candidates: List[str] = field(default_factory=list)
    entities: List[Dict[str, Any]] = field(default_factory=list)
    classification: str = "restricted"
    access_policy: AccessPolicy = field(default_factory=AccessPolicy)
    ingestion_run_id: str = ""

    def __post_init__(self) -> None:
        if not self.source_type.strip() or not self.source_native_id.strip():
            raise ValueError("event source_type and source_native_id are required")
        if not self.session_native_id.strip() or not self.evidence_id.strip():
            raise ValueError("event session_native_id and evidence_id are required")
        event_type = self.event_type.strip().lower()
        if event_type not in EVENT_TYPES:
            raise ValueError(f"Unsupported event type: {self.event_type}")
        summary = " ".join(self.summary.split())
        if len(summary) > 4_000:
            raise ValueError("event summary must not exceed 4,000 characters")
        object.__setattr__(self, "event_type", event_type)
        object.__setattr__(self, "summary", summary)
        object.__setattr__(self, "classification", _classification(self.classification))


@dataclass(frozen=True)
class SessionInput:
    source_type: str
    source_native_id: str
    evidence_ids: List[str]
    tenant_id: str = "local"
    title: str = ""
    project_id: str = ""
    participants: List[str] = field(default_factory=list)
    started_at: str = ""
    ended_at: str = ""
    status: str = "partial"
    event_count: int = 0
    classification: str = "restricted"
    access_policy: AccessPolicy = field(default_factory=AccessPolicy)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.source_type.strip() or not self.source_native_id.strip():
            raise ValueError("session source identity is required")
        status = self.status.strip().lower()
        if status not in SESSION_STATUSES:
            raise ValueError(f"Unsupported session status: {self.status}")
        if self.event_count < 0:
            raise ValueError("event_count must be non-negative")
        object.__setattr__(self, "status", status)
        object.__setattr__(self, "classification", _classification(self.classification))


@dataclass(frozen=True)
class EpisodeInput:
    title: str
    goal: str
    session_ids: List[str]
    evidence_ids: List[str]
    event_ids: List[str]
    tenant_id: str = "local"
    project_id: str = ""
    participants: List[str] = field(default_factory=list)
    started_at: str = ""
    ended_at: str = ""
    status: str = "partial"
    outcome_summary: str = ""
    phase_summary: Dict[str, Any] = field(default_factory=dict)
    boundary_signals: List[str] = field(default_factory=list)
    confidence: float = 0.5
    classification: str = "restricted"
    access_policy: AccessPolicy = field(default_factory=AccessPolicy)
    extraction_run_id: str = ""
    source_native_id: str = ""

    def __post_init__(self) -> None:
        title = self.title.strip()
        goal = self.goal.strip()
        status = self.status.strip().lower()
        if not title or _NON_SEMANTIC_TITLE.fullmatch(title):
            raise ValueError("Episode title must be semantic")
        if not goal:
            raise ValueError("Episode goal is required")
        if not self.session_ids or not self.evidence_ids or not self.event_ids:
            raise ValueError("Episode requires sessions, evidence, and events")
        if status not in EPISODE_STATUSES:
            raise ValueError(f"Unsupported episode status: {self.status}")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("episode confidence must be between 0 and 1")
        object.__setattr__(self, "title", title[:180])
        object.__setattr__(self, "goal", goal[:2_000])
        object.__setattr__(self, "status", status)
        object.__setattr__(self, "classification", _classification(self.classification))


@dataclass(frozen=True)
class EvidenceReference:
    evidence_id: str
    segment_id: str = ""
    locator: str = ""
    support: str = "direct"
    quote: str = ""

    def __post_init__(self) -> None:
        if not self.evidence_id.strip():
            raise ValueError("evidence_id is required")
        if self.support not in SUPPORT_TYPES:
            raise ValueError(f"Unsupported evidence support type: {self.support}")
        if len(self.quote) > 2_000:
            raise ValueError("Evidence quote must not exceed 2,000 characters")


@dataclass(frozen=True)
class MemoryInput:
    memory_type: str
    title: str
    statement: str
    evidence: List[EvidenceReference]
    tenant_id: str = "local"
    rationale: str = ""
    project_id: str = ""
    entity_ids: List[str] = field(default_factory=list)
    owner_ids: List[str] = field(default_factory=list)
    lifecycle: str = "candidate"
    confidence: float = 0.5
    importance: float = 0.5
    valid_from: str = ""
    valid_to: str = ""
    observed_at: str = ""
    supersedes: List[str] = field(default_factory=list)
    classification: str = "restricted"
    access_policy: AccessPolicy = field(default_factory=AccessPolicy)
    extractor: Dict[str, Any] = field(default_factory=dict)
    source_native_id: str = ""

    def __post_init__(self) -> None:
        memory_type = self.memory_type.strip().lower()
        lifecycle = self.lifecycle.strip().lower()
        title = self.title.strip()
        statement = self.statement.strip()
        if memory_type not in MEMORY_TYPES:
            raise ValueError(f"Unsupported memory type: {self.memory_type}")
        if lifecycle not in LIFECYCLES:
            raise ValueError(f"Unsupported lifecycle: {self.lifecycle}")
        if not title or _NON_SEMANTIC_TITLE.fullmatch(title):
            raise ValueError("Memory title must be semantic, not a number, UUID, agent ID, or rollout ID")
        if len(title) > 180:
            raise ValueError("Memory title must not exceed 180 characters")
        if len(statement) < 10 or len(statement) > 4_000:
            raise ValueError("Memory statement must contain 10 to 4,000 characters")
        if len(self.rationale) > 8_000:
            raise ValueError("Memory rationale must not exceed 8,000 characters")
        if not self.evidence:
            raise ValueError("At least one evidence reference is required")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be between 0 and 1")
        if not 0.0 <= self.importance <= 1.0:
            raise ValueError("importance must be between 0 and 1")
        object.__setattr__(self, "memory_type", memory_type)
        object.__setattr__(self, "lifecycle", lifecycle)
        object.__setattr__(self, "title", title)
        object.__setattr__(self, "statement", statement)
        object.__setattr__(self, "classification", _classification(self.classification))


@dataclass(frozen=True)
class ContextRequest:
    task: str
    principal: Principal
    project_id: str = ""
    memory_types: List[str] = field(default_factory=list)
    as_of: str = ""
    token_budget: int = 8_000
    limit: int = 40

    def __post_init__(self) -> None:
        if not self.task.strip():
            raise ValueError("task is required")
        if not 512 <= self.token_budget <= 100_000:
            raise ValueError("token_budget must be between 512 and 100,000")
        invalid = set(self.memory_types) - MEMORY_TYPES
        if invalid:
            raise ValueError(f"Unsupported memory types: {', '.join(sorted(invalid))}")
