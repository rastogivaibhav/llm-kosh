"""
Tests for QueryTrace dataclass (llm_kosh/engine/reasoning/trace.py).

Covers:
- Default construction
- to_dict / from_dict round-trip
- trace_id is a valid UUID4
- parent_trace_id linkage between iterations
- Incremental / partial population
"""
from __future__ import annotations

import json
import time
import uuid

import pytest

import pathlib
import tempfile

from llm_kosh.engine.reasoning.trace import QueryTrace, TraceStore


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _full_trace(**overrides) -> QueryTrace:
    """Return a fully-populated QueryTrace for round-trip tests."""
    defaults = dict(
        query="What caused the 2008 financial crisis?",
        temporal_context="2008-09-15",
        query_time=1221436800.0,
        executed_at=time.time(),
        execution_time_secs=0.342,
        reasoning_mode="balanced",
        candidates=[
            ("fact-001", 1, 0.95),
            ("fact-002", 2, 0.81),
        ],
        anchor_ids=["fact-001"],
        bundle_summary={
            "fiber_count": 2,
            "total_paths": 5,
            "max_degeneracy": 3,
            "fact_ids": ["fact-001", "fact-002"],
        },
        lyapunov_dimensions={
            "temporal_consistency": 0.9,
            "contradiction_score": 0.1,
            "path_diversity": 0.8,
            "degeneracy": 0.7,
            "pattern_lock_score": 0.2,
        },
        stability_score=0.82,
        stability_status="stable",
        escape_triggered=False,
        escape_surfaced=[],
        dialectic_result_summary={
            "converged_fact_id": "fact-001",
            "converged_score": 0.95,
            "opposition_challenges": 1,
            "reopened": False,
            "final_status": "survived_opposition",
        },
        discovery_result_summary=None,
        iteration=0,
        metadata={"source": "unit_test"},
    )
    defaults.update(overrides)
    return QueryTrace(**defaults)


# ---------------------------------------------------------------------------
# Creation with defaults
# ---------------------------------------------------------------------------

class TestDefaultConstruction:
    def test_trace_id_auto_generated(self):
        t = QueryTrace()
        assert t.trace_id != ""
        # Must be parseable as a UUID
        parsed = uuid.UUID(t.trace_id)
        assert str(parsed) == t.trace_id

    def test_trace_id_is_uuid4(self):
        t = QueryTrace()
        parsed = uuid.UUID(t.trace_id)
        assert parsed.version == 4

    def test_unique_trace_ids(self):
        ids = {QueryTrace().trace_id for _ in range(10)}
        assert len(ids) == 10, "Each trace must get a unique ID"

    def test_parent_trace_id_defaults_none(self):
        t = QueryTrace()
        assert t.parent_trace_id is None

    def test_numeric_defaults(self):
        t = QueryTrace()
        assert t.execution_time_secs == 0.0
        assert t.stability_score == 0.0
        assert t.iteration == 0

    def test_bool_defaults(self):
        t = QueryTrace()
        assert t.escape_triggered is False

    def test_list_defaults_are_empty(self):
        t = QueryTrace()
        assert t.candidates == []
        assert t.anchor_ids == []
        assert t.escape_surfaced == []

    def test_dict_defaults_are_empty(self):
        t = QueryTrace()
        assert t.bundle_summary == {}
        assert t.lyapunov_dimensions == {}
        assert t.metadata == {}

    def test_optional_fields_default_none(self):
        t = QueryTrace()
        assert t.temporal_context is None
        assert t.query_time is None
        assert t.dialectic_result_summary is None
        assert t.discovery_result_summary is None

    def test_executed_at_is_recent(self):
        before = time.time()
        t = QueryTrace()
        after = time.time()
        assert before <= t.executed_at <= after

    def test_query_time_defaults_none(self):
        """query_time should default to None; it represents semantic temporal context,
        not wall-clock execution time (which is captured by executed_at)."""
        t = QueryTrace()
        assert t.query_time is None


# ---------------------------------------------------------------------------
# to_dict
# ---------------------------------------------------------------------------

class TestToDict:
    def test_returns_dict(self):
        assert isinstance(QueryTrace().to_dict(), dict)

    def test_all_keys_present(self):
        d = QueryTrace().to_dict()
        expected_keys = {
            "trace_id", "parent_trace_id", "query", "temporal_context",
            "query_time", "executed_at", "execution_time_secs", "reasoning_mode",
            "candidates", "anchor_ids", "bundle_summary", "lyapunov_dimensions",
            "stability_score", "stability_status", "escape_triggered",
            "escape_surfaced", "dialectic_result_summary",
            "discovery_result_summary", "iteration", "metadata",
        }
        assert expected_keys == set(d.keys())

    def test_candidates_serialised_as_lists(self):
        t = QueryTrace(candidates=[("fact-1", 2, 0.9)])
        d = t.to_dict()
        # Each candidate must be a list (JSON-serialisable), not a tuple.
        assert isinstance(d["candidates"][0], list)
        assert d["candidates"][0] == ["fact-1", 2, 0.9]

    def test_json_serialisable(self):
        t = _full_trace()
        # Must not raise
        json_str = json.dumps(t.to_dict())
        assert isinstance(json_str, str)

    def test_values_match_fields(self):
        t = _full_trace(query="test query", stability_score=0.75, iteration=3)
        d = t.to_dict()
        assert d["query"] == "test query"
        assert d["stability_score"] == 0.75
        assert d["iteration"] == 3


