"""
Tests for TraceWeakness dataclass and TraceCritic (llm_kosh/engine/reasoning/critique.py).

Covers:
- WeaknessType enum has all 14 values
- TraceWeakness construction with all fields
- to_dict() / from_dict() round-trip
- severity is validated to be in [0.0, 1.0]
- Invalid weakness_type raises ValueError in from_dict()
- TraceCritic.analyze() detects each of the 6 per-trace weaknesses
"""
from __future__ import annotations

import pytest

from llm_kosh.engine.reasoning.critique import (
    CrossQueryCritic,
    TraceCritic,
    TraceWeakness,
    WeaknessReport,
    WeaknessType,
)
from llm_kosh.engine.reasoning.trace import QueryTrace


class TestWeaknessType:
    """Tests for WeaknessType enum."""

    def test_all_14_enum_values_present(self):
        """Verify all 14 weakness types are defined."""
        expected_values = {
            # Per-trace weaknesses (6)
            "temporal_consistency_low",
            "contradiction_unresolved",
            "single_path_dominance",
            "shallow_depth",
            "low_evidence_diversity",
            "hypothetical_promoted_silently",
            # Cross-iteration weaknesses (3)
            "improvement_stall",
            "discovery_gain_zero",
            "oscillation",
            # Session-level weaknesses (5)
            "novelty_deficit",
            "coverage_bias",
            "self_repetition",
            "escape_never_triggers",
            "learning_stagnation",
        }

        actual_values = {e.value for e in WeaknessType}
        assert actual_values == expected_values, (
            f"Mismatch in WeaknessType values.\n"
            f"Expected: {expected_values}\n"
            f"Actual: {actual_values}\n"
            f"Missing: {expected_values - actual_values}\n"
            f"Extra: {actual_values - expected_values}"
        )

    def test_enum_count_is_14(self):
        """Verify exactly 14 enum members."""
        assert len(WeaknessType) == 14

    def test_enum_members_are_strings(self):
        """Verify all enum members inherit from str."""
        for member in WeaknessType:
            assert isinstance(member.value, str)


class TestTraceWeaknessConstruction:
    """Tests for TraceWeakness dataclass construction."""

    def test_construct_with_all_fields(self):
        """Test creating a TraceWeakness with all fields."""
        weakness = TraceWeakness(
            weakness_type=WeaknessType.TEMPORAL_CONSISTENCY_LOW,
            severity=0.75,
            location="lyapunov_critic",
            description="Temporal consistency score is below 0.5",
            suggested_repair_type="widen_temporal_window",
        )

        assert weakness.weakness_type == WeaknessType.TEMPORAL_CONSISTENCY_LOW
        assert weakness.severity == 0.75
        assert weakness.location == "lyapunov_critic"
        assert weakness.description == "Temporal consistency score is below 0.5"
        assert weakness.suggested_repair_type == "widen_temporal_window"

    def test_construct_with_different_weakness_types(self):
        """Test construction with different weakness types."""
        for weakness_type in WeaknessType:
            weakness = TraceWeakness(
                weakness_type=weakness_type,
                severity=0.5,
                location="test",
                description="test",
                suggested_repair_type="test",
            )
            assert weakness.weakness_type == weakness_type

    def test_severity_zero(self):
        """Test severity can be 0.0."""
        weakness = TraceWeakness(
            weakness_type=WeaknessType.IMPROVEMENT_STALL,
            severity=0.0,
            location="convergence",
            description="No improvement detected",
            suggested_repair_type="force_exploration",
        )
        assert weakness.severity == 0.0

    def test_severity_one(self):
        """Test severity can be 1.0 (most severe)."""
        weakness = TraceWeakness(
            weakness_type=WeaknessType.OSCILLATION,
            severity=1.0,
            location="session",
            description="System is oscillating between states",
            suggested_repair_type="reset_damping",
        )
        assert weakness.severity == 1.0

    def test_severity_mid_range(self):
        """Test severity can be any value in [0.0, 1.0]."""
        for severity in [0.0, 0.25, 0.5, 0.75, 1.0]:
            weakness = TraceWeakness(
                weakness_type=WeaknessType.LOW_EVIDENCE_DIVERSITY,
                severity=severity,
                location="retrieval",
                description="Low diversity in evidence",
                suggested_repair_type="broaden_query",
            )
            assert weakness.severity == severity


class TestTraceWeaknessSerialization:
    """Tests for to_dict() and from_dict() round-trip."""

    def test_to_dict_returns_dict(self):
        """Test to_dict() returns a dict."""
        weakness = TraceWeakness(
            weakness_type=WeaknessType.CONTRADICTION_UNRESOLVED,
            severity=0.6,
            location="escape",
            description="Contradiction not resolved",
            suggested_repair_type="force_contradiction_surface",
        )
        result = weakness.to_dict()
        assert isinstance(result, dict)

    def test_to_dict_contains_all_fields(self):
        """Test to_dict() includes all required fields."""
        weakness = TraceWeakness(
            weakness_type=WeaknessType.SINGLE_PATH_DOMINANCE,
            severity=0.8,
            location="lyapunov_critic",
            description="One path dominates",
            suggested_repair_type="force_diversity",
        )
        result = weakness.to_dict()

        assert "weakness_type" in result
        assert "severity" in result
        assert "location" in result
        assert "description" in result
        assert "suggested_repair_type" in result

    def test_to_dict_weakness_type_is_string_value(self):
        """Test that weakness_type is serialized as string value."""
        weakness = TraceWeakness(
            weakness_type=WeaknessType.SHALLOW_DEPTH,
            severity=0.4,
            location="retrieval",
            description="Reasoning is shallow",
            suggested_repair_type="deepen_search",
        )
        result = weakness.to_dict()
        assert result["weakness_type"] == "shallow_depth"
        assert isinstance(result["weakness_type"], str)

    def test_from_dict_basic(self):
        """Test from_dict() with valid input."""
        data = {
            "weakness_type": "temporal_consistency_low",
            "severity": 0.7,
            "location": "lyapunov_critic",
            "description": "Temporal consistency is low",
            "suggested_repair_type": "widen_temporal_window",
        }
        weakness = TraceWeakness.from_dict(data)

        assert weakness.weakness_type == WeaknessType.TEMPORAL_CONSISTENCY_LOW
        assert weakness.severity == 0.7
        assert weakness.location == "lyapunov_critic"
        assert weakness.description == "Temporal consistency is low"
        assert weakness.suggested_repair_type == "widen_temporal_window"

    def test_roundtrip_all_weakness_types(self):
        """Test to_dict() -> from_dict() round-trip for all weakness types."""
        for weakness_type in WeaknessType:
            original = TraceWeakness(
                weakness_type=weakness_type,
                severity=0.65,
                location="test_location",
                description="Test description",
                suggested_repair_type="test_repair",
            )
            data = original.to_dict()
            restored = TraceWeakness.from_dict(data)

            assert restored.weakness_type == original.weakness_type
            assert restored.severity == original.severity
            assert restored.location == original.location
            assert restored.description == original.description
            assert restored.suggested_repair_type == original.suggested_repair_type

    def test_roundtrip_boundary_severities(self):
        """Test round-trip with boundary severity values."""
        for severity in [0.0, 0.5, 1.0]:
            original = TraceWeakness(
                weakness_type=WeaknessType.NOVELTY_DEFICIT,
                severity=severity,
                location="session",
                description="Test",
                suggested_repair_type="test_repair",
            )
            data = original.to_dict()
            restored = TraceWeakness.from_dict(data)

            assert restored.severity == severity

    def test_roundtrip_special_characters_in_description(self):
        """Test round-trip with special characters in description."""
        original = TraceWeakness(
            weakness_type=WeaknessType.COVERAGE_BIAS,
            severity=0.55,
            location="session",
            description='Description with "quotes" and \\ backslash & special chars',
            suggested_repair_type="rebalance_coverage",
        )
        data = original.to_dict()
        restored = TraceWeakness.from_dict(data)

        assert restored.description == original.description

    def test_from_dict_missing_optional_defaults_to_empty_string(self):
        """Test from_dict() with missing fields defaults to empty string."""
        data = {
            "weakness_type": "oscillation",
            "severity": 0.9,
        }
        weakness = TraceWeakness.from_dict(data)

        assert weakness.weakness_type == WeaknessType.OSCILLATION
        assert weakness.severity == 0.9
        assert weakness.location == ""
        assert weakness.description == ""
        assert weakness.suggested_repair_type == ""


