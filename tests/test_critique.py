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

from llm_kosh.engine.reasoning.critique import TraceCritic, TraceWeakness, WeaknessType
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

    def test_hypothetical_not_detected_when_escape_not_triggered(self):
        """NOT triggered when escape_triggered is False."""
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
        assert WeaknessType.HYPOTHETICAL_PROMOTED_SILENTLY not in types

    def test_hypothetical_not_detected_when_tc_too_low(self):
        """NOT triggered when temporal_consistency < 0.7."""
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
        assert WeaknessType.HYPOTHETICAL_PROMOTED_SILENTLY not in types

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
