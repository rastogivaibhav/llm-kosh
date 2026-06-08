"""Tests for llm_kosh.engine.reasoning.self_model (Task 11: T6.1–T6.5)."""
from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

from llm_kosh.engine.reasoning.healer import QueryParams
from llm_kosh.engine.reasoning.lyapunov_critic import LyapunovCritic
from llm_kosh.engine.reasoning.self_model import (
    BiasProfile,
    ReasoningPattern,
    SelfModel,
    SelfModelController,
    get_adapted_weights,
)
from llm_kosh.engine.reasoning.trace import QueryTrace


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_trace(
    *,
    anchor_ids=None,
    query_time=None,
    stability_score=0.5,
    stability_status="marginal",
    lyapunov_dimensions=None,
    escape_triggered=False,
    bundle_summary=None,
) -> QueryTrace:
    """Build a minimal QueryTrace for testing."""
    now = time.time()
    return QueryTrace(
        anchor_ids=anchor_ids or [],
        query_time=query_time if query_time is not None else now,
        stability_score=stability_score,
        stability_status=stability_status,
        lyapunov_dimensions=lyapunov_dimensions or {
            "temporal_consistency": 0.5,
            "path_diversity": 0.5,
            "degeneracy": 0.5,
            "contradiction_score": 0.5,
            "pattern_lock_score": 0.5,
        },
        escape_triggered=escape_triggered,
        bundle_summary=bundle_summary or {},
    )


# ---------------------------------------------------------------------------
# ReasoningPattern
# ---------------------------------------------------------------------------

class TestReasoningPattern:
    def test_round_trip(self):
        now = time.time()
        p = ReasoningPattern(
            pattern_type="stability_plateau",
            description="test",
            supporting_trace_ids=["t1", "t2"],
            confidence=0.8,
            first_seen=now,
            last_seen=now + 1,
        )
        assert ReasoningPattern.from_dict(p.to_dict()) == p


# ---------------------------------------------------------------------------
# BiasProfile
# ---------------------------------------------------------------------------

class TestBiasProfile:
    def test_dominant_bias_none_when_all_low(self):
        bp = BiasProfile(biases={"recency_bias": 0.1, "high_confidence_bias": 0.2})
        assert bp.dominant_bias() is None

    def test_dominant_bias_returns_highest_above_threshold(self):
        bp = BiasProfile(biases={"recency_bias": 0.5, "high_confidence_bias": 0.2})
        assert bp.dominant_bias() == "recency_bias"

    def test_dominant_bias_exactly_at_threshold_returns_none(self):
        bp = BiasProfile(biases={"recency_bias": 0.3})
        assert bp.dominant_bias() is None

    def test_round_trip(self):
        bp = BiasProfile(biases={
            "recency_bias": 0.5,
            "high_confidence_bias": 0.0,
            "domain_bias": 0.1,
            "compression_preference": 0.0,
        })
        bp2 = BiasProfile.from_dict(bp.to_dict())
        assert bp2.biases == bp.biases


# ---------------------------------------------------------------------------
# SelfModel — persistence
# ---------------------------------------------------------------------------

class TestSelfModelPersistence:
    def test_persists_to_disk_and_reloads(self, tmp_path):
        sm = SelfModel(tmp_path)
        trace = _make_trace(
            anchor_ids=["abcd1234"],
            stability_status="stable",
            stability_score=0.8,
            lyapunov_dimensions={
                "temporal_consistency": 0.9,
                "path_diversity": 0.8,
                "degeneracy": 0.7,
                "contradiction_score": 0.1,
                "pattern_lock_score": 0.2,
            },
        )
        sm.observe(trace)
        assert (tmp_path / ".self_model.json").exists()

        sm2 = SelfModel(tmp_path)
        assert sm2._trace_count == 1
        # bias profile survived round-trip
        assert sm2.bias_profile.biases == sm.bias_profile.biases

    def test_corrupt_file_handled_gracefully(self, tmp_path):
        corrupt = tmp_path / ".self_model.json"
        corrupt.write_text("{invalid json:::}", encoding="utf-8")
        # Should not raise
        sm = SelfModel(tmp_path)
        assert sm._trace_count == 0
        assert sm.bias_profile.biases["recency_bias"] == 0.0


