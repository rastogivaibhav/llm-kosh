"""
Tests for HealingAction, QueryParams, and HealingExecutor
(llm_kosh/engine/reasoning/healer.py).

Covers:
- HealingActionType has all 7 enum values
- HealingAction construction and round-trip serialization
- QueryParams has correct defaults
- QueryParams round-trip serialization
- HealingExecutor.heal() strategy mapping and accumulation
"""
from __future__ import annotations

import pytest

from llm_kosh.engine.reasoning.healer import (
    HealingActionType,
    HealingAction,
    HealingExecutor,
    QueryParams,
)
from llm_kosh.engine.reasoning.critique import (
    TraceWeakness,
    WeaknessReport,
    WeaknessType,
)


# ---------------------------------------------------------------------------
# HealingActionType enum tests
# ---------------------------------------------------------------------------


class TestHealingActionType:
    """Test that HealingActionType enum has all required values."""

    def test_enum_has_widen_temporal_window(self):
        assert hasattr(HealingActionType, "WIDEN_TEMPORAL_WINDOW")
        assert HealingActionType.WIDEN_TEMPORAL_WINDOW.value == "widen_temporal_window"

    def test_enum_has_force_contradiction_surface(self):
        assert hasattr(HealingActionType, "FORCE_CONTRADICTION_SURFACE")
        assert HealingActionType.FORCE_CONTRADICTION_SURFACE.value == "force_contradiction_surface"

    def test_enum_has_increase_retrieval_depth(self):
        assert hasattr(HealingActionType, "INCREASE_RETRIEVAL_DEPTH")
        assert HealingActionType.INCREASE_RETRIEVAL_DEPTH.value == "increase_retrieval_depth"

    def test_enum_has_lower_anchor_threshold(self):
        assert hasattr(HealingActionType, "LOWER_ANCHOR_THRESHOLD")
        assert HealingActionType.LOWER_ANCHOR_THRESHOLD.value == "lower_anchor_threshold"

    def test_enum_has_demote_hypothetical(self):
        assert hasattr(HealingActionType, "DEMOTE_HYPOTHETICAL")
        assert HealingActionType.DEMOTE_HYPOTHETICAL.value == "demote_hypothetical"

    def test_enum_has_reset_to_low_freq_region(self):
        assert hasattr(HealingActionType, "RESET_TO_LOW_FREQ_REGION")
        assert HealingActionType.RESET_TO_LOW_FREQ_REGION.value == "reset_to_low_freq_region"

    def test_enum_has_rotate_anchor_prefix(self):
        assert hasattr(HealingActionType, "ROTATE_ANCHOR_PREFIX")
        assert HealingActionType.ROTATE_ANCHOR_PREFIX.value == "rotate_anchor_prefix"

    def test_enum_has_exactly_7_values(self):
        """Ensure we have exactly 7 healing action types."""
        enum_members = list(HealingActionType)
        assert len(enum_members) == 7

    def test_enum_is_string_enum(self):
        """Verify HealingActionType is a string enum."""
        action = HealingActionType.WIDEN_TEMPORAL_WINDOW
        assert isinstance(action, str)
        assert action == "widen_temporal_window"


# ---------------------------------------------------------------------------
# HealingAction dataclass tests
# ---------------------------------------------------------------------------


class TestHealingActionConstruction:
    """Test basic HealingAction construction."""

    def test_construct_minimal(self):
        """Create a HealingAction with all required fields."""
        action = HealingAction(
            action_type=HealingActionType.WIDEN_TEMPORAL_WINDOW,
            target="temporal_offset_secs",
            magnitude=10.0,
            rationale="Temporal window too narrow to capture causality",
        )
        assert action.action_type == HealingActionType.WIDEN_TEMPORAL_WINDOW
        assert action.target == "temporal_offset_secs"
        assert action.magnitude == 10.0
        assert action.rationale == "Temporal window too narrow to capture causality"

    def test_all_action_types(self):
        """Verify we can construct HealingAction with all action types."""
        for action_type in HealingActionType:
            action = HealingAction(
                action_type=action_type,
                target="test_target",
                magnitude=1.0,
                rationale="test rationale",
            )
            assert action.action_type == action_type