class TestTraceWeaknessValidation:
    """Tests for validation in from_dict()."""

    def test_severity_below_zero_raises_error(self):
        """Test that severity < 0.0 raises ValueError."""
        data = {
            "weakness_type": "improvement_stall",
            "severity": -0.1,
            "location": "convergence",
            "description": "Test",
            "suggested_repair_type": "test",
        }
        with pytest.raises(ValueError, match="severity must be in"):
            TraceWeakness.from_dict(data)

    def test_severity_above_one_raises_error(self):
        """Test that severity > 1.0 raises ValueError."""
        data = {
            "weakness_type": "discovery_gain_zero",
            "severity": 1.5,
            "location": "convergence",
            "description": "Test",
            "suggested_repair_type": "test",
        }
        with pytest.raises(ValueError, match="severity must be in"):
            TraceWeakness.from_dict(data)

    def test_invalid_weakness_type_raises_error(self):
        """Test that invalid weakness_type raises ValueError."""
        data = {
            "weakness_type": "invalid_weakness_type",
            "severity": 0.5,
            "location": "test",
            "description": "Test",
            "suggested_repair_type": "test",
        }
        with pytest.raises(ValueError, match="Invalid weakness_type"):
            TraceWeakness.from_dict(data)

    def test_invalid_weakness_type_message_includes_valid_options(self):
        """Test that error message lists valid weakness types."""
        data = {
            "weakness_type": "not_a_real_weakness",
            "severity": 0.5,
            "location": "test",
            "description": "Test",
            "suggested_repair_type": "test",
        }
        with pytest.raises(ValueError) as exc_info:
            TraceWeakness.from_dict(data)
        error_msg = str(exc_info.value)
        assert "temporal_consistency_low" in error_msg or "Must be one of" in error_msg


class TestTraceWeaknessEdgeCases:
    """Tests for edge cases and corner cases."""

    def test_empty_strings_for_location_and_others(self):
        """Test that empty strings are allowed."""
        weakness = TraceWeakness(
            weakness_type=WeaknessType.LEARNING_STAGNATION,
            severity=0.5,
            location="",
            description="",
            suggested_repair_type="",
        )
        data = weakness.to_dict()
        restored = TraceWeakness.from_dict(data)

        assert restored.location == ""
        assert restored.description == ""
        assert restored.suggested_repair_type == ""

    def test_very_long_description(self):
        """Test that long descriptions are preserved."""
        long_desc = "x" * 10000
        weakness = TraceWeakness(
            weakness_type=WeaknessType.SELF_REPETITION,
            severity=0.3,
            location="session",
            description=long_desc,
            suggested_repair_type="diversify",
        )
        data = weakness.to_dict()
        restored = TraceWeakness.from_dict(data)

        assert restored.description == long_desc

    def test_severity_as_string_converted_to_float(self):
        """Test that severity string values are converted to float."""
        data = {
            "weakness_type": "escape_never_triggers",
            "severity": "0.42",  # String instead of float
            "location": "session",
            "description": "Escape never triggers",
            "suggested_repair_type": "adjust_escape_threshold",
        }
        weakness = TraceWeakness.from_dict(data)
        assert weakness.severity == 0.42
        assert isinstance(weakness.severity, float)


# ---------------------------------------------------------------------------
# Helper: build a "clean" trace with all triggers OFF
# ---------------------------------------------------------------------------

def _clean_trace(**overrides) -> QueryTrace:
    """
    Return a QueryTrace whose default field values do NOT trigger any weakness.

    Callers can override individual fields to trigger specific weaknesses.
    """
    defaults = dict(
        lyapunov_dimensions={
            "temporal_consistency": 0.9,   # >= 0.6  → no temporal_consistency_low
            "contradiction_score": 0.1,    # <= 0.3  → no contradiction_unresolved
            "path_diversity": 0.8,
            "degeneracy": 0.5,
            "pattern_lock_score": 0.5,     # <= 0.7  → no single_path_dominance
        },
        bundle_summary={
            "fiber_count": 3,
            "total_paths": 10,             # > num_anchors → no shallow_depth
            "max_degeneracy": 3,           # > 1      → no shallow_depth
            "fact_ids": ["f1", "f2", "f3"],
        },
        anchor_ids=["a1", "a2", "a3"],     # >= 3    → no low_evidence_diversity
        candidates=[("c1", 1, 0.9), ("c2", 2, 0.8)],  # <= 5 → no low_evidence_diversity
        escape_triggered=False,
        stability_status="stable",
        dialectic_result_summary=None,
        metadata={},
    )
    defaults.update(overrides)
    return QueryTrace(**defaults)


