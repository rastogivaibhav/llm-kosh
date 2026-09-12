"""Precision-first conflict detection for trusted memory proposals.

Structured claims receive deterministic comparison. Unstructured text is only
used to raise conservative duplicate/update/potential-conflict signals; it is
never treated as proof of a direct contradiction.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable, List, Sequence, Set

from .admission import ConflictSignals
from .models import ConflictState, MemoryProposal


_CURRENT_LIFECYCLES = {"reviewed", "verified", "active", "stale"}
_TOKEN_RE = re.compile(r"[a-z0-9][a-z0-9_.:/+-]*", re.IGNORECASE)


@dataclass(frozen=True)
class ConflictCandidate:
    memory_id: str
    memory_type: str
    title: str
    statement: str
    project_id: str = ""
    lifecycle: str = "active"
    subject: str = ""
    predicate: str = ""
    object_value: str = ""
    valid_from: str = ""
    valid_to: str = ""

    def __post_init__(self) -> None:
        if not self.memory_id.strip():
            raise ValueError("memory_id is required")
        if not self.title.strip() or not self.statement.strip():
            raise ValueError("candidate title and statement are required")

    @property
    def has_structured_claim(self) -> bool:
        return bool(self.subject and self.predicate and self.object_value)


def _tokens(value: str) -> Set[str]:
    return {match.group(0).lower() for match in _TOKEN_RE.finditer(value or "")}


def _jaccard(left: str, right: str) -> float:
    a, b = _tokens(left), _tokens(right)
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def _same_scope(proposal: MemoryProposal, candidate: ConflictCandidate) -> bool:
    if candidate.lifecycle not in _CURRENT_LIFECYCLES:
        return False
    if proposal.memory_type != candidate.memory_type and proposal.memory_type != "correction":
        return False
    if proposal.project_id and candidate.project_id and proposal.project_id != candidate.project_id:
        return False
    return True


def _normalize_supersedes(value: object) -> Set[str]:
    """Normalize explicit supersession metadata without interpreting prose.

    A single memory ID is accepted as a convenience, but arbitrary mappings or
    scalar values are ignored rather than iterated character-by-character.
    """

    if isinstance(value, str):
        item = value.strip()
        return {item} if item else set()
    if not isinstance(value, (list, tuple, set, frozenset)):
        return set()
    return {str(item).strip() for item in value if str(item).strip()}


def _state_rank(state: ConflictState) -> int:
    return {
        ConflictState.NONE: 0,
        ConflictState.UPDATE: 1,
        ConflictState.DUPLICATE: 2,
        ConflictState.POTENTIAL_CONTRADICTION: 3,
        ConflictState.SUPERSESSION: 4,
        ConflictState.DIRECT_CONTRADICTION: 5,
    }[state]


class ConflictDetector:
    """Detect the strongest relevant conflict without mutating memory."""

    def classify(self, proposal: MemoryProposal, candidate: ConflictCandidate) -> ConflictState:
        if not _same_scope(proposal, candidate):
            return ConflictState.NONE

        explicit_supersedes = _normalize_supersedes(proposal.metadata.get("supersedes", []))
        if candidate.memory_id in explicit_supersedes:
            return ConflictState.SUPERSESSION

        if proposal.has_structured_claim and candidate.has_structured_claim:
            same_subject = proposal.subject.casefold() == candidate.subject.casefold()
            same_predicate = proposal.predicate.casefold() == candidate.predicate.casefold()
            if same_subject and same_predicate:
                if proposal.object_value.casefold() == candidate.object_value.casefold():
                    if _jaccard(proposal.statement, candidate.statement) >= 0.80:
                        return ConflictState.DUPLICATE
                    return ConflictState.UPDATE
                return ConflictState.DIRECT_CONTRADICTION
            return ConflictState.NONE

        title_similarity = _jaccard(proposal.title, candidate.title)
        statement_similarity = _jaccard(proposal.statement, candidate.statement)

        if title_similarity >= 0.90 and statement_similarity >= 0.82:
            return ConflictState.DUPLICATE
        if title_similarity >= 0.72 and statement_similarity >= 0.50:
            return ConflictState.UPDATE
        if title_similarity >= 0.72 and statement_similarity < 0.35:
            return ConflictState.POTENTIAL_CONTRADICTION
        return ConflictState.NONE

    def detect(
        self,
        proposal: MemoryProposal,
        candidates: Sequence[ConflictCandidate] | Iterable[ConflictCandidate],
    ) -> ConflictSignals:
        strongest = ConflictState.NONE
        memory_ids: List[str] = []

        for candidate in candidates:
            state = self.classify(proposal, candidate)
            if state is ConflictState.NONE:
                continue
            if _state_rank(state) > _state_rank(strongest):
                strongest = state
                memory_ids = [candidate.memory_id]
            elif state is strongest:
                memory_ids.append(candidate.memory_id)

        return ConflictSignals(state=strongest, memory_ids=memory_ids)