class TestHealingActionSerialization:
    """Test HealingAction round-trip serialization."""

    def test_to_dict_basic(self):
        """Verify to_dict returns a proper dictionary."""
        action = HealingAction(
            action_type=HealingActionType.LOWER_ANCHOR_THRESHOLD,
            target="score_threshold",
            magnitude=0.1,
            rationale="Need to consider weaker anchors",
        )
        d = action.to_dict()
        assert isinstance(d, dict)
        assert d["action_type"] == "lower_anchor_threshold"
        assert d["target"] == "score_threshold"
        assert d["magnitude"] == 0.1
        assert d["rationale"] == "Need to consider weaker anchors"

    def test_from_dict_basic(self):
        """Verify from_dict reconstructs the object."""
        data = {
            "action_type": "increase_retrieval_depth",
            "target": "depth",
            "magnitude": 2.0,
            "rationale": "Need more context",
        }
        action = HealingAction.from_dict(data)
        assert action.action_type == HealingActionType.INCREASE_RETRIEVAL_DEPTH
        assert action.target == "depth"
        assert action.magnitude == 2.0
        assert action.rationale == "Need more context"

    def test_roundtrip_serialization(self):
        """Verify object survives to_dict -> from_dict cycle."""
        original = HealingAction(
            action_type=HealingActionType.FORCE_CONTRADICTION_SURFACE,
            target="force_contradiction_surface",
            magnitude=1.0,
            rationale="Contradictions are being hidden",
        )
        data = original.to_dict()
        reconstructed = HealingAction.from_dict(data)

        assert reconstructed.action_type == original.action_type
        assert reconstructed.target == original.target
        assert reconstructed.magnitude == original.magnitude
        assert reconstructed.rationale == original.rationale

    def test_roundtrip_all_action_types(self):
        """Roundtrip test for each action type."""
        for action_type in HealingActionType:
            original = HealingAction(
                action_type=action_type,
                target=f"{action_type.value}_target",
                magnitude=1.5,
                rationale=f"Healing reason for {action_type.value}",
            )
            data = original.to_dict()
            reconstructed = HealingAction.from_dict(data)

            assert reconstructed.action_type == original.action_type
            assert reconstructed.target == original.target
            assert reconstructed.magnitude == original.magnitude
            assert reconstructed.rationale == original.rationale


# ---------------------------------------------------------------------------
# QueryParams dataclass tests
# ---------------------------------------------------------------------------


class TestQueryParamsDefaults:
    """Test that QueryParams has correct default values."""

    def test_default_score_threshold(self):
        params = QueryParams()
        assert params.score_threshold == 0.25

    def test_default_depth(self):
        params = QueryParams()
        assert params.depth == 3

    def test_default_temporal_offset_secs(self):
        params = QueryParams()
        assert params.temporal_offset_secs == 0.0

    def test_default_force_contradiction_surface(self):
        params = QueryParams()
        assert params.force_contradiction_surface is False

    def test_default_demote_hypothetical(self):
        params = QueryParams()
        assert params.demote_hypothetical is False

    def test_default_anchor_prefix_filter(self):
        params = QueryParams()
        assert params.anchor_prefix_filter is None


class TestQueryParamsConstruction:
    """Test custom QueryParams construction."""

    def test_construct_all_defaults(self):
        """Create QueryParams with default values."""
        params = QueryParams()
        assert params.score_threshold == 0.25
        assert params.depth == 3
        assert params.temporal_offset_secs == 0.0
        assert params.force_contradiction_surface is False
        assert params.demote_hypothetical is False
        assert params.anchor_prefix_filter is None

    def test_construct_custom_values(self):
        """Create QueryParams with custom values."""
        params = QueryParams(
            score_threshold=0.15,
            depth=5,
            temporal_offset_secs=30.0,
            force_contradiction_surface=True,
            demote_hypothetical=True,
            anchor_prefix_filter="fact_",
        )
        assert params.score_threshold == 0.15
        assert params.depth == 5
        assert params.temporal_offset_secs == 30.0
        assert params.force_contradiction_surface is True
        assert params.demote_hypothetical is True
        assert params.anchor_prefix_filter == "fact_"

    def test_construct_partial_custom_values(self):
        """Create QueryParams with some custom values and some defaults."""
        params = QueryParams(
            depth=7,
            force_contradiction_surface=True,
        )
        assert params.depth == 7
        assert params.force_contradiction_surface is True
        # Check defaults are preserved
        assert params.score_threshold == 0.25
        assert params.temporal_offset_secs == 0.0
        assert params.demote_hypothetical is False
        assert params.anchor_prefix_filter is None


