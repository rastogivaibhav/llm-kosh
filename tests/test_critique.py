"""
Tests for TraceWeakness dataclass (llm_kosh/engine/reasoning/critique.py).

Covers:
- WeaknessType enum has all 14 values
- TraceWeakness construction with all fields
- to_dict() / from_dict() round-trip
- severity is validated to be in [0.0, 1.0]
- Invalid weakness_type raises ValueError in from_dict()
"""
from __future__ import annotations

import pytest

from llm_kosh.engine.reasoning.critique import TraceWeakness, WeaknessType


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
