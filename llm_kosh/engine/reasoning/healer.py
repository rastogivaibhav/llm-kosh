from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class HealingActionType(str, Enum):
    """
    Enum of healing actions that can be applied when the recursive loop
    detects insufficient stability or contradictions in the current reasoning state.

    Each action encodes a specific modification to query parameters for the
    next recursive iteration:
    - widen_temporal_window: Increase temporal_offset_secs
    - force_contradiction_surface: Set force_contradiction_surface=True
    - increase_retrieval_depth: Increase depth parameter
    - lower_anchor_threshold: Decrease score_threshold
    - demote_hypothetical: Set demote_hypothetical=True
    - reset_to_low_freq_region: Reset anchor_prefix_filter
    - rotate_anchor_prefix: Rotate anchor_prefix_filter to a different region
    """

    WIDEN_TEMPORAL_WINDOW = "widen_temporal_window"
    FORCE_CONTRADICTION_SURFACE = "force_contradiction_surface"
    INCREASE_RETRIEVAL_DEPTH = "increase_retrieval_depth"
    LOWER_ANCHOR_THRESHOLD = "lower_anchor_threshold"
    DEMOTE_HYPOTHETICAL = "demote_hypothetical"
    RESET_TO_LOW_FREQ_REGION = "reset_to_low_freq_region"
    ROTATE_ANCHOR_PREFIX = "rotate_anchor_prefix"


@dataclass
class HealingAction:
    """
    Represents a single healing action to apply during recursive loop iteration.

    Fields:
    - action_type: Which type of healing action (from HealingActionType)
    - target: The parameter/component name being adjusted (e.g., 'temporal_offset_secs',
              'depth', 'score_threshold')
    - magnitude: How much to change the target parameter (semantics depend on target)
    - rationale: Human-readable explanation of why this action was chosen
    """

    action_type: HealingActionType
    target: str
    magnitude: float
    rationale: str

    def to_dict(self) -> dict:
        """Convert to a JSON-serializable dictionary."""
        return {
            "action_type": self.action_type.value,
            "target": self.target,
            "magnitude": self.magnitude,
            "rationale": self.rationale,
        }

    @classmethod
    def from_dict(cls, data: dict) -> HealingAction:
        """Reconstruct a HealingAction from a dictionary."""
        return cls(
            action_type=HealingActionType(data["action_type"]),
            target=data["target"],
            magnitude=float(data["magnitude"]),
            rationale=data["rationale"],
        )


@dataclass
class QueryParams:
    """
    Represents modified query parameters for the next recursive iteration.

    This is what the HealingExecutor produces after applying healing actions.
    It captures all the parameter adjustments needed to retry a query with
    a different strategy.

    Fields with defaults:
    - score_threshold: Minimum score for anchor validity (0.0-1.0), default 0.25
    - depth: Maximum retrieval depth, default 3
    - temporal_offset_secs: Temporal window offset in seconds, default 0.0
    - force_contradiction_surface: Whether to force surfacing contradictions, default False
    - demote_hypothetical: Whether to demote hypothetical facts, default False
    - anchor_prefix_filter: Optional prefix filter for anchor selection, default None
    """

    score_threshold: float = 0.25
    depth: int = 3
    temporal_offset_secs: float = 0.0
    force_contradiction_surface: bool = False
    demote_hypothetical: bool = False
    anchor_prefix_filter: Optional[str] = None

    def to_dict(self) -> dict:
        """Convert to a JSON-serializable dictionary."""
        return {
            "score_threshold": self.score_threshold,
            "depth": self.depth,
            "temporal_offset_secs": self.temporal_offset_secs,
            "force_contradiction_surface": self.force_contradiction_surface,
            "demote_hypothetical": self.demote_hypothetical,
            "anchor_prefix_filter": self.anchor_prefix_filter,
        }

    @classmethod
    def from_dict(cls, data: dict) -> QueryParams:
        """Reconstruct a QueryParams from a dictionary."""
        return cls(
            score_threshold=float(data.get("score_threshold", 0.25)),
            depth=int(data.get("depth", 3)),
            temporal_offset_secs=float(data.get("temporal_offset_secs", 0.0)),
            force_contradiction_surface=bool(data.get("force_contradiction_surface", False)),
            demote_hypothetical=bool(data.get("demote_hypothetical", False)),
            anchor_prefix_filter=data.get("anchor_prefix_filter"),
        )