# ---------------------------------------------------------------------------
# SelfModel — trace_count
# ---------------------------------------------------------------------------

class TestTraceCount:
    def test_trace_count_increments(self, tmp_path):
        sm = SelfModel(tmp_path)
        assert sm._trace_count == 0
        for _ in range(5):
            sm.observe(_make_trace())
        assert sm._trace_count == 5

    def test_trace_count_persists(self, tmp_path):
        sm = SelfModel(tmp_path)
        sm.observe(_make_trace())
        sm.observe(_make_trace())
        sm2 = SelfModel(tmp_path)
        assert sm2._trace_count == 2


# ---------------------------------------------------------------------------
# SelfModel — observe() updates bias_profile
# ---------------------------------------------------------------------------

class TestObserveBiases:
    def test_observe_updates_bias_profile(self, tmp_path):
        sm = SelfModel(tmp_path)
        # A trace that should trigger recency_bias (query_time is now → within 7 days)
        trace = _make_trace(anchor_ids=["abcd1234"], query_time=time.time())
        sm.observe(trace)
        # recency_bias should be > 0 after decay+increment
        assert sm.bias_profile.biases["recency_bias"] > 0.0

    def test_high_confidence_bias_increments(self, tmp_path):
        sm = SelfModel(tmp_path)
        trace = _make_trace(
            stability_status="stable",
            lyapunov_dimensions={
                "temporal_consistency": 0.9,
                "path_diversity": 0.8,
                "degeneracy": 0.3,   # < 0.5 → triggers high_confidence_bias
                "contradiction_score": 0.1,
                "pattern_lock_score": 0.1,
            },
        )
        sm.observe(trace)
        assert sm.bias_profile.biases["high_confidence_bias"] > 0.0

    def test_compression_preference_increments(self, tmp_path):
        sm = SelfModel(tmp_path)
        trace = _make_trace(
            stability_score=0.8,   # > 0.7
            bundle_summary={"max_degeneracy": 1},
        )
        sm.observe(trace)
        assert sm.bias_profile.biases["compression_preference"] > 0.0

    def test_bias_scores_clamped_to_one(self, tmp_path):
        sm = SelfModel(tmp_path)
        # Force high value by observing many times
        for _ in range(20):
            sm.observe(_make_trace(
                anchor_ids=["abcd1234"],
                query_time=time.time(),
                stability_status="stable",
                lyapunov_dimensions={
                    "temporal_consistency": 0.9,
                    "path_diversity": 0.8,
                    "degeneracy": 0.3,
                    "contradiction_score": 0.1,
                    "pattern_lock_score": 0.1,
                },
            ))
        for v in sm.bias_profile.biases.values():
            assert 0.0 <= v <= 1.0

    def test_no_anchors_no_recency_bias(self, tmp_path):
        sm = SelfModel(tmp_path)
        trace = _make_trace(anchor_ids=[], query_time=time.time())
        sm.observe(trace)
        assert sm.bias_profile.biases["recency_bias"] == 0.0


# ---------------------------------------------------------------------------
# SelfModel — bottleneck counts / get_adapted_weights
# ---------------------------------------------------------------------------