class TestQueryParamsSerialization:
    """Test QueryParams round-trip serialization."""

    def test_to_dict_defaults(self):
        """Verify to_dict with default values."""
        params = QueryParams()
        d = params.to_dict()
        assert isinstance(d, dict)
        assert d["score_threshold"] == 0.25
        assert d["depth"] == 3
        assert d["temporal_offset_secs"] == 0.0
        assert d["force_contradiction_surface"] is False
        assert d["demote_hypothetical"] is False
        assert d["anchor_prefix_filter"] is None

    def test_to_dict_custom_values(self):
        """Verify to_dict with custom values."""
        params = QueryParams(
            score_threshold=0.1,
            depth=10,
            temporal_offset_secs=60.0,
            force_contradiction_surface=True,
            demote_hypothetical=True,
            anchor_prefix_filter="prefix_",
        )
        d = params.to_dict()
        assert d["score_threshold"] == 0.1
        assert d["depth"] == 10
        assert d["temporal_offset_secs"] == 60.0
        assert d["force_contradiction_surface"] is True
        assert d["demote_hypothetical"] is True
        assert d["anchor_prefix_filter"] == "prefix_"

    def test_from_dict_defaults(self):
        """Verify from_dict with missing fields uses defaults."""
        data = {}
        params = QueryParams.from_dict(data)
        assert params.score_threshold == 0.25
        assert params.depth == 3
        assert params.temporal_offset_secs == 0.0
        assert params.force_contradiction_surface is False
        assert params.demote_hypothetical is False
        assert params.anchor_prefix_filter is None

    def test_from_dict_partial(self):
        """Verify from_dict with partial data."""
        data = {
            "score_threshold": 0.2,
            "depth": 5,
        }
        params = QueryParams.from_dict(data)
        assert params.score_threshold == 0.2
        assert params.depth == 5
        assert params.temporal_offset_secs == 0.0  # default
        assert params.force_contradiction_surface is False  # default
        assert params.demote_hypothetical is False  # default
        assert params.anchor_prefix_filter is None  # default

    def test_from_dict_full(self):
        """Verify from_dict with all fields."""
        data = {
            "score_threshold": 0.15,
            "depth": 7,
            "temporal_offset_secs": 45.0,
            "force_contradiction_surface": True,
            "demote_hypothetical": True,
            "anchor_prefix_filter": "test_",
        }
        params = QueryParams.from_dict(data)
        assert params.score_threshold == 0.15
        assert params.depth == 7
        assert params.temporal_offset_secs == 45.0
        assert params.force_contradiction_surface is True
        assert params.demote_hypothetical is True
        assert params.anchor_prefix_filter == "test_"

    def test_roundtrip_defaults(self):
        """Verify QueryParams with defaults survives roundtrip."""
        original = QueryParams()
        data = original.to_dict()
        reconstructed = QueryParams.from_dict(data)

        assert reconstructed.score_threshold == original.score_threshold
        assert reconstructed.depth == original.depth
        assert reconstructed.temporal_offset_secs == original.temporal_offset_secs
        assert reconstructed.force_contradiction_surface == original.force_contradiction_surface
        assert reconstructed.demote_hypothetical == original.demote_hypothetical
        assert reconstructed.anchor_prefix_filter == original.anchor_prefix_filter

    def test_roundtrip_custom(self):
        """Verify QueryParams with custom values survives roundtrip."""
        original = QueryParams(
            score_threshold=0.08,
            depth=12,
            temporal_offset_secs=120.0,
            force_contradiction_surface=True,
            demote_hypothetical=True,
            anchor_prefix_filter="custom_prefix",
        )
        data = original.to_dict()
        reconstructed = QueryParams.from_dict(data)

        assert reconstructed.score_threshold == original.score_threshold
        assert reconstructed.depth == original.depth
        assert reconstructed.temporal_offset_secs == original.temporal_offset_secs
        assert reconstructed.force_contradiction_surface == original.force_contradiction_surface
        assert reconstructed.demote_hypothetical == original.demote_hypothetical
        assert reconstructed.anchor_prefix_filter == original.anchor_prefix_filter

    def test_type_coercion_in_from_dict(self):
        """Verify from_dict properly coerces types from string/int inputs."""
        data = {
            "score_threshold": "0.33",  # string that should be float
            "depth": "8",  # string that should be int
            "temporal_offset_secs": 15,  # int that should be float
            "force_contradiction_surface": 1,  # int that should be bool
            "demote_hypothetical": 0,  # int that should be bool
            "anchor_prefix_filter": None,
        }
        params = QueryParams.from_dict(data)
        assert params.score_threshold == 0.33
        assert isinstance(params.score_threshold, float)
        assert params.depth == 8
        assert isinstance(params.depth, int)
        assert params.temporal_offset_secs == 15.0
        assert isinstance(params.temporal_offset_secs, float)
        assert params.force_contradiction_surface is True
        assert isinstance(params.force_contradiction_surface, bool)
        assert params.demote_hypothetical is False
        assert isinstance(params.demote_hypothetical, bool)