class TestTraceCritic:
    """Tests for TraceCritic.analyze()."""

    # ------------------------------------------------------------------ #
    # Empty / missing lyapunov_dimensions
    # ------------------------------------------------------------------ #

    def test_empty_lyapunov_returns_empty_list(self):
        """If lyapunov_dimensions is empty, return []."""
        trace = QueryTrace(lyapunov_dimensions={})
        critic = TraceCritic()
        result = critic.analyze(trace)
        assert result == []

    def test_missing_required_key_returns_empty_list(self):
        """If a required key is absent from lyapunov_dimensions, return []."""
        # Only 'temporal_consistency' present — contradiction_score and
        # pattern_lock_score missing.
        trace = QueryTrace(lyapunov_dimensions={"temporal_consistency": 0.4})
        critic = TraceCritic()
        result = critic.analyze(trace)
        assert result == []

    # ------------------------------------------------------------------ #
    # 1. temporal_consistency_low
    # ------------------------------------------------------------------ #

    def test_temporal_consistency_low_detected(self):
        """Trigger when temporal_consistency < 0.6."""
        trace = _clean_trace(
            lyapunov_dimensions={
                "temporal_consistency": 0.4,
                "contradiction_score": 0.1,
                "path_diversity": 0.8,
                "degeneracy": 0.5,
                "pattern_lock_score": 0.5,
            }
        )
        result = TraceCritic().analyze(trace)
        types = [w.weakness_type for w in result]
        assert WeaknessType.TEMPORAL_CONSISTENCY_LOW in types

    def test_temporal_consistency_low_severity(self):
        """Severity = 1.0 - score."""
        trace = _clean_trace(
            lyapunov_dimensions={
                "temporal_consistency": 0.4,
                "contradiction_score": 0.1,
                "path_diversity": 0.8,
                "degeneracy": 0.5,
                "pattern_lock_score": 0.5,
            }
        )
        result = TraceCritic().analyze(trace)
        w = next(x for x in result if x.weakness_type == WeaknessType.TEMPORAL_CONSISTENCY_LOW)
        assert abs(w.severity - 0.6) < 1e-9
        assert w.location == "lyapunov_critic"
        assert w.suggested_repair_type == "widen_temporal_window"

    def test_temporal_consistency_not_detected_at_threshold(self):
        """NOT triggered when temporal_consistency == 0.6 (boundary, not < 0.6)."""
        trace = _clean_trace(
            lyapunov_dimensions={
                "temporal_consistency": 0.6,
                "contradiction_score": 0.1,
                "path_diversity": 0.8,
                "degeneracy": 0.5,
                "pattern_lock_score": 0.5,
            }
        )
        result = TraceCritic().analyze(trace)
        types = [w.weakness_type for w in result]
        assert WeaknessType.TEMPORAL_CONSISTENCY_LOW not in types

    # ------------------------------------------------------------------ #
    # 2. contradiction_unresolved
    # ------------------------------------------------------------------ #

    def test_contradiction_unresolved_detected(self):
        """Trigger: contradiction_score > 0.3, escape not triggered, no dialectic opposition."""
        trace = _clean_trace(
            lyapunov_dimensions={
                "temporal_consistency": 0.9,
                "contradiction_score": 0.5,
                "path_diversity": 0.8,
                "degeneracy": 0.5,
                "pattern_lock_score": 0.5,
            },
            escape_triggered=False,
            dialectic_result_summary=None,
        )
        result = TraceCritic().analyze(trace)
        types = [w.weakness_type for w in result]
        assert WeaknessType.CONTRADICTION_UNRESOLVED in types

    def test_contradiction_unresolved_not_detected_when_escape_fired(self):
        """NOT triggered when escape_triggered is True."""
        trace = _clean_trace(
            lyapunov_dimensions={
                "temporal_consistency": 0.9,
                "contradiction_score": 0.5,
                "path_diversity": 0.8,
                "degeneracy": 0.5,
                "pattern_lock_score": 0.5,
            },
            escape_triggered=True,
            dialectic_result_summary=None,
        )
        result = TraceCritic().analyze(trace)
        types = [w.weakness_type for w in result]
        assert WeaknessType.CONTRADICTION_UNRESOLVED not in types

    def test_contradiction_unresolved_not_detected_when_dialectic_has_opposition(self):
        """NOT triggered when dialectic found opposition challenges."""
        trace = _clean_trace(
            lyapunov_dimensions={
                "temporal_consistency": 0.9,
                "contradiction_score": 0.5,
                "path_diversity": 0.8,
                "degeneracy": 0.5,
                "pattern_lock_score": 0.5,
            },
            escape_triggered=False,
            dialectic_result_summary={
                "converged_fact_id": "f1",
                "converged_score": 0.9,
                "opposition_challenges": 2,
                "reopened": False,
                "final_status": "accepted",
            },
        )
        result = TraceCritic().analyze(trace)
        types = [w.weakness_type for w in result]
        assert WeaknessType.CONTRADICTION_UNRESOLVED not in types

    def test_contradiction_unresolved_not_detected_when_score_low(self):
        """NOT triggered when contradiction_score <= 0.3."""
        trace = _clean_trace(
            lyapunov_dimensions={
                "temporal_consistency": 0.9,
                "contradiction_score": 0.3,
                "path_diversity": 0.8,
                "degeneracy": 0.5,
                "pattern_lock_score": 0.5,
            },
            escape_triggered=False,
            dialectic_result_summary=None,
        )
        result = TraceCritic().analyze(trace)
        types = [w.weakness_type for w in result]
        assert WeaknessType.CONTRADICTION_UNRESOLVED not in types

    # ------------------------------------------------------------------ #
    # 3. single_path_dominance
    # ------------------------------------------------------------------ #

    def test_single_path_dominance_detected(self):
        """Trigger when pattern_lock_score > 0.7."""
        trace = _clean_trace(
            lyapunov_dimensions={
                "temporal_consistency": 0.9,
                "contradiction_score": 0.1,
                "path_diversity": 0.8,
                "degeneracy": 0.5,
                "pattern_lock_score": 0.85,
            }
        )
        result = TraceCritic().analyze(trace)
        types = [w.weakness_type for w in result]
        assert WeaknessType.SINGLE_PATH_DOMINANCE in types

    def test_single_path_dominance_severity(self):
        """Severity equals the pattern_lock_score."""
        trace = _clean_trace(
            lyapunov_dimensions={
                "temporal_consistency": 0.9,
                "contradiction_score": 0.1,
                "path_diversity": 0.8,
                "degeneracy": 0.5,
                "pattern_lock_score": 0.85,
            }
        )
        result = TraceCritic().analyze(trace)
        w = next(x for x in result if x.weakness_type == WeaknessType.SINGLE_PATH_DOMINANCE)
        assert abs(w.severity - 0.85) < 1e-9
        assert w.location == "convergence"
        assert w.suggested_repair_type == "increase_retrieval_depth"

    def test_single_path_dominance_not_detected_at_boundary(self):
        """NOT triggered when pattern_lock_score == 0.7."""
        trace = _clean_trace(
            lyapunov_dimensions={
                "temporal_consistency": 0.9,
                "contradiction_score": 0.1,
                "path_diversity": 0.8,
                "degeneracy": 0.5,
                "pattern_lock_score": 0.7,
            }
        )
        result = TraceCritic().analyze(trace)
        types = [w.weakness_type for w in result]
        assert WeaknessType.SINGLE_PATH_DOMINANCE not in types

    # ------------------------------------------------------------------ #
    # 4. shallow_depth
    # ------------------------------------------------------------------ #

    def test_shallow_depth_detected(self):
        """Trigger when max_degeneracy <= 1 and total_paths <= len(anchor_ids)."""
        trace = _clean_trace(
            bundle_summary={
                "fiber_count": 2,
                "total_paths": 2,   # == len(anchor_ids)
                "max_degeneracy": 1,
                "fact_ids": ["f1", "f2"],
            },
            anchor_ids=["a1", "a2"],
        )
        result = TraceCritic().analyze(trace)
        types = [w.weakness_type for w in result]
        assert WeaknessType.SHALLOW_DEPTH in types

    def test_shallow_depth_severity_is_0_6(self):
        """Severity is always 0.6."""
        trace = _clean_trace(
            bundle_summary={
                "fiber_count": 1,
                "total_paths": 1,
                "max_degeneracy": 0,
                "fact_ids": ["f1"],
            },
            anchor_ids=["a1"],
        )
        result = TraceCritic().analyze(trace)
        w = next(x for x in result if x.weakness_type == WeaknessType.SHALLOW_DEPTH)
        assert w.severity == 0.6
        assert w.location == "retrieval"
        assert w.suggested_repair_type == "increase_retrieval_depth"

    def test_shallow_depth_not_detected_when_paths_exceed_anchors(self):
        """NOT triggered when total_paths > len(anchor_ids)."""
        trace = _clean_trace(
            bundle_summary={
                "fiber_count": 3,
                "total_paths": 5,
                "max_degeneracy": 1,
                "fact_ids": ["f1", "f2"],
            },
            anchor_ids=["a1", "a2"],
        )
        result = TraceCritic().analyze(trace)
        types = [w.weakness_type for w in result]
        assert WeaknessType.SHALLOW_DEPTH not in types

    def test_shallow_depth_not_detected_when_max_degeneracy_high(self):
        """NOT triggered when max_degeneracy > 1."""
        trace = _clean_trace(
            bundle_summary={
                "fiber_count": 3,
                "total_paths": 2,
                "max_degeneracy": 2,
                "fact_ids": ["f1", "f2"],
            },
            anchor_ids=["a1", "a2"],
        )
        result = TraceCritic().analyze(trace)
        types = [w.weakness_type for w in result]
        assert WeaknessType.SHALLOW_DEPTH not in types

    # ------------------------------------------------------------------ #
    # 5. low_evidence_diversity
    # ------------------------------------------------------------------ #

    def test_low_evidence_diversity_detected(self):
        """Trigger when anchor_ids < 3 and candidates > 5."""
        trace = _clean_trace(
            anchor_ids=["a1", "a2"],
            candidates=[("c1", 1, 0.9), ("c2", 2, 0.8), ("c3", 3, 0.7),
                        ("c4", 4, 0.6), ("c5", 5, 0.5), ("c6", 6, 0.4)],
        )
        result = TraceCritic().analyze(trace)
        types = [w.weakness_type for w in result]
        assert WeaknessType.LOW_EVIDENCE_DIVERSITY in types

    def test_low_evidence_diversity_severity(self):
        """Severity = 1.0 - (num_anchors / num_candidates)."""
        anchor_ids = ["a1"]
        candidates = [("c%d" % i, i, 0.9) for i in range(10)]
        trace = _clean_trace(anchor_ids=anchor_ids, candidates=candidates)
        result = TraceCritic().analyze(trace)
        w = next(x for x in result if x.weakness_type == WeaknessType.LOW_EVIDENCE_DIVERSITY)
        expected_severity = 1.0 - (1 / 10)
        assert abs(w.severity - expected_severity) < 1e-9
        assert w.location == "retrieval"
        assert w.suggested_repair_type == "lower_anchor_threshold"

    def test_low_evidence_diversity_not_detected_when_anchors_sufficient(self):
        """NOT triggered when anchor_ids >= 3."""
        trace = _clean_trace(
            anchor_ids=["a1", "a2", "a3"],
            candidates=[("c%d" % i, i, 0.9) for i in range(10)],
        )
        result = TraceCritic().analyze(trace)
        types = [w.weakness_type for w in result]
        assert WeaknessType.LOW_EVIDENCE_DIVERSITY not in types

    def test_low_evidence_diversity_not_detected_when_few_candidates(self):
        """NOT triggered when candidates <= 5."""
        trace = _clean_trace(
            anchor_ids=["a1"],
            candidates=[("c1", 1, 0.9), ("c2", 2, 0.8)],
        )
        result = TraceCritic().analyze(trace)
        types = [w.weakness_type for w in result]
        assert WeaknessType.LOW_EVIDENCE_DIVERSITY not in types

    # ------------------------------------------------------------------ #
    # 6. hypothetical_promoted_silently
    # ------------------------------------------------------------------ #

    def test_hypothetical_promoted_silently_detected(self):
        """Trigger when escape fired, stability ok, tc >= 0.7, metadata has HYPOTHETICAL."""
        trace = _clean_trace(
            lyapunov_dimensions={
                "temporal_consistency": 0.8,
                "contradiction_score": 0.1,
                "path_diversity": 0.8,
                "degeneracy": 0.5,
                "pattern_lock_score": 0.5,
            },
            escape_triggered=True,
            stability_status="stable",
            metadata={"converged_edge_origins": "HYPOTHETICAL:edge42"},
        )
        result = TraceCritic().analyze(trace)
        types = [w.weakness_type for w in result]
        assert WeaknessType.HYPOTHETICAL_PROMOTED_SILENTLY in types

    def test_hypothetical_promoted_silently_severity_and_fields(self):
        """Severity is 0.8, location convergence, repair demote_hypothetical."""
        trace = _clean_trace(
            lyapunov_dimensions={
                "temporal_consistency": 0.8,
                "contradiction_score": 0.1,
                "path_diversity": 0.8,
                "degeneracy": 0.5,
                "pattern_lock_score": 0.5,
            },
            escape_triggered=True,
            stability_status="marginal",
            metadata={"some_key": "HYPOTHETICAL"},
        )
        result = TraceCritic().analyze(trace)
        w = next(x for x in result if x.weakness_type == WeaknessType.HYPOTHETICAL_PROMOTED_SILENTLY)
        assert w.severity == 0.8
        assert w.location == "convergence"
        assert w.suggested_repair_type == "demote_hypothetical"

    def test_hypothetical_not_detected_without_metadata_marker(self):
        """NOT triggered when metadata has no HYPOTHETICAL value."""
        trace = _clean_trace(
            lyapunov_dimensions={
                "temporal_consistency": 0.8,
                "contradiction_score": 0.1,
                "path_diversity": 0.8,
                "degeneracy": 0.5,
                "pattern_lock_score": 0.5,
            },
            escape_triggered=True,
            stability_status="stable",
            metadata={"converged_edge_origins": "NORMAL:edge42"},
        )
        result = TraceCritic().analyze(trace)
        types = [w.weakness_type for w in result]
        assert WeaknessType.HYPOTHETICAL_PROMOTED_SILENTLY not in types

    def test_hypothetical_detected_even_without_escape_triggered(self):
        """Triggered when metadata has HYPOTHETICAL, regardless of escape_triggered."""
        trace = _clean_trace(
            lyapunov_dimensions={
                "temporal_consistency": 0.8,
                "contradiction_score": 0.1,
                "path_diversity": 0.8,
                "degeneracy": 0.5,
                "pattern_lock_score": 0.5,
            },
            escape_triggered=False,
            stability_status="stable",
            metadata={"converged_edge_origins": "HYPOTHETICAL:edge42"},
        )
        result = TraceCritic().analyze(trace)
        types = [w.weakness_type for w in result]
        assert WeaknessType.HYPOTHETICAL_PROMOTED_SILENTLY in types

    def test_hypothetical_detected_with_low_temporal_consistency(self):
        """Triggered when metadata has HYPOTHETICAL, regardless of temporal_consistency."""
        trace = _clean_trace(
            lyapunov_dimensions={
                "temporal_consistency": 0.65,
                "contradiction_score": 0.1,
                "path_diversity": 0.8,
                "degeneracy": 0.5,
                "pattern_lock_score": 0.5,
            },
            escape_triggered=True,
            stability_status="stable",
            metadata={"converged_edge_origins": "HYPOTHETICAL:edge42"},
        )
        result = TraceCritic().analyze(trace)
        types = [w.weakness_type for w in result]
        assert WeaknessType.HYPOTHETICAL_PROMOTED_SILENTLY in types

    # ------------------------------------------------------------------ #
    # Sorting & deduplication
    # ------------------------------------------------------------------ #

    def test_results_sorted_by_severity_descending(self):
        """Results must be sorted by severity descending."""
        # Force multiple weaknesses: temporal_consistency_low (sev=0.6)
        # + contradiction_unresolved (sev=0.5) + single_path_dominance (sev=0.85)
        trace = _clean_trace(
            lyapunov_dimensions={
                "temporal_consistency": 0.4,   # → temporal_consistency_low, sev=0.6
                "contradiction_score": 0.5,    # → contradiction_unresolved, sev=0.5
                "path_diversity": 0.8,
                "degeneracy": 0.5,
                "pattern_lock_score": 0.85,    # → single_path_dominance, sev=0.85
            },
            escape_triggered=False,
            dialectic_result_summary=None,
        )
        result = TraceCritic().analyze(trace)
        severities = [w.severity for w in result]
        assert severities == sorted(severities, reverse=True)

    def test_no_duplicate_weakness_types(self):
        """Returned list must not contain duplicate weakness types."""
        # A trace that could trigger multiple weaknesses.
        trace = _clean_trace(
            lyapunov_dimensions={
                "temporal_consistency": 0.4,
                "contradiction_score": 0.5,
                "path_diversity": 0.8,
                "degeneracy": 0.5,
                "pattern_lock_score": 0.85,
            },
            escape_triggered=False,
            dialectic_result_summary=None,
            anchor_ids=["a1"],
            candidates=[("c%d" % i, i, 0.9) for i in range(10)],
            bundle_summary={
                "fiber_count": 1,
                "total_paths": 1,
                "max_degeneracy": 0,
                "fact_ids": ["f1"],
            },
        )
        result = TraceCritic().analyze(trace)
        type_list = [w.weakness_type for w in result]
        assert len(type_list) == len(set(type_list))

    def test_clean_trace_returns_empty_list(self):
        """A trace with no triggers should return an empty list."""
        trace = _clean_trace()
        result = TraceCritic().analyze(trace)
        assert result == []


