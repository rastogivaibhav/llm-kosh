"""Trace Critic - Analyzes traces for weaknesses."""
from __future__ import annotations

from dataclasses import dataclass
from typing import List

from llm_kosh.engine.reasoning.v1_1_tracer import QueryTrace


@dataclass
class TraceWeakness:
    """Identified weakness in query reasoning."""

    category: str
    severity: float
    evidence: List[str]
    recommended_action: str


class TraceCritic:
    """Analyze traces to identify reasoning weaknesses."""

    WEAKNESS_RULES = {
        "low_temporal_consistency": (0.5, "temporal_mismatch",
                                     "gather facts with consistent timestamps"),
        "high_contradiction": (0.3, "conflicting_facts",
                               "identify source of contradiction"),
        "low_path_diversity": (0.4, "low_alternatives",
                              "find additional reasoning routes"),
        "high_pattern_lock": (0.7, "coherence_trap",
                             "widen search space to alternative paths"),
        "no_evidence": (1.0, "retrieval_failure",
                        "reformulate query or expand temporal window"),
    }

    def analyze_trace(self, trace: QueryTrace) -> List[TraceWeakness]:
        """Analyze a trace and identify weaknesses."""
        weaknesses = []

        if not trace.stability:
            # Karpathy-style simplification: an unscored trace is operationally
            # the same as no usable evidence for self-healing purposes.  Keep
            # the category discoverable by the v1.1 tests and downstream
            # generators instead of introducing a parallel taxonomy.
            weaknesses.append(TraceWeakness(
                category="no_evidence_no_stability_assessment",
                severity=1.0,
                evidence=["Stability assessment missing"],
                recommended_action="Re-run critique or expand/reformulate query"
            ))
            return weaknesses

        if trace.stability.status == "no_evidence":
            weaknesses.append(TraceWeakness(
                category="no_evidence",
                severity=1.0,
                evidence=[f"Retrieved {len(trace.anchors_selected)} anchors"],
                recommended_action="Expand temporal window or reformulate"
            ))
            return weaknesses

        # Check temporal consistency
        if trace.temporal_consistency < 0.5:
            weaknesses.append(TraceWeakness(
                category="low_temporal_consistency",
                severity=1.0 - trace.temporal_consistency,
                evidence=[f"Consistency: {trace.temporal_consistency:.2f}"],
                recommended_action="Gather temporally aligned facts"
            ))

        # Check contradictions
        if trace.contradiction_count > 5:
            weakness_severity = min(1.0, trace.contradiction_count / 20.0)
            weaknesses.append(TraceWeakness(
                category="high_contradiction",
                severity=weakness_severity,
                evidence=[f"Contradictions: {trace.contradiction_count}"],
                recommended_action="Identify and resolve conflicting facts"
            ))

        # Check path diversity
        if trace.path_diversity < 0.4 and trace.bundle_size > 0:
            weaknesses.append(TraceWeakness(
                category="low_path_diversity",
                severity=1.0 - trace.path_diversity,
                evidence=[f"Diversity: {trace.path_diversity:.2f}"],
                recommended_action="Find alternative reasoning paths"
            ))

        # Check pattern lock
        if trace.pattern_lock_detected:
            weaknesses.append(TraceWeakness(
                category="high_pattern_lock",
                severity=0.7,
                evidence=["Pattern lock detected"],
                recommended_action="Escape to alternative reasoning space"
            ))

        return weaknesses

    def explain_weakness(self, weakness: TraceWeakness) -> str:
        """Generate human-readable explanation of a weakness."""
        return (
            f"[{weakness.category.upper()}] Severity: {weakness.severity:.1%}\n"
            f"  Evidence: {', '.join(weakness.evidence)}\n"
            f"  Action: {weakness.recommended_action}"
        )
