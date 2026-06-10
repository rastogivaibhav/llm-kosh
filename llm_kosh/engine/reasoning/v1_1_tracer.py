"""Query Tracer - Captures complete execution traces."""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

from llm_kosh.engine.reasoning.causal_dag import TemporalFact
from llm_kosh.engine.reasoning.fiber_bundle import FiberBundle
from llm_kosh.engine.reasoning.lyapunov_critic import StabilityResult


@dataclass
class QueryTrace:
    """Complete record of one query execution."""

    trace_id: str
    query: str
    query_time: float

    retrieval_candidates: List[TemporalFact] = field(default_factory=list)
    anchors_selected: List[str] = field(default_factory=list)
    retrieval_count: int = 0

    fiber_bundle: Optional[FiberBundle] = None
    bundle_size: int = 0
    bundle_max_confidence: float = 0.0

    stability: Optional[StabilityResult] = None
    temporal_consistency: float = 0.0
    contradiction_count: int = 0
    path_diversity: float = 0.0
    pattern_lock_detected: bool = False

    escape_triggered: bool = False
    escape_strategies_used: List[str] = field(default_factory=list)

    execution_time_ms: float = 0.0
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class QueryTracer:
    """Instrument ReasoningEngine to capture execution traces."""

    def __init__(self, max_traces: int = 1000):
        self.traces: List[QueryTrace] = []
        self.trace_map: Dict[str, QueryTrace] = {}
        self.max_traces = max_traces

    def start_trace(self, query: str, query_time: float) -> str:
        """Start tracing a query execution."""
        trace_id = f"trace.{str(uuid.uuid4())[:12]}"
        trace = QueryTrace(trace_id=trace_id, query=query, query_time=query_time)
        self.traces.append(trace)
        self.trace_map[trace_id] = trace

        if len(self.traces) > self.max_traces:
            old_trace = self.traces.pop(0)
            del self.trace_map[old_trace.trace_id]

        return trace_id

    def record_retrieval(self, trace_id: str, candidates: List[Tuple], anchors: List[str]) -> None:
        """Record retrieval phase results."""
        if trace_id not in self.trace_map:
            return
        trace = self.trace_map[trace_id]
        trace.retrieval_candidates = [c[0] if isinstance(c, tuple) else c for c in candidates]
        trace.anchors_selected = anchors
        trace.retrieval_count = len(candidates)

    def record_bundling(self, trace_id: str, bundle: FiberBundle) -> None:
        """Record fiber bundle construction."""
        if trace_id not in self.trace_map:
            return
        trace = self.trace_map[trace_id]
        trace.fiber_bundle = bundle
        trace.bundle_size = len(bundle.fibers) if bundle and bundle.fibers else 0
        if bundle and bundle.fibers:
            max_conf = max((fiber.max_confidence for fiber in bundle.fibers.values()), default=0.0)
            trace.bundle_max_confidence = max_conf

    def record_critique(self, trace_id: str, stability: StabilityResult) -> None:
        """Record Lyapunov stability assessment."""
        if trace_id not in self.trace_map:
            return
        trace = self.trace_map[trace_id]
        trace.stability = stability
        if stability and stability.dimensions:
            dims = stability.dimensions
            trace.temporal_consistency = dims.get("temporal_consistency", 0.0)
            trace.contradiction_count = int(dims.get("contradiction_score", 0.0) * 100)
            trace.path_diversity = dims.get("path_diversity", 0.0)
            trace.pattern_lock_detected = dims.get("pattern_lock_score", 0.0) > 0.5

    def record_escape(self, trace_id: str, escape_triggered: bool, strategies: List[str]) -> None:
        """Record escape mechanism activation."""
        if trace_id not in self.trace_map:
            return
        trace = self.trace_map[trace_id]
        trace.escape_triggered = escape_triggered
        trace.escape_strategies_used = strategies

    def finalize_trace(self, trace_id: str, elapsed_ms: float) -> Optional[QueryTrace]:
        """Mark trace as complete."""
        if trace_id not in self.trace_map:
            return None
        trace = self.trace_map[trace_id]
        trace.execution_time_ms = elapsed_ms
        return trace

    def get_last_trace(self) -> Optional[QueryTrace]:
        """Get the most recent trace."""
        return self.traces[-1] if self.traces else None

    def __len__(self) -> int:
        return len(self.traces)
