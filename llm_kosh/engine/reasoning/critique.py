from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional

from llm_kosh.engine.reasoning.trace import QueryTrace


class WeaknessType(str, Enum):
    """
    Enum of weakness categories detected during trace analysis.

    Per-trace weaknesses: Problems in a single reasoning trace.
    Cross-iteration weaknesses: Problems across multiple iterations.
    Session-level weaknesses: Long-term patterns across many queries.
    """

    # --- Per-trace weaknesses -----------------------------------------------
    TEMPORAL_CONSISTENCY_LOW = "temporal_consistency_low"
    CONTRADICTION_UNRESOLVED = "contradiction_unresolved"
    SINGLE_PATH_DOMINANCE = "single_path_dominance"
    SHALLOW_DEPTH = "shallow_depth"
    LOW_EVIDENCE_DIVERSITY = "low_evidence_diversity"
    HYPOTHETICAL_PROMOTED_SILENTLY = "hypothetical_promoted_silently"

    # --- Cross-iteration weaknesses -----------------------------------------
    IMPROVEMENT_STALL = "improvement_stall"
    DISCOVERY_GAIN_ZERO = "discovery_gain_zero"
    OSCILLATION = "oscillation"

    # --- Session-level weaknesses -------------------------------------------
    NOVELTY_DEFICIT = "novelty_deficit"
    COVERAGE_BIAS = "coverage_bias"
    SELF_REPETITION = "self_repetition"
    ESCAPE_NEVER_TRIGGERS = "escape_never_triggers"
    LEARNING_STAGNATION = "learning_stagnation"


@dataclass
class TraceWeakness:
    """
    Represents a single weakness detected in a reasoning trace.

    This is the primary output of TraceCritic.analyze() and the input to
    HealingExecutor and CrossQueryCritic. Each weakness records:
    - What is weak (weakness_type)
    - How severe (severity 0.0–1.0)
    - Where it occurred (location in the pipeline)
    - Why it matters (description)
    - How to fix it (suggested_repair_type)
    """

    weakness_type: WeaknessType
    severity: float  # 0.0–1.0, where 1.0 = most severe
    location: str  # Pipeline step: 'lyapunov_critic', 'escape', 'retrieval', 'convergence', 'session'
    description: str  # Human-readable explanation
    suggested_repair_type: str  # Maps to a healing action type

    def to_dict(self) -> dict:
        """Return a JSON-serialisable dict representation."""
        return {
            "weakness_type": self.weakness_type.value,
            "severity": float(self.severity),
            "location": str(self.location),
            "description": str(self.description),
            "suggested_repair_type": str(self.suggested_repair_type),
        }

    @classmethod
    def from_dict(cls, data: dict) -> TraceWeakness:
        """Reconstruct a TraceWeakness from a previously serialised dict."""
        # Validate severity is in [0.0, 1.0]
        severity = float(data.get("severity", 0.0))
        if not (0.0 <= severity <= 1.0):
            raise ValueError(f"severity must be in [0.0, 1.0], got {severity}")

        weakness_type_value = data.get("weakness_type", "")
        try:
            weakness_type = WeaknessType(weakness_type_value)
        except ValueError:
            raise ValueError(
                f"Invalid weakness_type: {weakness_type_value}. "
                f"Must be one of {[t.value for t in WeaknessType]}"
            )

        return cls(
            weakness_type=weakness_type,
            severity=severity,
            location=data.get("location", ""),
            description=data.get("description", ""),
            suggested_repair_type=data.get("suggested_repair_type", ""),
        )