class TestTraceCriticIteration:
    """Tests for TraceCritic.analyze_iteration()."""

    # ------------------------------------------------------------------ #
    # Early returns
    # ------------------------------------------------------------------ #

    def test_returns_empty_list_when_iteration_zero(self):
        """Returns [] immediately if iteration == 0."""
        trace = QueryTrace(iteration=0, stability_score=0.8)
        prior_traces = [
            QueryTrace(iteration=0, stability_score=0.7),
        ]
        critic = TraceCritic()
        result = critic.analyze_iteration(trace, iteration=0, prior_traces=prior_traces)
        assert result == []

    def test_returns_empty_list_when_prior_traces_empty(self):
        """Returns [] immediately if prior_traces is empty."""
        trace = QueryTrace(iteration=1, stability_score=0.8)
        critic = TraceCritic()
        result = critic.analyze_iteration(trace, iteration=1, prior_traces=[])
        assert result == []

    def test_returns_empty_list_when_both_zero_and_empty(self):
        """Returns [] if both iteration == 0 and prior_traces is empty."""
        trace = QueryTrace(iteration=0, stability_score=0.8)
        critic = TraceCritic()
        result = critic.analyze_iteration(trace, iteration=0, prior_traces=[])
        assert result == []

    # ------------------------------------------------------------------ #
    # 1. improvement_stall
    # ------------------------------------------------------------------ #

    def test_improvement_stall_detected_when_gain_below_threshold(self):
        """Detects improvement_stall when gain < 0.05."""
        prior_trace = QueryTrace(iteration=0, stability_score=0.80)
        trace = QueryTrace(iteration=1, stability_score=0.82)  # gain = 0.02 < 0.05
        critic = TraceCritic()
        result = critic.analyze_iteration(trace, iteration=1, prior_traces=[prior_trace])

        types = [w.weakness_type for w in result]
        assert WeaknessType.IMPROVEMENT_STALL in types

    def test_improvement_stall_severity_is_0_7(self):
        """Severity is always 0.7 for improvement_stall."""
        prior_trace = QueryTrace(iteration=0, stability_score=0.80)
        trace = QueryTrace(iteration=1, stability_score=0.82)
        critic = TraceCritic()
        result = critic.analyze_iteration(trace, iteration=1, prior_traces=[prior_trace])

        w = next(x for x in result if x.weakness_type == WeaknessType.IMPROVEMENT_STALL)
        assert w.severity == 0.7
        assert w.location == "recursive_loop"
        assert w.suggested_repair_type == "increase_retrieval_depth"

    def test_improvement_stall_description_includes_gain(self):
        """Description includes actual gain value."""
        prior_trace = QueryTrace(iteration=0, stability_score=0.80)
        trace = QueryTrace(iteration=1, stability_score=0.83)  # gain = 0.03
        critic = TraceCritic()
        result = critic.analyze_iteration(trace, iteration=1, prior_traces=[prior_trace])

        w = next(x for x in result if x.weakness_type == WeaknessType.IMPROVEMENT_STALL)
        assert "0.030" in w.description

    def test_improvement_stall_not_detected_when_gain_at_threshold(self):
        """NOT detected when gain == 0.05 (boundary)."""
        prior_trace = QueryTrace(iteration=0, stability_score=0.80)
        trace = QueryTrace(iteration=1, stability_score=0.85001)  # gain ≈ 0.05001, not < 0.05
        critic = TraceCritic()
        result = critic.analyze_iteration(trace, iteration=1, prior_traces=[prior_trace])

        types = [w.weakness_type for w in result]
        assert WeaknessType.IMPROVEMENT_STALL not in types

    def test_improvement_stall_not_detected_when_gain_above_threshold(self):
        """NOT detected when gain > 0.05."""
        prior_trace = QueryTrace(iteration=0, stability_score=0.80)
        trace = QueryTrace(iteration=1, stability_score=0.88)  # gain = 0.08 > 0.05
        critic = TraceCritic()
        result = critic.analyze_iteration(trace, iteration=1, prior_traces=[prior_trace])

        types = [w.weakness_type for w in result]
        assert WeaknessType.IMPROVEMENT_STALL not in types

    def test_improvement_stall_with_negative_gain(self):
        """Detected even when gain is negative (regression)."""
        prior_trace = QueryTrace(iteration=0, stability_score=0.80)
        trace = QueryTrace(iteration=1, stability_score=0.75)  # gain = -0.05 < 0.05
        critic = TraceCritic()
        result = critic.analyze_iteration(trace, iteration=1, prior_traces=[prior_trace])

        types = [w.weakness_type for w in result]
        assert WeaknessType.IMPROVEMENT_STALL in types

    # ------------------------------------------------------------------ #
    # 2. discovery_gain_zero
    # ------------------------------------------------------------------ #

    def test_discovery_gain_zero_detected_when_repair_strength_low(self):
        """Detects discovery_gain_zero when repair_strength < 0.1."""
        prior_trace = QueryTrace(iteration=0, stability_score=0.8)
        trace = QueryTrace(
            iteration=1,
            stability_score=0.85,
            discovery_result_summary={"repair_strength": 0.05},
        )
        critic = TraceCritic()
        result = critic.analyze_iteration(trace, iteration=1, prior_traces=[prior_trace])

        types = [w.weakness_type for w in result]
        assert WeaknessType.DISCOVERY_GAIN_ZERO in types

    def test_discovery_gain_zero_severity_is_0_8(self):
        """Severity is always 0.8 for discovery_gain_zero."""
        prior_trace = QueryTrace(iteration=0, stability_score=0.8)
        trace = QueryTrace(
            iteration=1,
            stability_score=0.85,
            discovery_result_summary={"repair_strength": 0.05},
        )
        critic = TraceCritic()
        result = critic.analyze_iteration(trace, iteration=1, prior_traces=[prior_trace])

        w = next(x for x in result if x.weakness_type == WeaknessType.DISCOVERY_GAIN_ZERO)
        assert w.severity == 0.8
        assert w.location == "discovery"
        assert w.suggested_repair_type == "reset_to_low_freq_region"

    def test_discovery_gain_zero_description_includes_strength(self):
        """Description includes actual repair_strength value."""
        prior_trace = QueryTrace(iteration=0, stability_score=0.8)
        trace = QueryTrace(
            iteration=1,
            stability_score=0.85,
            discovery_result_summary={"repair_strength": 0.075},
        )
        critic = TraceCritic()
        result = critic.analyze_iteration(trace, iteration=1, prior_traces=[prior_trace])

        w = next(x for x in result if x.weakness_type == WeaknessType.DISCOVERY_GAIN_ZERO)
        assert "0.075" in w.description

    def test_discovery_gain_zero_not_detected_when_repair_strength_at_threshold(self):
        """NOT detected when repair_strength == 0.1 (boundary)."""
        prior_trace = QueryTrace(iteration=0, stability_score=0.8)
        trace = QueryTrace(
            iteration=1,
            stability_score=0.85,
            discovery_result_summary={"repair_strength": 0.1},
        )
        critic = TraceCritic()
        result = critic.analyze_iteration(trace, iteration=1, prior_traces=[prior_trace])

        types = [w.weakness_type for w in result]
        assert WeaknessType.DISCOVERY_GAIN_ZERO not in types

    def test_discovery_gain_zero_not_detected_when_repair_strength_high(self):
        """NOT detected when repair_strength >= 0.1."""
        prior_trace = QueryTrace(iteration=0, stability_score=0.8)
        trace = QueryTrace(
            iteration=1,
            stability_score=0.85,
            discovery_result_summary={"repair_strength": 0.5},
        )
        critic = TraceCritic()
        result = critic.analyze_iteration(trace, iteration=1, prior_traces=[prior_trace])

        types = [w.weakness_type for w in result]
        assert WeaknessType.DISCOVERY_GAIN_ZERO not in types

    def test_discovery_gain_zero_not_detected_when_discovery_result_none(self):
        """NOT detected when discovery_result_summary is None."""
        prior_trace = QueryTrace(iteration=0, stability_score=0.8)
        trace = QueryTrace(
            iteration=1,
            stability_score=0.85,
            discovery_result_summary=None,
        )
        critic = TraceCritic()
        result = critic.analyze_iteration(trace, iteration=1, prior_traces=[prior_trace])

        types = [w.weakness_type for w in result]
        assert WeaknessType.DISCOVERY_GAIN_ZERO not in types

    def test_discovery_gain_zero_with_default_repair_strength(self):
        """When repair_strength key missing, defaults to 1.0 (no weakness)."""
        prior_trace = QueryTrace(iteration=0, stability_score=0.8)
        trace = QueryTrace(
            iteration=1,
            stability_score=0.85,
            discovery_result_summary={"some_other_key": "value"},
        )
        critic = TraceCritic()
        result = critic.analyze_iteration(trace, iteration=1, prior_traces=[prior_trace])

        types = [w.weakness_type for w in result]
        assert WeaknessType.DISCOVERY_GAIN_ZERO not in types

    # ------------------------------------------------------------------ #
    # 3. oscillation
    # ------------------------------------------------------------------ #

    def test_oscillation_detected_with_three_iteration_pattern(self):
        """Detects oscillation when stability goes UP then DOWN."""
        # iteration 0: stability = 0.70
        # iteration 1: stability = 0.75 (up)
        # iteration 2: stability = 0.71 (down by > 0.03)
        iter0_trace = QueryTrace(iteration=0, stability_score=0.70)
        iter1_trace = QueryTrace(iteration=1, stability_score=0.75)
        iter2_trace = QueryTrace(iteration=2, stability_score=0.71)

        critic = TraceCritic()
        result = critic.analyze_iteration(
            iter2_trace, iteration=2, prior_traces=[iter0_trace, iter1_trace]
        )

        types = [w.weakness_type for w in result]
        assert WeaknessType.OSCILLATION in types

    def test_oscillation_severity_equals_drop(self):
        """Severity = |curr - prev| (absolute drop)."""
        iter0_trace = QueryTrace(iteration=0, stability_score=0.70)
        iter1_trace = QueryTrace(iteration=1, stability_score=0.80)
        iter2_trace = QueryTrace(iteration=2, stability_score=0.71)

        critic = TraceCritic()
        result = critic.analyze_iteration(
            iter2_trace, iteration=2, prior_traces=[iter0_trace, iter1_trace]
        )

        w = next(x for x in result if x.weakness_type == WeaknessType.OSCILLATION)
        expected_severity = abs(0.71 - 0.80)  # 0.09
        assert abs(w.severity - expected_severity) < 1e-9
        assert w.location == "recursive_loop"
        assert w.suggested_repair_type == "widen_temporal_window"

    def test_oscillation_description_includes_three_scores(self):
        """Description includes all three stability scores."""
        iter0_trace = QueryTrace(iteration=0, stability_score=0.70)
        iter1_trace = QueryTrace(iteration=1, stability_score=0.80)
        iter2_trace = QueryTrace(iteration=2, stability_score=0.71)

        critic = TraceCritic()
        result = critic.analyze_iteration(
            iter2_trace, iteration=2, prior_traces=[iter0_trace, iter1_trace]
        )

        w = next(x for x in result if x.weakness_type == WeaknessType.OSCILLATION)
        assert "0.70" in w.description or "0.700" in w.description
        assert "0.80" in w.description or "0.800" in w.description
        assert "0.71" in w.description or "0.710" in w.description

    def test_oscillation_not_detected_when_iteration_less_than_2(self):
        """NOT detected when iteration < 2."""
        iter0_trace = QueryTrace(iteration=0, stability_score=0.70)
        iter1_trace = QueryTrace(iteration=1, stability_score=0.80)

        critic = TraceCritic()
        result = critic.analyze_iteration(
            iter1_trace, iteration=1, prior_traces=[iter0_trace]
        )

        types = [w.weakness_type for w in result]
        assert WeaknessType.OSCILLATION not in types

    def test_oscillation_not_detected_when_prior_traces_short(self):
        """NOT detected when len(prior_traces) < 2."""
        iter0_trace = QueryTrace(iteration=0, stability_score=0.70)
        iter2_trace = QueryTrace(iteration=2, stability_score=0.71)

        critic = TraceCritic()
        # Only one prior trace; need at least 2
        result = critic.analyze_iteration(
            iter2_trace, iteration=2, prior_traces=[iter0_trace]
        )

        types = [w.weakness_type for w in result]
        assert WeaknessType.OSCILLATION not in types

    def test_oscillation_not_detected_when_monotonic_up(self):
        """NOT detected when stability goes UP consistently."""
        iter0_trace = QueryTrace(iteration=0, stability_score=0.70)
        iter1_trace = QueryTrace(iteration=1, stability_score=0.75)
        iter2_trace = QueryTrace(iteration=2, stability_score=0.85)  # still going up

        critic = TraceCritic()
        result = critic.analyze_iteration(
            iter2_trace, iteration=2, prior_traces=[iter0_trace, iter1_trace]
        )

        types = [w.weakness_type for w in result]
        assert WeaknessType.OSCILLATION not in types

    def test_oscillation_not_detected_when_first_step_down(self):
        """NOT detected when first step (0→1) was DOWN."""
        iter0_trace = QueryTrace(iteration=0, stability_score=0.80)
        iter1_trace = QueryTrace(iteration=1, stability_score=0.75)  # down
        iter2_trace = QueryTrace(iteration=2, stability_score=0.70)  # down again

        critic = TraceCritic()
        result = critic.analyze_iteration(
            iter2_trace, iteration=2, prior_traces=[iter0_trace, iter1_trace]
        )

        types = [w.weakness_type for w in result]
        assert WeaknessType.OSCILLATION not in types

    def test_oscillation_not_detected_when_second_drop_too_small(self):
        """NOT detected when second drop is <= 0.03."""
        iter0_trace = QueryTrace(iteration=0, stability_score=0.70)
        iter1_trace = QueryTrace(iteration=1, stability_score=0.80)
        iter2_trace = QueryTrace(iteration=2, stability_score=0.770)  # drop = 0.03, not > 0.03

        critic = TraceCritic()
        result = critic.analyze_iteration(
            iter2_trace, iteration=2, prior_traces=[iter0_trace, iter1_trace]
        )

        types = [w.weakness_type for w in result]
        assert WeaknessType.OSCILLATION not in types

    # ------------------------------------------------------------------ #
    # Sorting & deduplication
    # ------------------------------------------------------------------ #

    def test_results_sorted_by_severity_descending(self):
        """Results must be sorted by severity descending."""
        # Create scenario that triggers both improvement_stall (0.7) and
        # discovery_gain_zero (0.8), so discovery_gain_zero should come first.
        iter0_trace = QueryTrace(iteration=0, stability_score=0.80)
        iter1_trace = QueryTrace(
            iteration=1,
            stability_score=0.82,  # gain = 0.02 < 0.05 → improvement_stall (sev=0.7)
            discovery_result_summary={"repair_strength": 0.05},  # → discovery_gain_zero (sev=0.8)
        )

        critic = TraceCritic()
        result = critic.analyze_iteration(iter1_trace, iteration=1, prior_traces=[iter0_trace])

        severities = [w.severity for w in result]
        assert severities == sorted(severities, reverse=True)
        # First should be discovery_gain_zero (0.8), then improvement_stall (0.7)
        assert result[0].weakness_type == WeaknessType.DISCOVERY_GAIN_ZERO
        assert result[1].weakness_type == WeaknessType.IMPROVEMENT_STALL

    def test_no_duplicate_weakness_types_in_iteration_analysis(self):
        """Returned list must not contain duplicate weakness types."""
        iter0_trace = QueryTrace(iteration=0, stability_score=0.80)
        iter1_trace = QueryTrace(
            iteration=1,
            stability_score=0.82,
            discovery_result_summary={"repair_strength": 0.05},
        )

        critic = TraceCritic()
        result = critic.analyze_iteration(iter1_trace, iteration=1, prior_traces=[iter0_trace])

        type_list = [w.weakness_type for w in result]
        assert len(type_list) == len(set(type_list))

    def test_returns_empty_list_when_no_weaknesses_detected(self):
        """Returns [] when no cross-iteration weaknesses are found."""
        iter0_trace = QueryTrace(iteration=0, stability_score=0.70)
        iter1_trace = QueryTrace(
            iteration=1,
            stability_score=0.80,  # gain = 0.10 >= 0.05, no improvement_stall
            discovery_result_summary={"repair_strength": 0.5},  # >= 0.1, no discovery_gain_zero
        )

        critic = TraceCritic()
        result = critic.analyze_iteration(iter1_trace, iteration=1, prior_traces=[iter0_trace])

        assert result == []

    # ------------------------------------------------------------------ #
    # Real-world scenarios
    # ------------------------------------------------------------------ #

    def test_all_three_weaknesses_together(self):
        """All three weaknesses can be detected simultaneously."""
        iter0_trace = QueryTrace(iteration=0, stability_score=0.70)
        iter1_trace = QueryTrace(iteration=1, stability_score=0.75)
        iter2_trace = QueryTrace(
            iteration=2,
            stability_score=0.71,  # oscillation: 0.70 → 0.75 → 0.71
            discovery_result_summary={"repair_strength": 0.05},  # discovery_gain_zero
        )
        # improvement_stall: 0.71 - 0.75 = -0.04 < 0.05

        critic = TraceCritic()
        result = critic.analyze_iteration(
            iter2_trace, iteration=2, prior_traces=[iter0_trace, iter1_trace]
        )

        types = [w.weakness_type for w in result]
        assert WeaknessType.OSCILLATION in types
        assert WeaknessType.DISCOVERY_GAIN_ZERO in types
        assert WeaknessType.IMPROVEMENT_STALL in types
        assert len(result) == 3


