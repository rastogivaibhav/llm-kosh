from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional


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


# ---------------------------------------------------------------------------
# Strategy mapping constants
# ---------------------------------------------------------------------------

_TEMPORAL_STEP = 86_400.0          # seconds per day
_TEMPORAL_CAP = 7 * _TEMPORAL_STEP  # 7 days max
_DEPTH_CAP = 8
_SCORE_FLOOR = 0.05
_LOW_FREQ_MARKER = "__low_freq_region__"

# Regex to extract the overused prefix from a COVERAGE_BIAS description.
# Example description: "Anchor selection concentrated in DAG prefix 'abcd' …"
_PREFIX_RE = re.compile(r"DAG prefix '([^']+)'")


class HealingExecutor:
    """
    Translates a WeaknessReport into a QueryParams for the next recursive iteration.

    SAFETY CONTRACT — this class MUST NEVER:
    - Inject facts into the knowledge graph
    - Modify edge confidences
    - Create new facts
    It only produces a modified QueryParams object.
    """

    def heal(
        self,
        weakness_report: "WeaknessReport",  # noqa: F821 – imported lazily to avoid circular deps
        base_params: Optional[QueryParams] = None,
    ) -> QueryParams:
        """
        Apply healing actions derived from *weakness_report* and return new QueryParams.

        Parameters
        ----------
        weakness_report:
            Aggregated report produced by TraceCritic / CrossQueryCritic.
        base_params:
            Starting QueryParams.  If provided, healing accumulates on top of
            these values; otherwise the dataclass defaults are used.

        Returns
        -------
        QueryParams
            Modified parameters for the next iteration.  Never mutates
            *base_params* – a fresh object is always returned.
        """
        # Import here to avoid circular-import issues at module load time.
        from llm_kosh.engine.reasoning.critique import WeaknessType  # noqa: PLC0415

        if base_params is None:
            base_params = QueryParams()

        # Work with mutable accumulators seeded from base_params.
        depth: int = base_params.depth
        temporal_offset: float = base_params.temporal_offset_secs
        score_threshold: float = base_params.score_threshold
        force_contradiction: bool = base_params.force_contradiction_surface
        demote_hypo: bool = base_params.demote_hypothetical
        anchor_prefix: Optional[str] = base_params.anchor_prefix_filter
        metadata: dict = {}

        # Process weaknesses in descending severity order (already guaranteed by
        # WeaknessReport.all_weaknesses, but we sort defensively here as well).
        weaknesses = weakness_report.all_weaknesses  # sorted desc by severity

        # Collect COVERAGE_BIAS descriptions for prefix rotation (needed below).
        coverage_bias_descriptions: List[str] = [
            w.description
            for w in weaknesses
            if w.weakness_type == WeaknessType.COVERAGE_BIAS
        ]

        for weakness in weaknesses:
            wt = weakness.weakness_type

            if wt == WeaknessType.TEMPORAL_CONSISTENCY_LOW:
                temporal_offset = min(temporal_offset + _TEMPORAL_STEP, _TEMPORAL_CAP)

            elif wt == WeaknessType.CONTRADICTION_UNRESOLVED:
                force_contradiction = True

            elif wt in (
                WeaknessType.SINGLE_PATH_DOMINANCE,
                WeaknessType.SHALLOW_DEPTH,
                WeaknessType.IMPROVEMENT_STALL,
            ):
                depth = min(depth + 2, _DEPTH_CAP)

            elif wt == WeaknessType.LEARNING_STAGNATION:
                depth = min(depth + 1, _DEPTH_CAP)

            elif wt == WeaknessType.LOW_EVIDENCE_DIVERSITY:
                score_threshold = max(score_threshold - 0.05, _SCORE_FLOOR)

            elif wt == WeaknessType.HYPOTHETICAL_PROMOTED_SILENTLY:
                demote_hypo = True

            elif wt == WeaknessType.NOVELTY_DEFICIT:
                # Mark metadata to signal the retrieval layer to explore low-frequency
                # regions; we never write to the knowledge graph.
                metadata["reset_to_low_freq_region"] = True
                if anchor_prefix is None:
                    anchor_prefix = _LOW_FREQ_MARKER

            elif wt == WeaknessType.COVERAGE_BIAS:
                # Rotate to the LEAST common prefix seen in COVERAGE_BIAS descriptions.
                # The most-biased prefix is mentioned in the description; the "least
                # common" available prefix is any other prefix – we try to extract and
                # then invert the selection.
                if anchor_prefix is None:
                    least_common = self._least_common_prefix(coverage_bias_descriptions)
                    if least_common is not None:
                        anchor_prefix = least_common

            # WeaknessTypes with no action: SELF_REPETITION, DISCOVERY_GAIN_ZERO,
            # OSCILLATION, ESCAPE_NEVER_TRIGGERS – intentionally skipped.

        return QueryParams(
            score_threshold=score_threshold,
            depth=depth,
            temporal_offset_secs=temporal_offset,
            force_contradiction_surface=force_contradiction,
            demote_hypothetical=demote_hypo,
            anchor_prefix_filter=anchor_prefix,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _least_common_prefix(coverage_bias_descriptions: List[str]) -> Optional[str]:
        """
        Given the description strings of all COVERAGE_BIAS weaknesses in the
        current report, extract the overused prefix from each, then return
        one that is *least* common (i.e., not the dominant one).

        If no prefix can be extracted, return None.
        """
        overused: List[str] = []
        for desc in coverage_bias_descriptions:
            m = _PREFIX_RE.search(desc)
            if m:
                overused.append(m.group(1))

        if not overused:
            return None

        # Count frequency of each extracted prefix.
        counts = Counter(overused)
        # Return the least-common prefix (inverse of coverage bias).
        least = counts.most_common()[-1][0]
        return least
