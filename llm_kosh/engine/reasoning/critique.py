from __future__ import annotations

from collections import Counter
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


@dataclass
class WeaknessReport:
    """
    Aggregated weakness report for a single trace, combining per-trace and
    session-level weaknesses into a single auditable record.
    """

    trace_id: str
    per_trace_weaknesses: List[TraceWeakness] = field(default_factory=list)
    session_weaknesses: List[TraceWeakness] = field(default_factory=list)
    total_severity: float = 0.0

    def __post_init__(self) -> None:
        """Recompute total_severity from all weaknesses."""
        all_w = self.per_trace_weaknesses + self.session_weaknesses
        if all_w:
            self.total_severity = sum(w.severity for w in all_w) / len(all_w)
        else:
            self.total_severity = 0.0

    # ------------------------------------------------------------------ #
    # Properties
    # ------------------------------------------------------------------ #

    @property
    def all_weaknesses(self) -> List[TraceWeakness]:
        """Return per_trace_weaknesses + session_weaknesses sorted by severity descending."""
        combined = self.per_trace_weaknesses + self.session_weaknesses
        return sorted(combined, key=lambda w: w.severity, reverse=True)

    @property
    def has_weaknesses(self) -> bool:
        """True if any weakness (per-trace or session) exists."""
        return bool(self.per_trace_weaknesses or self.session_weaknesses)

    @property
    def worst_weakness(self) -> Optional[TraceWeakness]:
        """Highest severity weakness, or None if no weaknesses exist."""
        all_w = self.all_weaknesses
        return all_w[0] if all_w else None

    # ------------------------------------------------------------------ #
    # Serialization
    # ------------------------------------------------------------------ #

    def to_dict(self) -> dict:
        """Return a JSON-serialisable dict representation."""
        return {
            "trace_id": self.trace_id,
            "per_trace_weaknesses": [w.to_dict() for w in self.per_trace_weaknesses],
            "session_weaknesses": [w.to_dict() for w in self.session_weaknesses],
            "total_severity": float(self.total_severity),
        }

    @classmethod
    def from_dict(cls, data: dict) -> WeaknessReport:
        """Reconstruct a WeaknessReport from a previously serialised dict."""
        per_trace = [TraceWeakness.from_dict(d) for d in data.get("per_trace_weaknesses", [])]
        session = [TraceWeakness.from_dict(d) for d in data.get("session_weaknesses", [])]
        return cls(
            trace_id=data.get("trace_id", ""),
            per_trace_weaknesses=per_trace,
            session_weaknesses=session,
        )