# ---------------------------------------------------------------------------
# from_dict round-trip
# ---------------------------------------------------------------------------

class TestFromDict:
    def _round_trip(self, original: QueryTrace) -> QueryTrace:
        return QueryTrace.from_dict(original.to_dict())

    def test_basic_round_trip(self):
        original = _full_trace()
        restored = self._round_trip(original)
        assert restored.trace_id == original.trace_id
        assert restored.query == original.query

    def test_all_scalar_fields_round_trip(self):
        original = _full_trace()
        restored = self._round_trip(original)
        assert restored.execution_time_secs == original.execution_time_secs
        assert restored.stability_score == original.stability_score
        assert restored.stability_status == original.stability_status
        assert restored.escape_triggered == original.escape_triggered
        assert restored.iteration == original.iteration
        assert restored.reasoning_mode == original.reasoning_mode

    def test_candidates_restored_as_tuples(self):
        original = QueryTrace(candidates=[("fact-1", 2, 0.9), ("fact-2", 1, 0.7)])
        restored = self._round_trip(original)
        assert restored.candidates == [("fact-1", 2, 0.9), ("fact-2", 1, 0.7)]
        # Specifically check tuples
        assert isinstance(restored.candidates[0], tuple)

    def test_anchor_ids_round_trip(self):
        original = QueryTrace(anchor_ids=["a1", "a2", "a3"])
        restored = self._round_trip(original)
        assert restored.anchor_ids == ["a1", "a2", "a3"]

    def test_bundle_summary_round_trip(self):
        summary = {
            "fiber_count": 3,
            "total_paths": 7,
            "max_degeneracy": 4,
            "fact_ids": ["f1", "f2", "f3"],
        }
        original = QueryTrace(bundle_summary=summary)
        restored = self._round_trip(original)
        assert restored.bundle_summary == summary

    def test_lyapunov_dimensions_round_trip(self):
        dims = {
            "temporal_consistency": 0.9,
            "contradiction_score": 0.1,
            "path_diversity": 0.8,
            "degeneracy": 0.7,
            "pattern_lock_score": 0.2,
        }
        original = QueryTrace(lyapunov_dimensions=dims)
        restored = self._round_trip(original)
        assert restored.lyapunov_dimensions == dims

    def test_dialectic_summary_round_trip(self):
        summary = {
            "converged_fact_id": "fact-X",
            "converged_score": 0.88,
            "opposition_challenges": 2,
            "reopened": True,
            "final_status": "challenged",
        }
        original = QueryTrace(dialectic_result_summary=summary)
        restored = self._round_trip(original)
        assert restored.dialectic_result_summary == summary

    def test_none_fields_preserved(self):
        original = QueryTrace(parent_trace_id=None, temporal_context=None,
                              dialectic_result_summary=None,
                              discovery_result_summary=None)
        restored = self._round_trip(original)
        assert restored.parent_trace_id is None
        assert restored.temporal_context is None
        assert restored.dialectic_result_summary is None
        assert restored.discovery_result_summary is None

    def test_metadata_round_trip(self):
        original = QueryTrace(metadata={"key": "value", "num": 42})
        restored = self._round_trip(original)
        assert restored.metadata == {"key": "value", "num": 42}

    def test_from_dict_via_json(self):
        """Verify that JSON serialise -> deserialise preserves the trace."""
        original = _full_trace()
        json_str = json.dumps(original.to_dict())
        restored = QueryTrace.from_dict(json.loads(json_str))
        assert restored.trace_id == original.trace_id
        assert restored.query == original.query
        assert restored.candidates == original.candidates

    def test_empty_dict_uses_defaults(self):
        """from_dict({}) must not raise; defaults fill in."""
        t = QueryTrace.from_dict({})
        # trace_id is generated inside from_dict when key is missing
        assert t.trace_id != ""
        uuid.UUID(t.trace_id)  # must be valid UUID


# ---------------------------------------------------------------------------
# Parent trace linkage (recursive iteration support)
# ---------------------------------------------------------------------------

