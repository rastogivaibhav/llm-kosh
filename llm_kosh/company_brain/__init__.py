"""Canonical evidence, memory, retrieval, and context services.

The company-brain layer deliberately lives beside the legacy human-readable
cartridge.  Raw source remains evidence; compact, governed records become
memory; indexes and context packs are derived projections.
"""

from .models import (
    AccessPolicy,
    ContextRequest,
    EvidenceInput,
    EvidenceReference,
    EvidenceSegmentInput,
    EpisodeInput,
    MemoryInput,
    NormalizedEventInput,
    Principal,
    SessionInput,
)
from .store import CompanyBrainStore
from .understanding import understand_evidence

__all__ = [
    "AccessPolicy",
    "CompanyBrainStore",
    "ContextRequest",
    "EvidenceInput",
    "EvidenceReference",
    "EvidenceSegmentInput",
    "EpisodeInput",
    "MemoryInput",
    "NormalizedEventInput",
    "Principal",
    "SessionInput",
    "understand_evidence",
]