class TestGetAdaptedWeights:
    def test_boosts_bottleneck_dimension(self, tmp_path):
        sm = SelfModel(tmp_path)
        base_weights = dict(LyapunovCritic.DEFAULT_WEIGHTS)
        # Observe many traces where temporal_consistency is always the minimum
        for _ in range(5):
            sm.observe(_make_trace(
                lyapunov_dimensions={
                    "temporal_consistency": 0.1,   # always lowest
                    "path_diversity": 0.8,
                    "degeneracy": 0.7,
                    "contradiction_score": 0.5,
                    "pattern_lock_score": 0.5,
                },
            ))
        adapted = get_adapted_weights(sm, base_weights)
        assert adapted["temporal_consistency"] > base_weights["temporal_consistency"]

    def test_no_boost_when_no_dominant_bottleneck(self, tmp_path):
        sm = SelfModel(tmp_path)
        base_weights = dict(LyapunovCritic.DEFAULT_WEIGHTS)
        # Alternate bottleneck between two dims — neither exceeds 60%
        for i in range(10):
            dim = "temporal_consistency" if i % 2 == 0 else "path_diversity"
            dims = {
                "temporal_consistency": 0.5,
                "path_diversity": 0.5,
                "degeneracy": 0.7,
                "contradiction_score": 0.5,
                "pattern_lock_score": 0.5,
            }
            dims[dim] = 0.1  # make it the min
            sm.observe(_make_trace(lyapunov_dimensions=dims))
        adapted = get_adapted_weights(sm, base_weights)
        assert adapted["temporal_consistency"] == pytest.approx(
            base_weights["temporal_consistency"], abs=0.06
        )

    def test_no_crash_on_empty_self_model(self, tmp_path):
        sm = SelfModel(tmp_path)
        base_weights = dict(LyapunovCritic.DEFAULT_WEIGHTS)
        adapted = get_adapted_weights(sm, base_weights)
        assert adapted == base_weights


# ---------------------------------------------------------------------------
# SelfModelController — adapt_params
# ---------------------------------------------------------------------------

class TestSelfModelController:
    def _make_sm_with_bias(self, tmp_path, bias_key: str, value: float) -> SelfModel:
        sm = SelfModel(tmp_path)
        sm.bias_profile.biases[bias_key] = value
        return sm

    def test_domain_bias_sets_anchor_prefix(self, tmp_path):
        sm = self._make_sm_with_bias(tmp_path, "domain_bias", 0.7)
        sm._trace_count = 0
        controller = SelfModelController()
        result = controller.adapt_params(QueryParams(), sm)
        assert result.anchor_prefix_filter in ["0", "1", "2", "3"]

    def test_high_confidence_bias_increases_depth(self, tmp_path):
        sm = self._make_sm_with_bias(tmp_path, "high_confidence_bias", 0.7)
        controller = SelfModelController()
        base = QueryParams(depth=3)
        result = controller.adapt_params(base, sm)
        assert result.depth > 3

    def test_depth_never_exceeds_cap(self, tmp_path):
        sm = SelfModel(tmp_path)
        sm.bias_profile.biases["high_confidence_bias"] = 0.9
        sm.bias_profile.biases["compression_preference"] = 0.9
        controller = SelfModelController()
        result = controller.adapt_params(QueryParams(depth=8), sm)
        assert result.depth <= 8

    def test_recency_bias_reduces_temporal_offset(self, tmp_path):
        sm = self._make_sm_with_bias(tmp_path, "recency_bias", 0.8)
        controller = SelfModelController()
        base = QueryParams(temporal_offset_secs=90000.0)
        result = controller.adapt_params(base, sm)
        assert result.temporal_offset_secs < 90000.0

    def test_temporal_offset_never_negative(self, tmp_path):
        sm = self._make_sm_with_bias(tmp_path, "recency_bias", 0.9)
        controller = SelfModelController()
        base = QueryParams(temporal_offset_secs=0.0)
        result = controller.adapt_params(base, sm)
        assert result.temporal_offset_secs >= 0.0

    def test_no_bias_no_change(self, tmp_path):
        sm = SelfModel(tmp_path)
        controller = SelfModelController()
        base = QueryParams()
        result = controller.adapt_params(base, sm)
        assert result.depth == base.depth
        assert result.anchor_prefix_filter == base.anchor_prefix_filter
        assert result.temporal_offset_secs == base.temporal_offset_secs

    def test_compression_preference_increases_depth(self, tmp_path):
        sm = self._make_sm_with_bias(tmp_path, "compression_preference", 0.6)
        controller = SelfModelController()
        base = QueryParams(depth=3)
        result = controller.adapt_params(base, sm)
        assert result.depth > 3