class TestParentTraceLinkage:
    def test_child_links_to_parent(self):
        parent = QueryTrace(query="first pass", iteration=0)
        child = QueryTrace(
            query="second pass",
            parent_trace_id=parent.trace_id,
            iteration=1,
        )
        assert child.parent_trace_id == parent.trace_id
        assert child.iteration == 1

    def test_multi_hop_chain(self):
        t0 = QueryTrace(iteration=0)
        t1 = QueryTrace(parent_trace_id=t0.trace_id, iteration=1)
        t2 = QueryTrace(parent_trace_id=t1.trace_id, iteration=2)
        assert t1.parent_trace_id == t0.trace_id
        assert t2.parent_trace_id == t1.trace_id
        # All IDs are distinct
        assert len({t0.trace_id, t1.trace_id, t2.trace_id}) == 3

    def test_parent_trace_id_survives_round_trip(self):
        parent_id = str(uuid.uuid4())
        original = QueryTrace(parent_trace_id=parent_id, iteration=1)
        restored = QueryTrace.from_dict(original.to_dict())
        assert restored.parent_trace_id == parent_id
        assert restored.iteration == 1

    def test_root_trace_has_no_parent(self):
        root = QueryTrace()
        assert root.parent_trace_id is None
        assert root.iteration == 0


# ---------------------------------------------------------------------------
# TraceStore
# ---------------------------------------------------------------------------

class TestTraceStore:
    """Tests for TraceStore — persistence layer for QueryTrace objects."""

    @pytest.fixture()
    def store(self, tmp_path):
        """A fresh TraceStore backed by a temp directory."""
        return TraceStore(tmp_path)

    # --- save ---------------------------------------------------------------

    def test_save_writes_file_with_correct_name(self, store, tmp_path):
        trace = QueryTrace(query="hello")
        store.save(trace)
        expected = tmp_path / ".traces" / f"{trace.trace_id}.json"
        assert expected.exists(), f"Expected file {expected} not found"

    def test_save_writes_valid_json(self, store, tmp_path):
        trace = QueryTrace(query="json check")
        store.save(trace)
        path = tmp_path / ".traces" / f"{trace.trace_id}.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        assert data["trace_id"] == trace.trace_id
        assert data["query"] == "json check"

    def test_save_is_idempotent(self, store):
        trace = QueryTrace(query="first")
        store.save(trace)
        # Mutate in-place is not possible (dataclass), so create a new object
        # with the same trace_id to simulate overwriting.
        trace2 = QueryTrace.__new__(QueryTrace)
        trace2.__dict__.update(trace.__dict__)
        trace2.query = "second"
        store.save(trace2)
        assert store.count() == 1
        loaded = store.load_all()[0]
        assert loaded.query == "second"

    # --- load_recent --------------------------------------------------------

    def test_load_recent_returns_most_recent(self, store):
        older = QueryTrace(executed_at=1_000_000.0, query="older")
        newer = QueryTrace(executed_at=2_000_000.0, query="newer")
        store.save(older)
        store.save(newer)
        result = store.load_recent(1)
        assert len(result) == 1
        assert result[0].query == "newer"

    def test_load_recent_n_greater_than_count_returns_all(self, store):
        for i in range(3):
            store.save(QueryTrace(executed_at=float(i), query=f"trace-{i}"))
        result = store.load_recent(100)
        assert len(result) == 3

    def test_load_recent_empty_store_returns_empty_list(self, store):
        assert store.load_recent() == []

    # --- load_all -----------------------------------------------------------

    def test_load_all_returns_all_sorted_descending(self, store):
        timestamps = [3_000_000.0, 1_000_000.0, 2_000_000.0]
        for ts in timestamps:
            store.save(QueryTrace(executed_at=ts))
        result = store.load_all()
        assert len(result) == 3
        executed_times = [t.executed_at for t in result]
        assert executed_times == sorted(executed_times, reverse=True)

    def test_load_all_empty_store(self, store):
        assert store.load_all() == []

    # --- corrupt file handling ----------------------------------------------

    def test_corrupt_file_is_skipped(self, store, tmp_path):
        good = QueryTrace(executed_at=5.0, query="good trace")
        store.save(good)
        # Write a corrupt JSON file manually
        corrupt_path = tmp_path / ".traces" / "corrupt-id.json"
        corrupt_path.write_text("{ not valid json !!!", encoding="utf-8")
        result = store.load_all()
        assert len(result) == 1
        assert result[0].trace_id == good.trace_id

    def test_multiple_corrupt_files_others_still_load(self, store, tmp_path):
        traces_dir = tmp_path / ".traces"
        for i in range(2):
            (traces_dir / f"bad-{i}.json").write_text("{}", encoding="utf-8")
        good = QueryTrace(query="survivor")
        store.save(good)
        result = store.load_all()
        # The two empty-dict traces will deserialise (from_dict({}) is valid),
        # so only truly corrupt files are skipped.  Re-test with actual bad JSON.
        (traces_dir / "really-bad.json").write_text("???", encoding="utf-8")
        result2 = store.load_all()
        # At minimum the good trace must be present
        ids = {t.trace_id for t in result2}
        assert good.trace_id in ids

    # --- count --------------------------------------------------------------

    def test_count_zero_on_empty_store(self, store):
        assert store.count() == 0

    def test_count_reflects_saved_traces(self, store):
        for _ in range(5):
            store.save(QueryTrace())
        assert store.count() == 5

    def test_count_does_not_double_count_overwrite(self, store, tmp_path):
        trace = QueryTrace()
        store.save(trace)
        store.save(trace)  # idempotent overwrite
        assert store.count() == 1
