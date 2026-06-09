"""Query execution tracing for recursive self-healing loop."""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from llm_kosh.engine.reasoning.trace import QueryTrace


@dataclass
class TraceSnapshot:
    """Snapshot of execution state at a specific point during query processing."""
    stage: str  # "retrieval" | "bundling" | "critique" | "escape" | "completion"
    timestamp: float = field(default_factory=time.time)
    stage_data: dict = field(default_factory=dict)


class QueryTracer:
    """
    Instrument the reasoning engine to capture detailed execution traces.

    Wraps engine.query() calls and produces QueryTrace objects with complete
    diagnostics for the recursive self-healing loop to analyze.
    """

    def __init__(self, engine):
        """
        Initialize with reference to ReasoningEngine.

        Args:
            engine: ReasoningEngine instance to instrument
        """
        self.engine = engine
        self.traces: List[QueryTrace] = []
        self._snapshots: List[TraceSnapshot] = []

    def trace_query(
        self,
        query: str,
        temporal_context: Optional[str] = None,
        depth: int = 3,
        reasoning_mode: str = "balanced",
        parent_trace_id: Optional[str] = None,
        iteration: int = 0,
    ) -> Tuple:
        """
        Execute query with full tracing and return (QueryResult, QueryTrace).

        This method wraps engine.query() to capture timing, diagnostics,
        and intermediate state, producing a QueryTrace suitable for analysis
        by the recursive self-healing loop components.

        Args:
            query: The natural language query
            temporal_context: ISO 8601 datetime, Unix timestamp, or None (now)
            depth: Traversal depth in causal graph (default 3)
            reasoning_mode: "empirical" | "theoretical" | "balanced"
            parent_trace_id: If this is an iteration, trace_id of previous iteration
            iteration: Which iteration number is this? (0 for initial query)

        Returns:
            (QueryResult, QueryTrace) tuple
        """
        # Create empty trace; will be populated with data from result
        trace = QueryTrace(
            query=query,
            temporal_context=temporal_context,
            executed_at=time.time(),
            reasoning_mode=reasoning_mode,
            parent_trace_id=parent_trace_id,
            iteration=iteration,
        )

        # Execute query with timing
        t0 = time.time()
        result = self.engine.query(
            query,
            temporal_context=temporal_context,
            depth=depth,
            reasoning_mode=reasoning_mode,
        )
        execution_time = time.time() - t0

        # Populate trace from result
        trace.query_time = result.bundle.fibers[list(result.bundle.fibers.keys())[0]].fact.query_time \
            if result.bundle.fibers else time.time()
        trace.execution_time_secs = execution_time
        trace.anchor_ids = result.anchors
        trace.candidates = []  # Will be filled from retrieval if available

        # Bundle summary
        fibers = result.bundle.fibers
        trace.bundle_summary = {
            "fiber_count": len(fibers),
            "total_paths": sum(len(f.paths) for f in fibers.values()),
            "max_degeneracy": max((f.degeneracy for f in fibers.values()), default=0),
            "fact_ids": list(fibers.keys()),
        }

        # Stability and escape info
        trace.lyapunov_dimensions = result.stability.dimensions or {}
        trace.stability_score = result.stability.score
        trace.stability_status = result.stability.status
        trace.escape_triggered = result.escape_triggered
        trace.escape_surfaced = result.escape_surfaced or []

        # Store trace
        self.traces.append(trace)
        return result, trace

    def trace_query_with_retrieval(
        self,
        query: str,
        temporal_context: Optional[str] = None,
        depth: int = 3,
        reasoning_mode: str = "balanced",
        parent_trace_id: Optional[str] = None,
        iteration: int = 0,
    ) -> Tuple:
        """
        Execute query with tracing, capturing retrieval candidates.

        This variant uses engine.query_with_trace() internally to ensure
        candidates are captured before query execution, which is useful
        for diagnosing retrieval-level weaknesses.

        Returns:
            (QueryResult, QueryTrace) tuple
        """
        # Use the engine's built-in query_with_trace if available
        if hasattr(self.engine, 'query_with_trace'):
            result, trace = self.engine.query_with_trace(
                query,
                temporal_context=temporal_context,
                depth=depth,
                reasoning_mode=reasoning_mode,
            )
            # Update iteration info if this is a recursive pass
            trace.parent_trace_id = parent_trace_id
            trace.iteration = iteration
            self.traces.append(trace)
            return result, trace
        else:
            # Fallback to trace_query
            return self.trace_query(
                query,
                temporal_context=temporal_context,
                depth=depth,
                reasoning_mode=reasoning_mode,
                parent_trace_id=parent_trace_id,
                iteration=iteration,
            )

    def get_recent_traces(self, n: int = 10) -> List[QueryTrace]:
        """Return the n most recently executed traces."""
        return self.traces[-n:] if self.traces else []

    def get_all_traces(self) -> List[QueryTrace]:
        """Return all captured traces."""
        return list(self.traces)

    def clear_traces(self) -> None:
        """Clear in-memory trace history."""
        self.traces.clear()

    def _take_snapshot(self, stage: str, data: dict = None) -> None:
        """Record execution state at a pipeline stage (internal use)."""
        snapshot = TraceSnapshot(
            stage=stage,
            stage_data=data or {}
        )
        self._snapshots.append(snapshot)