class TraceCritic:
    """
    Analyzes QueryTrace objects for weaknesses.

    Provides two analysis methods:
    - analyze(): Single-trace weaknesses (per-trace analysis)
    - analyze_iteration(): Cross-iteration weaknesses (recursive loop context)
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

    def analyze_iteration(
        self, trace: QueryTrace, iteration: int, prior_traces: List[QueryTrace]
    ) -> List[TraceWeakness]:
        """
        Analyze *trace* for cross-iteration weaknesses in the recursive loop context.

        Detects 3 weaknesses that only make sense when iteration > 0:
        1. improvement_stall: Stability gain < 0.05
        2. discovery_gain_zero: Discovery executed but repair_strength < 0.1
        3. oscillation: Stability went UP then DOWN over 3 consecutive iterations

        Returns a list of TraceWeakness objects sorted by severity descending.
        Returns an empty list if iteration == 0 OR prior_traces is empty.
        No duplicate weakness types are returned.
        """
        # Guard: only analyze if we have prior iterations
        if iteration == 0 or not prior_traces:
            return []

        weaknesses: List[TraceWeakness] = []
        seen_types: set = set()

        def _add(w: TraceWeakness) -> None:
            if w.weakness_type not in seen_types:
                seen_types.add(w.weakness_type)
                weaknesses.append(w)

        # ------------------------------------------------------------------ #
        # 1. improvement_stall
        # ------------------------------------------------------------------ #
        stability_gain = trace.stability_score - prior_traces[-1].stability_score
        if stability_gain < 0.05:
            _add(TraceWeakness(
                weakness_type=WeaknessType.IMPROVEMENT_STALL,
                severity=0.7,
                location="recursive_loop",
                description=(
                    f"Stability gain from iteration {iteration - 1} to {iteration} "
                    f"is {stability_gain:.3f}, below threshold 0.05"
                ),
                suggested_repair_type="increase_retrieval_depth",
            ))

        # ------------------------------------------------------------------ #
        # 2. discovery_gain_zero
        # ------------------------------------------------------------------ #
        if trace.discovery_result_summary is not None:
            repair_strength = trace.discovery_result_summary.get("repair_strength", 1.0)
            if repair_strength < 0.1:
                _add(TraceWeakness(
                    weakness_type=WeaknessType.DISCOVERY_GAIN_ZERO,
                    severity=0.8,
                    location="discovery",
                    description=(
                        f"Discovery executed but repair_strength {repair_strength:.3f} "
                        "indicates no new evidence found"
                    ),
                    suggested_repair_type="reset_to_low_freq_region",
                ))

        # ------------------------------------------------------------------ #
        # 3. oscillation
        # ------------------------------------------------------------------ #
        if iteration >= 2 and len(prior_traces) >= 2:
            prev_prev_stability = prior_traces[-2].stability_score
            prev_stability = prior_traces[-1].stability_score
            curr_stability = trace.stability_score

            # Detect pattern: up then down
            if (prev_stability > prev_prev_stability and
                curr_stability < prev_stability - 0.03):
                severity = abs(curr_stability - prev_stability)
                _add(TraceWeakness(
                    weakness_type=WeaknessType.OSCILLATION,
                    severity=severity,
                    location="recursive_loop",
                    description=(
                        f"Stability oscillated: {prev_prev_stability:.3f} → "
                        f"{prev_stability:.3f} → {curr_stability:.3f}"
                    ),
                    suggested_repair_type="widen_temporal_window",
                ))

        # Sort by severity descending.
        weaknesses.sort(key=lambda w: w.severity, reverse=True)
        return weaknesses


class CrossQueryCritic:
    """
    Analyzes a session (list of QueryTrace objects) for long-term, cross-query
    weakness patterns that cannot be detected by inspecting a single trace.
    """

    def analyze_session(self, traces: List[QueryTrace]) -> List[TraceWeakness]:
        """
        Analyze a session of traces for 5 session-level weaknesses.

        Returns a list of TraceWeakness objects sorted by severity descending.
        Returns [] for an empty traces list.
        No duplicate weakness types are returned.
        """
        if not traces:
            return []

        weaknesses: List[TraceWeakness] = []
        seen_types: set = set()

        def _add(w: TraceWeakness) -> None:
            if w.weakness_type not in seen_types:
                seen_types.add(w.weakness_type)
                weaknesses.append(w)

        n = len(traces)

        # ------------------------------------------------------------------ #
        # 1. novelty_deficit
        # ------------------------------------------------------------------ #
        if n >= 5:
            # Gather fact_ids per trace (from bundle_summary["fact_ids"])
            per_trace_fact_sets = [
                set(t.bundle_summary.get("fact_ids", [])) for t in traces
            ]
            all_fact_ids: set = set()
            for fs in per_trace_fact_sets:
                all_fact_ids.update(fs)

            if all_fact_ids:
                # Count how many traces each fact_id appears in
                fact_counts: Counter = Counter()
                for fs in per_trace_fact_sets:
                    for fid in fs:
                        fact_counts[fid] += 1

                threshold = 0.8 * n
                overused = {fid for fid, cnt in fact_counts.items() if cnt >= threshold}
                if overused:
                    pct = threshold / n  # == 0.8
                    count = len(overused)
                    severity = len(overused) / len(all_fact_ids)
                    _add(TraceWeakness(
                        weakness_type=WeaknessType.NOVELTY_DEFICIT,
                        severity=severity,
                        location="session",
                        description=(
                            f"{count} fact(s) appear in {pct:.0%}+ of {n} recent queries; "
                            "novelty deficit detected"
                        ),
                        suggested_repair_type="reset_to_low_freq_region",
                    ))

        # ------------------------------------------------------------------ #
        # 2. coverage_bias
        # ------------------------------------------------------------------ #
        if n >= 5:
            all_anchors: List[str] = []
            for t in traces:
                all_anchors.extend(t.anchor_ids)

            if all_anchors:
                prefix_counts: Counter = Counter(a[:4] for a in all_anchors)
                most_common_prefix, most_common_count = prefix_counts.most_common(1)[0]
                pct = most_common_count / len(all_anchors)
                if pct >= 0.70:
                    _add(TraceWeakness(
                        weakness_type=WeaknessType.COVERAGE_BIAS,
                        severity=0.6,
                        location="session",
                        description=(
                            f"Anchor selection concentrated in DAG prefix '{most_common_prefix}' "
                            f"({pct:.0%} of anchors); coverage bias detected"
                        ),
                        suggested_repair_type="rotate_anchor_prefix",
                    ))

        # ------------------------------------------------------------------ #
        # 3. self_repetition
        # ------------------------------------------------------------------ #
        if n >= 3:
            # Collect converged_fact_ids from traces that have a dialectic summary
            converged_ids = [
                t.dialectic_result_summary.get("converged_fact_id", "")
                for t in traces
                if t.dialectic_result_summary is not None
            ]
            # Only proceed if we have at least 2 converged answers to compare
            if len(converged_ids) >= 2:
                # Count fact_id frequencies
                id_counts: Counter = Counter(converged_ids)
                total = len(converged_ids)
                max_count = id_counts.most_common(1)[0][1]
                repetition_pct = max_count / total
                if repetition_pct > 0.5:
                    _add(TraceWeakness(
                        weakness_type=WeaknessType.SELF_REPETITION,
                        severity=repetition_pct,
                        location="session",
                        description=f"Converged answers showing {repetition_pct:.0%} cross-query repetition",
                        suggested_repair_type="reset_to_low_freq_region",
                    ))

        # ------------------------------------------------------------------ #
        # 4. escape_never_triggers
        # ------------------------------------------------------------------ #
        if n >= 10:
            all_escaped = [t.escape_triggered for t in traces]
            if not any(all_escaped):
                mean_stability = sum(t.stability_score for t in traces) / n
                if mean_stability < 0.75:
                    _add(TraceWeakness(
                        weakness_type=WeaknessType.ESCAPE_NEVER_TRIGGERS,
                        severity=0.5,
                        location="session",
                        description=(
                            f"Escape mechanism never triggered across {n} queries "
                            "despite marginal stability"
                        ),
                        suggested_repair_type="lower_anchor_threshold",
                    ))

        # ------------------------------------------------------------------ #
        # 5. learning_stagnation
        # ------------------------------------------------------------------ #
        if n >= 8:
            def _lyapunov_weakness_count(t: QueryTrace) -> int:
                dims = t.lyapunov_dimensions or {}
                count = 0
                if dims.get("temporal_consistency", 1.0) < 0.6:
                    count += 1
                if dims.get("contradiction_score", 0.0) > 0.3:
                    count += 1
                if dims.get("pattern_lock_score", 0.0) > 0.7:
                    count += 1
                return count

            counts = [_lyapunov_weakness_count(t) for t in traces]
            mid = n // 2
            first_half_mean = sum(counts[:mid]) / mid
            second_half_mean = sum(counts[mid:]) / (n - mid)

            # No improvement = second half weakness count is not lower than first half
            # (weaknesses should decrease over time; if second_half >= first_half, no learning)
            if second_half_mean >= first_half_mean:
                _add(TraceWeakness(
                    weakness_type=WeaknessType.LEARNING_STAGNATION,
                    severity=0.6,
                    location="session",
                    description=(
                        f"Weakness count not decreasing over {n} traces: "
                        f"first_half={first_half_mean:.2f}, second_half={second_half_mean:.2f}"
                    ),
                    suggested_repair_type="increase_retrieval_depth",
                ))

        # Sort by severity descending
        weaknesses.sort(key=lambda w: w.severity, reverse=True)
        return weaknesses