# ---------------------------------------------------------------------------
# Helper: build a session of "clean" traces for CrossQueryCritic tests
# ---------------------------------------------------------------------------

def _make_trace(
    fact_ids=None,
    anchor_ids=None,
    escape_triggered=False,
    stability_score=0.9,
    lyapunov_dims=None,
    dialectic_summary=None,
) -> QueryTrace:
    """Return a QueryTrace suitable for session-level analysis."""
    if fact_ids is None:
        fact_ids = ["f1", "f2", "f3"]
    if anchor_ids is None:
        anchor_ids = ["anch1", "anch2"]
    if lyapunov_dims is None:
        lyapunov_dims = {
            "temporal_consistency": 0.9,
            "contradiction_score": 0.1,
            "pattern_lock_score": 0.3,
        }
    return QueryTrace(
        bundle_summary={"fact_ids": fact_ids},
        anchor_ids=anchor_ids,
        escape_triggered=escape_triggered,
        stability_score=stability_score,
        lyapunov_dimensions=lyapunov_dims,
        dialectic_result_summary=dialectic_summary,
    )


# ---------------------------------------------------------------------------
# TestWeaknessReport
# ---------------------------------------------------------------------------

class TestWeaknessReport:
    """Tests for WeaknessReport dataclass."""

    def _make_weakness(self, wtype=WeaknessType.TEMPORAL_CONSISTENCY_LOW, severity=0.5):
        return TraceWeakness(
            weakness_type=wtype,
            severity=severity,
            location="test",
            description="test",
            suggested_repair_type="test",
        )

    # ------------------------------------------------------------------ #
    # Construction
    # ------------------------------------------------------------------ #

    def test_empty_report(self):
        """WeaknessReport with no weaknesses has total_severity=0.0."""
        report = WeaknessReport(trace_id="t1")
        assert report.trace_id == "t1"
        assert report.per_trace_weaknesses == []
        assert report.session_weaknesses == []
        assert report.total_severity == 0.0

    def test_total_severity_computed_from_all_weaknesses(self):
        """total_severity is mean of all severities."""
        w1 = self._make_weakness(WeaknessType.TEMPORAL_CONSISTENCY_LOW, severity=0.8)
        w2 = self._make_weakness(WeaknessType.NOVELTY_DEFICIT, severity=0.4)
        report = WeaknessReport(
            trace_id="t1",
            per_trace_weaknesses=[w1],
            session_weaknesses=[w2],
        )
        assert abs(report.total_severity - 0.6) < 1e-9

    def test_total_severity_only_per_trace(self):
        """total_severity works with only per_trace_weaknesses."""
        w1 = self._make_weakness(severity=1.0)
        w2 = self._make_weakness(WeaknessType.CONTRADICTION_UNRESOLVED, severity=0.5)
        report = WeaknessReport(trace_id="t1", per_trace_weaknesses=[w1, w2])
        assert abs(report.total_severity - 0.75) < 1e-9

    def test_total_severity_only_session(self):
        """total_severity works with only session_weaknesses."""
        w = self._make_weakness(severity=0.6)
        report = WeaknessReport(trace_id="t1", session_weaknesses=[w])
        assert abs(report.total_severity - 0.6) < 1e-9

    # ------------------------------------------------------------------ #
    # all_weaknesses property
    # ------------------------------------------------------------------ #

    def test_all_weaknesses_combined_and_sorted(self):
        """all_weaknesses = per_trace + session, sorted by severity descending."""
        w1 = self._make_weakness(WeaknessType.TEMPORAL_CONSISTENCY_LOW, severity=0.3)
        w2 = self._make_weakness(WeaknessType.NOVELTY_DEFICIT, severity=0.9)
        w3 = self._make_weakness(WeaknessType.COVERAGE_BIAS, severity=0.6)
        report = WeaknessReport(
            trace_id="t1",
            per_trace_weaknesses=[w1, w3],
            session_weaknesses=[w2],
        )
        all_w = report.all_weaknesses
        assert len(all_w) == 3
        severities = [w.severity for w in all_w]
        assert severities == sorted(severities, reverse=True)

    def test_all_weaknesses_empty(self):
        """all_weaknesses returns [] when no weaknesses exist."""
        report = WeaknessReport(trace_id="t1")
        assert report.all_weaknesses == []

    # ------------------------------------------------------------------ #
    # has_weaknesses property
    # ------------------------------------------------------------------ #

    def test_has_weaknesses_false_when_empty(self):
        """has_weaknesses is False when no weaknesses."""
        report = WeaknessReport(trace_id="t1")
        assert report.has_weaknesses is False

    def test_has_weaknesses_true_with_per_trace(self):
        """has_weaknesses is True when per_trace_weaknesses exist."""
        w = self._make_weakness()
        report = WeaknessReport(trace_id="t1", per_trace_weaknesses=[w])
        assert report.has_weaknesses is True

    def test_has_weaknesses_true_with_session(self):
        """has_weaknesses is True when session_weaknesses exist."""
        w = self._make_weakness()
        report = WeaknessReport(trace_id="t1", session_weaknesses=[w])
        assert report.has_weaknesses is True

    # ------------------------------------------------------------------ #
    # worst_weakness property
    # ------------------------------------------------------------------ #

    def test_worst_weakness_none_when_empty(self):
        """worst_weakness is None when no weaknesses exist."""
        report = WeaknessReport(trace_id="t1")
        assert report.worst_weakness is None

    def test_worst_weakness_highest_severity(self):
        """worst_weakness returns the highest-severity weakness."""
        w1 = self._make_weakness(WeaknessType.TEMPORAL_CONSISTENCY_LOW, severity=0.3)
        w2 = self._make_weakness(WeaknessType.NOVELTY_DEFICIT, severity=0.9)
        w3 = self._make_weakness(WeaknessType.COVERAGE_BIAS, severity=0.6)
        report = WeaknessReport(
            trace_id="t1",
            per_trace_weaknesses=[w1, w3],
            session_weaknesses=[w2],
        )
        worst = report.worst_weakness
        assert worst is not None
        assert worst.weakness_type == WeaknessType.NOVELTY_DEFICIT
        assert worst.severity == 0.9

    # ------------------------------------------------------------------ #
    # Serialization round-trip
    # ------------------------------------------------------------------ #

    def test_to_dict_contains_expected_keys(self):
        """to_dict() contains trace_id, per_trace_weaknesses, session_weaknesses, total_severity."""
        report = WeaknessReport(trace_id="t1")
        d = report.to_dict()
        assert "trace_id" in d
        assert "per_trace_weaknesses" in d
        assert "session_weaknesses" in d
        assert "total_severity" in d

    def test_roundtrip_empty(self):
        """Empty WeaknessReport survives to_dict/from_dict round-trip."""
        original = WeaknessReport(trace_id="abc-123")
        restored = WeaknessReport.from_dict(original.to_dict())
        assert restored.trace_id == "abc-123"
        assert restored.per_trace_weaknesses == []
        assert restored.session_weaknesses == []
        assert restored.total_severity == 0.0

    def test_roundtrip_with_weaknesses(self):
        """WeaknessReport with weaknesses survives round-trip."""
        w1 = self._make_weakness(WeaknessType.TEMPORAL_CONSISTENCY_LOW, severity=0.7)
        w2 = self._make_weakness(WeaknessType.NOVELTY_DEFICIT, severity=0.5)
        original = WeaknessReport(
            trace_id="xyz",
            per_trace_weaknesses=[w1],
            session_weaknesses=[w2],
        )
        restored = WeaknessReport.from_dict(original.to_dict())
        assert restored.trace_id == "xyz"
        assert len(restored.per_trace_weaknesses) == 1
        assert len(restored.session_weaknesses) == 1
        assert restored.per_trace_weaknesses[0].weakness_type == WeaknessType.TEMPORAL_CONSISTENCY_LOW
        assert restored.session_weaknesses[0].weakness_type == WeaknessType.NOVELTY_DEFICIT
        assert abs(restored.total_severity - original.total_severity) < 1e-9


