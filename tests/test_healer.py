"""
Tests for HealingAction and QueryParams dataclasses (llm_kosh/engine/reasoning/healer.py).

Covers:
- HealingActionType has all 7 enum values
- HealingAction construction and round-trip serialization
- QueryParams has correct defaults
- QueryParams round-trip serialization
"""
from __future__ import annotations

import pytest

from llm_kosh.engine.reasoning.healer import (
    HealingActionType,
    HealingAction,
    QueryParams,
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
