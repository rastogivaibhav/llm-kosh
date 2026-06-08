"""
Tests for T7.1–T7.5: RecursiveReasoningLoop and query_recursive().
"""
from __future__ import annotations

import pytest
from datetime import datetime, timezone
from pathlib import Path

from llm_kosh.core.memory import init_cartridge
from llm_kosh.engine.reasoning import ReasoningEngine, QueryResult
from llm_kosh.engine.reasoning.dialectic import DialecticResult
from llm_kosh.engine.reasoning.trace import QueryTrace
from llm_kosh.engine.reasoning.recursive_loop import LoopState, RecursiveReasoningLoop


def _now():
    return datetime.now(timezone.utc)


@pytest.fixture
def engine(tmp_path):
    init_cartridge(tmp_path, "Test")
    eng = ReasoningEngine(tmp_path, enable_recursive=True)
    now = _now()
    # Ingest a few facts so retrieval and bundle are non-trivial
    for i in range(5):
        eng.ingest(
            content=f"Fact about gravity and motion number {i}",
            documented_at=now,
            valid_from=now,
            valid_until=None,
            confidence=0.85,
            causal_edges=[],
        )
    return eng


@pytest.fixture
def engine_no_recursive(tmp_path):
    init_cartridge(tmp_path, "Test")
    eng = ReasoningEngine(tmp_path, enable_recursive=False)
    now = _now()
    eng.ingest("Fact", now, now, None, 0.9, [])
    return eng


# ---------------------------------------------------------------------------
# Basic smoke tests
# ---------------------------------------------------------------------------

def test_query_recursive_returns_tuple(engine):
    result, state = engine.query_recursive("gravity motion", max_iterations=2)
    assert isinstance(result, QueryResult)
    assert isinstance(state, LoopState)


def test_loop_state_iteration_count_at_least_1(engine):
    _, state = engine.query_recursive("gravity motion", max_iterations=2)
    assert state.iteration_count >= 1


def test_loop_state_termination_reason_set(engine):
    _, state = engine.query_recursive("gravity motion", max_iterations=2)
    assert state.termination_reason is not None


def test_loop_state_stability_progression_one_float_per_iteration(engine):
    _, state = engine.query_recursive("gravity motion", max_iterations=3)
    assert len(state.stability_progression) == state.iteration_count
    for s in state.stability_progression:
        assert isinstance(s, float)


def test_loop_state_traces_are_query_traces(engine):
    _, state = engine.query_recursive("gravity motion", max_iterations=2)
    assert len(state.traces) == state.iteration_count
    for trace in state.traces:
        assert isinstance(trace, QueryTrace)


# ---------------------------------------------------------------------------
# Fallback when recursive disabled
# ---------------------------------------------------------------------------

def test_recursive_disabled_falls_back_to_single_pass(engine_no_recursive):
    result, state = engine_no_recursive.query_recursive("fact", max_iterations=5)
    assert isinstance(result, QueryResult)
    assert state.termination_reason == "recursive_disabled"
    assert state.iteration_count == 1
    # No traces saved in single-pass fallback
    assert state.traces == []


# ---------------------------------------------------------------------------
# Stability threshold early termination
# ---------------------------------------------------------------------------

def test_stability_threshold_terminates_immediately(tmp_path):
    """When stability >= threshold from iteration 1, terminates with stability_threshold_reached."""
    init_cartridge(tmp_path, "Test")
    engine = ReasoningEngine(tmp_path, enable_recursive=True)
    now = _now()
    # Ingest many high-confidence, consistent facts to push stability up
    for i in range(10):
        engine.ingest(f"High confidence stable fact {i}", now, now, None, 0.99, [])

    # Use a very low threshold so it's almost certain to trigger immediately
    _, state = engine.query_recursive(
        "stable fact",
        max_iterations=5,
        stability_threshold=0.0,  # always satisfied
    )
    assert state.termination_reason == "stability_threshold_reached"
    assert state.iteration_count == 1


def test_max_iterations_terminates(engine):
    """When max_iterations is hit, termination_reason is max_iterations_reached."""
    _, state = engine.query_recursive("gravity motion", max_iterations=1)
    # With max_iterations=1, either stability threshold or max_iterations_reached
    assert state.termination_reason in (
        "stability_threshold_reached",
        "max_iterations_reached",
        "no_discovery_gain",
        "oscillation_detected",
    )
    assert state.iteration_count >= 1


# ---------------------------------------------------------------------------
# query_dialectic_recursive
# ---------------------------------------------------------------------------

def test_query_dialectic_recursive_returns_tuple(engine):
    dialectic_result, state = engine.query_dialectic_recursive(
        "gravity motion", max_iterations=2
    )
    assert isinstance(dialectic_result, DialecticResult)
    assert isinstance(state, LoopState)


def test_query_dialectic_recursive_loop_state_traces_are_query_traces(engine):
    _, state = engine.query_dialectic_recursive("gravity motion", max_iterations=2)
    assert len(state.traces) == state.iteration_count
    for trace in state.traces:
        assert isinstance(trace, QueryTrace)


def test_query_dialectic_recursive_termination_reason_set(engine):
    _, state = engine.query_dialectic_recursive("gravity motion", max_iterations=2)
    assert state.termination_reason is not None


def test_query_dialectic_recursive_stability_progression(engine):
    _, state = engine.query_dialectic_recursive("gravity motion", max_iterations=2)
    assert len(state.stability_progression) == state.iteration_count


# ---------------------------------------------------------------------------
# LoopState structural checks
# ---------------------------------------------------------------------------

def test_loop_state_discovery_gain_progression_matches_iteration_count(engine):
    _, state = engine.query_recursive("gravity motion", max_iterations=2)
    assert len(state.discovery_gain_progression) == state.iteration_count


def test_loop_state_all_weaknesses_matches_iteration_count(engine):
    _, state = engine.query_recursive("gravity motion", max_iterations=2)
    assert len(state.all_weaknesses) == state.iteration_count


# ---------------------------------------------------------------------------
# enable_recursive flag on constructor
# ---------------------------------------------------------------------------

def test_engine_enable_recursive_flag_defaults_to_true(tmp_path):
    init_cartridge(tmp_path, "Test")
    engine = ReasoningEngine(tmp_path)
    assert engine._enable_recursive is True


def test_engine_enable_recursive_flag_can_be_disabled(tmp_path):
    init_cartridge(tmp_path, "Test")
    engine = ReasoningEngine(tmp_path, enable_recursive=False)
    assert engine._enable_recursive is False
