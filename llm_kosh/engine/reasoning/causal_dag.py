from __future__ import annotations

import bisect
import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Set


class EdgeType(str, Enum):
    ENABLES = "ENABLES"
    CAUSES = "CAUSES"
    CONTRADICTS = "CONTRADICTS"
    SUPERSEDES = "SUPERSEDES"
    INFERS = "INFERS"


@dataclass
class TemporalFact:
    id: str
    content: str
    ingested_at: datetime
    documented_at: datetime
    valid_from: datetime
    valid_until: Optional[datetime]
    confidence: float
    resonance_profile: dict
    source: str  # "receipt" | "agent" | "user" | "inference"


@dataclass
class CausalEdge:
    id: str
    source_id: str
    target_id: str
    edge_type: EdgeType
    confidence: float
    valid_from: datetime
    valid_until: Optional[datetime]
    established_by: str


@dataclass
class HyperEdge:
    id: str
    source_ids: Set[str]
    target_id: str
    edge_type: EdgeType
    confidence: float
    valid_from: datetime
    valid_until: Optional[datetime]


@dataclass
class TrajectoryState:
    session_id: str
    steps: List[dict] = field(default_factory=list)
    stability: float = 1.0
    escape_count: int = 0