# ---------------------------------------------------------------------------
# TestCrossQueryCritic
# ---------------------------------------------------------------------------

class TestCrossQueryCritic:
    """Tests for CrossQueryCritic.analyze_session()."""

    # ------------------------------------------------------------------ #
    # Edge cases
    # ------------------------------------------------------------------ #

    def test_empty_traces_returns_empty_list(self):
        """analyze_session([]) returns []."""
        critic = CrossQueryCritic()
        assert critic.analyze_session([]) == []

    def test_too_few_traces_returns_empty_list(self):
        """analyze_session with 4 traces returns [] (minimum is 5 for any check)."""
        traces = [_make_trace() for _ in range(4)]
        critic = CrossQueryCritic()
        result = critic.analyze_session(traces)
        # novelty_deficit and coverage_bias require >= 5
        # self_repetition requires >= 3 but also needs dialectic summaries
        # escape_never_triggers requires >= 10
        # learning_stagnation requires >= 8
        # With 4 traces and no dialectic, should be empty
        assert result == []

    # ------------------------------------------------------------------ #
    # 1. novelty_deficit
    # ------------------------------------------------------------------ #

    def test_novelty_deficit_detected(self):
        """Trigger: >=5 traces, same fact_ids appear in 80%+ of traces."""
        # 5 traces all sharing fact "shared_f" plus some unique ones
        traces = [
            _make_trace(fact_ids=["shared_f", f"unique_{i}"]) for i in range(5)
        ]
        critic = CrossQueryCritic()
        result = critic.analyze_session(traces)
        types = [w.weakness_type for w in result]
        assert WeaknessType.NOVELTY_DEFICIT in types

    def test_novelty_deficit_severity(self):
        """Severity = overused_count / all_unique_fact_ids."""
        # 5 traces, all have "shared_f" (appears in 100% > 80%), each has a unique fact
        traces = [
            _make_trace(fact_ids=["shared_f", f"u{i}"]) for i in range(5)
        ]
        critic = CrossQueryCritic()
        result = critic.analyze_session(traces)
        w = next(x for x in result if x.weakness_type == WeaknessType.NOVELTY_DEFICIT)
        # 1 overused (shared_f) out of 6 unique facts total
        assert abs(w.severity - 1 / 6) < 1e-9
        assert w.location == "session"
        assert w.suggested_repair_type == "reset_to_low_freq_region"

    def test_novelty_deficit_not_detected_below_threshold(self):
        """NOT triggered when no fact appears in >= 80% of traces."""
        # 5 traces, each with completely different fact_ids
        traces = [
            _make_trace(fact_ids=[f"f{i}_a", f"f{i}_b"]) for i in range(5)
        ]
        critic = CrossQueryCritic()
        result = critic.analyze_session(traces)
        types = [w.weakness_type for w in result]
        assert WeaknessType.NOVELTY_DEFICIT not in types

    def test_novelty_deficit_not_detected_with_fewer_than_5_traces(self):
        """NOT triggered with fewer than 5 traces."""
        traces = [_make_trace(fact_ids=["shared_f"]) for _ in range(4)]
        critic = CrossQueryCritic()
        result = critic.analyze_session(traces)
        types = [w.weakness_type for w in result]
        assert WeaknessType.NOVELTY_DEFICIT not in types

    def test_novelty_deficit_description_format(self):
        """Description includes count, pct, and trace count."""
        traces = [_make_trace(fact_ids=["shared_f"]) for _ in range(5)]
        critic = CrossQueryCritic()
        result = critic.analyze_session(traces)
        w = next(x for x in result if x.weakness_type == WeaknessType.NOVELTY_DEFICIT)
        assert "80%" in w.description
        assert "5" in w.description

    # ------------------------------------------------------------------ #
    # 2. coverage_bias
    # ------------------------------------------------------------------ #

    def test_coverage_bias_detected(self):
        """Trigger: >=5 traces, >=70% of anchor_ids share same 4-char prefix."""
        # All anchors start with "ABCD"
        traces = [
            _make_trace(anchor_ids=["ABCD1", "ABCD2", "ABCD3"]) for _ in range(5)
        ]
        critic = CrossQueryCritic()
        result = critic.analyze_session(traces)
        types = [w.weakness_type for w in result]
        assert WeaknessType.COVERAGE_BIAS in types

    def test_coverage_bias_severity_is_0_6(self):
        """Severity is always 0.6."""
        traces = [_make_trace(anchor_ids=["ABCD1", "ABCD2"]) for _ in range(5)]
        critic = CrossQueryCritic()
        result = critic.analyze_session(traces)
        w = next(x for x in result if x.weakness_type == WeaknessType.COVERAGE_BIAS)
        assert w.severity == 0.6
        assert w.location == "session"
        assert w.suggested_repair_type == "rotate_anchor_prefix"

    def test_coverage_bias_not_detected_below_threshold(self):
        """NOT triggered when diversity is sufficient (< 70% same prefix)."""
        # 5 traces, each 3 anchors: 1 with prefix ABCD, 2 with different
        traces = [
            _make_trace(anchor_ids=["ABCD1", "WXYZ1", "LMNO1"]) for _ in range(5)
        ]
        # 5 * 1/3 = 33% with ABCD prefix → not triggered
        critic = CrossQueryCritic()
        result = critic.analyze_session(traces)
        types = [w.weakness_type for w in result]
        assert WeaknessType.COVERAGE_BIAS not in types

    def test_coverage_bias_not_detected_with_fewer_than_5_traces(self):
        """NOT triggered with fewer than 5 traces."""
        traces = [_make_trace(anchor_ids=["ABCD1", "ABCD2"]) for _ in range(4)]
        critic = CrossQueryCritic()
        result = critic.analyze_session(traces)
        types = [w.weakness_type for w in result]
        assert WeaknessType.COVERAGE_BIAS not in types

    def test_coverage_bias_description_includes_prefix(self):
        """Description includes the dominant prefix."""
        traces = [_make_trace(anchor_ids=["PREF1", "PREF2"]) for _ in range(5)]
        critic = CrossQueryCritic()
        result = critic.analyze_session(traces)
        w = next(x for x in result if x.weakness_type == WeaknessType.COVERAGE_BIAS)
        assert "PREF" in w.description

    # ------------------------------------------------------------------ #
    # 3. self_repetition
    # ------------------------------------------------------------------ #

    def test_self_repetition_detected(self):
        """Trigger: >=3 traces, same converged_fact_id in > 50% of dialectic summaries."""
        # 4 traces, 3 of 4 converge on same fact → 75% > 50%
        traces = [
            _make_trace(dialectic_summary={"converged_fact_id": "repeated_f", "opposition_challenges": 1})
            for _ in range(3)
        ] + [
            _make_trace(dialectic_summary={"converged_fact_id": "other_f", "opposition_challenges": 1})
        ]
        critic = CrossQueryCritic()
        result = critic.analyze_session(traces)
        types = [w.weakness_type for w in result]
        assert WeaknessType.SELF_REPETITION in types

    def test_self_repetition_severity(self):
        """Severity = fraction of converged answers that repeat the dominant fact."""
        traces = [
            _make_trace(dialectic_summary={"converged_fact_id": "rep_f"})
            for _ in range(4)
        ]  # 100% repetition
        critic = CrossQueryCritic()
        result = critic.analyze_session(traces)
        w = next(x for x in result if x.weakness_type == WeaknessType.SELF_REPETITION)
        assert abs(w.severity - 1.0) < 1e-9
        assert w.location == "session"
        assert w.suggested_repair_type == "reset_to_low_freq_region"

    def test_self_repetition_not_detected_when_varied(self):
        """NOT triggered when no single converged fact dominates > 50%."""
        # 4 traces, each converges on a different fact → each 25%
        traces = [
            _make_trace(dialectic_summary={"converged_fact_id": f"fact_{i}"})
            for i in range(4)
        ]
        critic = CrossQueryCritic()
        result = critic.analyze_session(traces)
        types = [w.weakness_type for w in result]
        assert WeaknessType.SELF_REPETITION not in types

    def test_self_repetition_skipped_without_dialectic_summaries(self):
        """NOT triggered when no traces have dialectic_result_summary."""
        traces = [_make_trace(dialectic_summary=None) for _ in range(5)]
        critic = CrossQueryCritic()
        result = critic.analyze_session(traces)
        types = [w.weakness_type for w in result]
        assert WeaknessType.SELF_REPETITION not in types

    def test_self_repetition_not_detected_with_fewer_than_3_traces(self):
        """NOT triggered with fewer than 3 traces."""
        traces = [
            _make_trace(dialectic_summary={"converged_fact_id": "rep_f"})
            for _ in range(2)
        ]
        critic = CrossQueryCritic()
        result = critic.analyze_session(traces)
        types = [w.weakness_type for w in result]
        assert WeaknessType.SELF_REPETITION not in types

    # ------------------------------------------------------------------ #
    # 4. escape_never_triggers
    # ------------------------------------------------------------------ #

    def test_escape_never_triggers_detected(self):
        """Trigger: >=10 traces, escape never fired, mean stability < 0.75."""
        traces = [
            _make_trace(escape_triggered=False, stability_score=0.6)
            for _ in range(10)
        ]
        critic = CrossQueryCritic()
        result = critic.analyze_session(traces)
        types = [w.weakness_type for w in result]
        assert WeaknessType.ESCAPE_NEVER_TRIGGERS in types

    def test_escape_never_triggers_severity_is_0_5(self):
        """Severity is always 0.5."""
        traces = [_make_trace(escape_triggered=False, stability_score=0.5) for _ in range(10)]
        critic = CrossQueryCritic()
        result = critic.analyze_session(traces)
        w = next(x for x in result if x.weakness_type == WeaknessType.ESCAPE_NEVER_TRIGGERS)
        assert w.severity == 0.5
        assert w.location == "session"
        assert w.suggested_repair_type == "lower_anchor_threshold"

    def test_escape_never_triggers_not_detected_when_escape_fires(self):
        """NOT triggered when at least one trace has escape_triggered=True."""
        traces = [
            _make_trace(escape_triggered=False, stability_score=0.6)
            for _ in range(9)
        ] + [_make_trace(escape_triggered=True, stability_score=0.6)]
        critic = CrossQueryCritic()
        result = critic.analyze_session(traces)
        types = [w.weakness_type for w in result]
        assert WeaknessType.ESCAPE_NEVER_TRIGGERS not in types

    def test_escape_never_triggers_not_detected_when_stability_high(self):
        """NOT triggered when mean stability >= 0.75 (escape correctly not needed)."""
        traces = [_make_trace(escape_triggered=False, stability_score=0.9) for _ in range(10)]
        critic = CrossQueryCritic()
        result = critic.analyze_session(traces)
        types = [w.weakness_type for w in result]
        assert WeaknessType.ESCAPE_NEVER_TRIGGERS not in types

    def test_escape_never_triggers_not_detected_with_fewer_than_10_traces(self):
        """NOT triggered with fewer than 10 traces."""
        traces = [_make_trace(escape_triggered=False, stability_score=0.5) for _ in range(9)]
        critic = CrossQueryCritic()
        result = critic.analyze_session(traces)
        types = [w.weakness_type for w in result]
        assert WeaknessType.ESCAPE_NEVER_TRIGGERS not in types

    def test_escape_never_triggers_description_includes_trace_count(self):
        """Description includes the number of traces."""
        traces = [_make_trace(escape_triggered=False, stability_score=0.5) for _ in range(12)]
        critic = CrossQueryCritic()
        result = critic.analyze_session(traces)
        w = next(x for x in result if x.weakness_type == WeaknessType.ESCAPE_NEVER_TRIGGERS)
        assert "12" in w.description

    # ------------------------------------------------------------------ #
    # 5. learning_stagnation
    # ------------------------------------------------------------------ #

    def _make_trace_with_dims(self, tc=0.9, cs=0.1, pls=0.3, **kwargs):
        """Shorthand for a trace with specific lyapunov dims."""
        return _make_trace(
            lyapunov_dims={
                "temporal_consistency": tc,
                "contradiction_score": cs,
                "pattern_lock_score": pls,
            },
            **kwargs,
        )

    def test_learning_stagnation_detected(self):
        """Trigger: >=8 traces, first half weakness count >= second half."""
        # First 4 traces: all have 3 weaknesses (tc<0.6, cs>0.3, pls>0.7)
        # Second 4 traces: also have 3 weaknesses → no improvement
        bad_dims = dict(tc=0.4, cs=0.5, pls=0.8)
        traces = [self._make_trace_with_dims(**bad_dims) for _ in range(8)]
        critic = CrossQueryCritic()
        result = critic.analyze_session(traces)
        types = [w.weakness_type for w in result]
        assert WeaknessType.LEARNING_STAGNATION in types

    def test_learning_stagnation_severity_is_0_6(self):
        """Severity is always 0.6."""
        bad_dims = dict(tc=0.4, cs=0.5, pls=0.8)
        traces = [self._make_trace_with_dims(**bad_dims) for _ in range(8)]
        critic = CrossQueryCritic()
        result = critic.analyze_session(traces)
        w = next(x for x in result if x.weakness_type == WeaknessType.LEARNING_STAGNATION)
        assert w.severity == 0.6
        assert w.location == "session"
        assert w.suggested_repair_type == "increase_retrieval_depth"

    def test_learning_stagnation_not_detected_when_improving(self):
        """NOT triggered when second half has fewer weaknesses than first half."""
        # First 4 traces: 3 weaknesses each (tc<0.6, cs>0.3, pls>0.7)
        # Second 4 traces: 0 weaknesses each
        bad_dims = dict(tc=0.4, cs=0.5, pls=0.8)
        good_dims = dict(tc=0.9, cs=0.1, pls=0.3)
        traces = (
            [self._make_trace_with_dims(**bad_dims) for _ in range(4)]
            + [self._make_trace_with_dims(**good_dims) for _ in range(4)]
        )
        critic = CrossQueryCritic()
        result = critic.analyze_session(traces)
        types = [w.weakness_type for w in result]
        assert WeaknessType.LEARNING_STAGNATION not in types

    def test_learning_stagnation_not_detected_with_fewer_than_8_traces(self):
        """NOT triggered with fewer than 8 traces."""
        bad_dims = dict(tc=0.4, cs=0.5, pls=0.8)
        traces = [self._make_trace_with_dims(**bad_dims) for _ in range(7)]
        critic = CrossQueryCritic()
        result = critic.analyze_session(traces)
        types = [w.weakness_type for w in result]
        assert WeaknessType.LEARNING_STAGNATION not in types

    def test_learning_stagnation_description_includes_halves(self):
        """Description includes first_half and second_half mean values."""
        bad_dims = dict(tc=0.4, cs=0.5, pls=0.8)
        traces = [self._make_trace_with_dims(**bad_dims) for _ in range(8)]
        critic = CrossQueryCritic()
        result = critic.analyze_session(traces)
        w = next(x for x in result if x.weakness_type == WeaknessType.LEARNING_STAGNATION)
        assert "first_half=" in w.description
        assert "second_half=" in w.description

    # ------------------------------------------------------------------ #
    # General properties
    # ------------------------------------------------------------------ #

    def test_results_sorted_by_severity_descending(self):
        """Results are sorted by severity descending."""
        # Build a session that triggers multiple weaknesses
        # novelty_deficit (severity = fraction of overused)
        # coverage_bias (severity = 0.6)
        # escape_never_triggers (severity = 0.5)
        # 10 traces with same fact_ids (novelty), same anchor prefix (coverage), no escape
        traces = [
            _make_trace(
                fact_ids=["shared_f"],
                anchor_ids=["ABCD1", "ABCD2"],
                escape_triggered=False,
                stability_score=0.5,
            )
            for _ in range(10)
        ]
        critic = CrossQueryCritic()
        result = critic.analyze_session(traces)
        severities = [w.severity for w in result]
        assert severities == sorted(severities, reverse=True)

    def test_no_duplicate_weakness_types(self):
        """No duplicate weakness types in results."""
        traces = [
            _make_trace(
                fact_ids=["shared_f"],
                anchor_ids=["ABCD1"],
                escape_triggered=False,
                stability_score=0.5,
            )
            for _ in range(10)
        ]
        critic = CrossQueryCritic()
        result = critic.analyze_session(traces)
        type_list = [w.weakness_type for w in result]
        assert len(type_list) == len(set(type_list))