# ---------------------------------------------------------------------------
# Helper factory
# ---------------------------------------------------------------------------

def _make_weakness(
    weakness_type: WeaknessType,
    severity: float = 0.5,
    description: str = "",
) -> TraceWeakness:
    """Create a minimal TraceWeakness for test purposes."""
    return TraceWeakness(
        weakness_type=weakness_type,
        severity=severity,
        location="test",
        description=description,
        suggested_repair_type="",
    )


def _make_report(*weaknesses: TraceWeakness) -> WeaknessReport:
    """Wrap weaknesses in a WeaknessReport (all treated as per-trace)."""
    return WeaknessReport(
        trace_id="test-trace",
        per_trace_weaknesses=list(weaknesses),
        session_weaknesses=[],
    )


# ---------------------------------------------------------------------------
# HealingExecutor tests
# ---------------------------------------------------------------------------


class TestHealingExecutor:
    """Tests for HealingExecutor.heal() strategy mapping and accumulation."""

    def setup_method(self):
        self.executor = HealingExecutor()

    # ------------------------------------------------------------------ #
    # Empty report → defaults
    # ------------------------------------------------------------------ #

    def test_empty_report_returns_default_params(self):
        report = _make_report()
        result = self.executor.heal(report)
        defaults = QueryParams()
        assert result.score_threshold == defaults.score_threshold
        assert result.depth == defaults.depth
        assert result.temporal_offset_secs == defaults.temporal_offset_secs
        assert result.force_contradiction_surface == defaults.force_contradiction_surface
        assert result.demote_hypothetical == defaults.demote_hypothetical
        assert result.anchor_prefix_filter == defaults.anchor_prefix_filter

    # ------------------------------------------------------------------ #
    # Single-weakness strategy mapping
    # ------------------------------------------------------------------ #

    def test_temporal_consistency_low_increases_temporal_offset(self):
        weakness = _make_weakness(WeaknessType.TEMPORAL_CONSISTENCY_LOW, severity=0.5)
        report = _make_report(weakness)
        result = self.executor.heal(report)
        assert result.temporal_offset_secs == pytest.approx(86_400.0)

    def test_contradiction_unresolved_sets_force_flag(self):
        weakness = _make_weakness(WeaknessType.CONTRADICTION_UNRESOLVED, severity=0.5)
        report = _make_report(weakness)
        result = self.executor.heal(report)
        assert result.force_contradiction_surface is True

    def test_single_path_dominance_increases_depth_by_2(self):
        weakness = _make_weakness(WeaknessType.SINGLE_PATH_DOMINANCE, severity=0.8)
        report = _make_report(weakness)
        result = self.executor.heal(report)
        assert result.depth == 3 + 2  # default 3 + 2

    def test_shallow_depth_increases_depth_by_2(self):
        weakness = _make_weakness(WeaknessType.SHALLOW_DEPTH, severity=0.6)
        report = _make_report(weakness)
        result = self.executor.heal(report)
        assert result.depth == 3 + 2

    def test_low_evidence_diversity_decreases_score_threshold(self):
        weakness = _make_weakness(WeaknessType.LOW_EVIDENCE_DIVERSITY, severity=0.7)
        report = _make_report(weakness)
        result = self.executor.heal(report)
        assert result.score_threshold == pytest.approx(0.25 - 0.05)

    def test_hypothetical_promoted_silently_sets_demote_flag(self):
        weakness = _make_weakness(WeaknessType.HYPOTHETICAL_PROMOTED_SILENTLY, severity=0.8)
        report = _make_report(weakness)
        result = self.executor.heal(report)
        assert result.demote_hypothetical is True

    def test_improvement_stall_increases_depth_by_2(self):
        weakness = _make_weakness(WeaknessType.IMPROVEMENT_STALL, severity=0.7)
        report = _make_report(weakness)
        result = self.executor.heal(report)
        assert result.depth == 3 + 2

    def test_learning_stagnation_increases_depth_by_1(self):
        weakness = _make_weakness(WeaknessType.LEARNING_STAGNATION, severity=0.6)
        report = _make_report(weakness)
        result = self.executor.heal(report)
        assert result.depth == 3 + 1

    # ------------------------------------------------------------------ #
    # No-action weakness types
    # ------------------------------------------------------------------ #

    def test_self_repetition_no_change(self):
        weakness = _make_weakness(WeaknessType.SELF_REPETITION, severity=0.9)
        report = _make_report(weakness)
        result = self.executor.heal(report)
        defaults = QueryParams()
        assert result.depth == defaults.depth
        assert result.score_threshold == defaults.score_threshold
        assert result.temporal_offset_secs == defaults.temporal_offset_secs
        assert result.force_contradiction_surface == defaults.force_contradiction_surface
        assert result.demote_hypothetical == defaults.demote_hypothetical

    def test_oscillation_no_change(self):
        weakness = _make_weakness(WeaknessType.OSCILLATION, severity=0.4)
        report = _make_report(weakness)
        result = self.executor.heal(report)
        defaults = QueryParams()
        assert result.depth == defaults.depth
        assert result.score_threshold == defaults.score_threshold

    # ------------------------------------------------------------------ #
    # Accumulation across multiple weaknesses
    # ------------------------------------------------------------------ #

    def test_multiple_depth_weaknesses_accumulate(self):
        """Two SINGLE_PATH_DOMINANCE → depth += 4 (2+2)."""
        w1 = _make_weakness(WeaknessType.SINGLE_PATH_DOMINANCE, severity=0.9)
        w2 = _make_weakness(WeaknessType.SHALLOW_DEPTH, severity=0.6)
        # Use session_weaknesses to get two distinct instances
        report = WeaknessReport(
            trace_id="test",
            per_trace_weaknesses=[w1],
            session_weaknesses=[w2],
        )
        result = self.executor.heal(report)
        assert result.depth == 3 + 2 + 2  # = 7

    def test_multiple_temporal_weaknesses_accumulate(self):
        """Two temporal weaknesses → 2 × 86400."""
        w1 = _make_weakness(WeaknessType.TEMPORAL_CONSISTENCY_LOW, severity=0.9)
        w2 = _make_weakness(WeaknessType.TEMPORAL_CONSISTENCY_LOW, severity=0.5)
        report = WeaknessReport(
            trace_id="test",
            per_trace_weaknesses=[w1],
            session_weaknesses=[w2],
        )
        result = self.executor.heal(report)
        assert result.temporal_offset_secs == pytest.approx(2 * 86_400.0)

    def test_mixed_weaknesses_accumulate_independently(self):
        """temporal + contradiction + depth should each apply independently."""
        report = _make_report(
            _make_weakness(WeaknessType.TEMPORAL_CONSISTENCY_LOW, severity=0.8),
            _make_weakness(WeaknessType.CONTRADICTION_UNRESOLVED, severity=0.7),
            _make_weakness(WeaknessType.SINGLE_PATH_DOMINANCE, severity=0.6),
        )
        result = self.executor.heal(report)
        assert result.temporal_offset_secs == pytest.approx(86_400.0)
        assert result.force_contradiction_surface is True
        assert result.depth == 3 + 2

    # ------------------------------------------------------------------ #
    # Cap / floor enforcement
    # ------------------------------------------------------------------ #

    def test_depth_cap_at_8(self):
        """Four depth+2 actions would give depth=11, but cap is 8."""
        weaknesses = [
            _make_weakness(WeaknessType.SINGLE_PATH_DOMINANCE, severity=0.9),
            _make_weakness(WeaknessType.SHALLOW_DEPTH, severity=0.8),
            _make_weakness(WeaknessType.IMPROVEMENT_STALL, severity=0.7),
        ]
        report = WeaknessReport(
            trace_id="test",
            per_trace_weaknesses=weaknesses[:2],
            session_weaknesses=weaknesses[2:],
        )
        result = self.executor.heal(report)
        assert result.depth == 8  # capped

    def test_score_threshold_floor_at_005(self):
        """Many lower_anchor_threshold actions should floor at 0.05."""
        # 5 × (-0.05) from default 0.25 = 0.0, but floor is 0.05
        weaknesses = [
            _make_weakness(WeaknessType.LOW_EVIDENCE_DIVERSITY, severity=0.9 - i * 0.1)
            for i in range(5)
        ]
        report = WeaknessReport(
            trace_id="test",
            per_trace_weaknesses=weaknesses[:3],
            session_weaknesses=weaknesses[3:],
        )
        result = self.executor.heal(report)
        assert result.score_threshold == pytest.approx(0.05)

    def test_temporal_offset_cap_at_7_days(self):
        """Eight temporal expansions capped at 7×86400."""
        weaknesses = [
            _make_weakness(WeaknessType.TEMPORAL_CONSISTENCY_LOW, severity=1.0 - i * 0.1)
            for i in range(8)
        ]
        report = WeaknessReport(
            trace_id="test",
            per_trace_weaknesses=weaknesses[:4],
            session_weaknesses=weaknesses[4:],
        )
        result = self.executor.heal(report)
        assert result.temporal_offset_secs == pytest.approx(7 * 86_400.0)

    # ------------------------------------------------------------------ #
    # base_params respected
    # ------------------------------------------------------------------ #

    def test_base_params_used_as_starting_values(self):
        """When base_params provided, healing accumulates on top of them."""
        base = QueryParams(depth=5, score_threshold=0.15, temporal_offset_secs=86_400.0)
        report = _make_report(
            _make_weakness(WeaknessType.SINGLE_PATH_DOMINANCE, severity=0.8),
        )
        result = self.executor.heal(report, base_params=base)
        assert result.depth == 5 + 2  # 7
        assert result.score_threshold == pytest.approx(0.15)  # unchanged
        assert result.temporal_offset_secs == pytest.approx(86_400.0)  # unchanged

    def test_base_params_not_mutated(self):
        """heal() must not modify the base_params object."""
        base = QueryParams(depth=4)
        report = _make_report(
            _make_weakness(WeaknessType.SINGLE_PATH_DOMINANCE, severity=0.8),
        )
        self.executor.heal(report, base_params=base)
        assert base.depth == 4  # unchanged

    def test_base_params_depth_cap_respected(self):
        """Base depth=7 + depth+2 action → capped at 8."""
        base = QueryParams(depth=7)
        report = _make_report(
            _make_weakness(WeaknessType.SINGLE_PATH_DOMINANCE, severity=0.8),
        )
        result = self.executor.heal(report, base_params=base)
        assert result.depth == 8

    def test_base_params_score_threshold_floor_respected(self):
        """Base threshold=0.07 - 0.05 = 0.02 → floored at 0.05."""
        base = QueryParams(score_threshold=0.07)
        report = _make_report(
            _make_weakness(WeaknessType.LOW_EVIDENCE_DIVERSITY, severity=0.6),
        )
        result = self.executor.heal(report, base_params=base)
        assert result.score_threshold == pytest.approx(0.05)

    def test_base_params_boolean_or_accumulation(self):
        """Boolean flags already True in base_params stay True."""
        base = QueryParams(force_contradiction_surface=True)
        # No CONTRADICTION_UNRESOLVED weakness this time
        report = _make_report(
            _make_weakness(WeaknessType.TEMPORAL_CONSISTENCY_LOW, severity=0.5),
        )
        result = self.executor.heal(report, base_params=base)
        assert result.force_contradiction_surface is True  # preserved from base
