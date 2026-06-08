from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


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