class TraceCritic:
    """
    Analyzes a single QueryTrace and returns a list of TraceWeakness objects
    describing per-trace weaknesses detected during reasoning.
    """

    # Required lyapunov keys; if any are missing we cannot analyze.
    _REQUIRED_KEYS = {
        "temporal_consistency",
        "contradiction_score",
        "pattern_lock_score",
    }

    def analyze(self, trace: QueryTrace) -> List[TraceWeakness]:
        """
        Analyze *trace* for per-trace weaknesses.

        Returns a list of TraceWeakness objects sorted by severity descending.
        Returns an empty list if lyapunov_dimensions is missing required keys.
        No duplicate weakness types are returned.
        """
        dims = trace.lyapunov_dimensions or {}

        # Guard: if any required key is absent, return no analysis.
        if not self._REQUIRED_KEYS.issubset(dims.keys()):
            return []

        weaknesses: List[TraceWeakness] = []
        seen_types: set = set()

        def _add(w: TraceWeakness) -> None:
            if w.weakness_type not in seen_types:
                seen_types.add(w.weakness_type)
                weaknesses.append(w)

        # ------------------------------------------------------------------ #
        # 1. temporal_consistency_low
        # ------------------------------------------------------------------ #
        tc_score = dims["temporal_consistency"]
        if tc_score < 0.6:
            _add(TraceWeakness(
                weakness_type=WeaknessType.TEMPORAL_CONSISTENCY_LOW,
                severity=1.0 - tc_score,
                location="lyapunov_critic",
                description=f"Temporal consistency {tc_score:.2f} below threshold 0.60",
                suggested_repair_type="widen_temporal_window",
            ))

        # ------------------------------------------------------------------ #
        # 2. contradiction_unresolved
        # ------------------------------------------------------------------ #
        contra_score = dims["contradiction_score"]
        if (
            contra_score > 0.3
            and trace.escape_triggered is False
            and (
                trace.dialectic_result_summary is None
                or trace.dialectic_result_summary.get("opposition_challenges", 0) == 0
            )
        ):
            _add(TraceWeakness(
                weakness_type=WeaknessType.CONTRADICTION_UNRESOLVED,
                severity=contra_score,
                location="escape",
                description=(
                    f"Contradiction score {contra_score:.2f} present but escape did not fire "
                    "and dialectic found no opposition"
                ),
                suggested_repair_type="force_contradiction_surface",
            ))

        # ------------------------------------------------------------------ #
        # 3. single_path_dominance
        # ------------------------------------------------------------------ #
        pl_score = dims["pattern_lock_score"]
        if pl_score > 0.7:
            _add(TraceWeakness(
                weakness_type=WeaknessType.SINGLE_PATH_DOMINANCE,
                severity=pl_score,
                location="convergence",
                description=f"Pattern lock score {pl_score:.2f} indicates single path dominance",
                suggested_repair_type="increase_retrieval_depth",
            ))

        # ------------------------------------------------------------------ #
        # 4. shallow_depth
        # ------------------------------------------------------------------ #
        max_deg = trace.bundle_summary.get("max_degeneracy", 0)
        total_paths = trace.bundle_summary.get("total_paths", 0)
        num_anchors = len(trace.anchor_ids)
        if max_deg <= 1 and total_paths <= num_anchors:
            _add(TraceWeakness(
                weakness_type=WeaknessType.SHALLOW_DEPTH,
                severity=0.6,
                location="retrieval",
                description="Bundle contains only shallow paths; indirect causal chains may be missed",
                suggested_repair_type="increase_retrieval_depth",
            ))

        # ------------------------------------------------------------------ #
        # 5. low_evidence_diversity
        # ------------------------------------------------------------------ #
        num_candidates = len(trace.candidates)
        if len(trace.anchor_ids) < 3 and num_candidates > 5:
            severity_led = 1.0 - (len(trace.anchor_ids) / max(num_candidates, 1))
            _add(TraceWeakness(
                weakness_type=WeaknessType.LOW_EVIDENCE_DIVERSITY,
                severity=severity_led,
                location="retrieval",
                description=(
                    f"Only {len(trace.anchor_ids)} anchors selected from {num_candidates} candidates"
                ),
                suggested_repair_type="lower_anchor_threshold",
            ))

        # ------------------------------------------------------------------ #
        # 6. hypothetical_promoted_silently
        # ------------------------------------------------------------------ #
        if any("HYPOTHETICAL" in str(v) for v in trace.metadata.values()):
            _add(TraceWeakness(
                weakness_type=WeaknessType.HYPOTHETICAL_PROMOTED_SILENTLY,
                severity=0.8,
                location="convergence",
                description="HYPOTHETICAL-origin edge may have propagated silently through convergence",
                suggested_repair_type="demote_hypothetical",
            ))

        # Sort by severity descending.
        weaknesses.sort(key=lambda w: w.severity, reverse=True)
        return weaknesses
