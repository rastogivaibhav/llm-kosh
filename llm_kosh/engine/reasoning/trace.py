from __future__ import annotations

import uuid
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


@dataclass
class QueryTrace:
    """
    Immutable record of a single reasoning pass.

    Captures every decision point from retrieval through stability evaluation
    so that the recursive self-healing loop (TraceCritic, self-healer, discovery
    engine, self-model, orchestrator) can inspect, replay, or improve any trace.

    All time values are stored as float Unix timestamps.
    """

    # --- Identity & lineage ------------------------------------------------
    trace_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    parent_trace_id: Optional[str] = None  # links recursive iterations

    # --- Query context -----------------------------------------------------
    query: str = ""
    temporal_context: Optional[str] = None
    query_time: Optional[float] = None  # semantic temporal anchor; None means current time
    executed_at: float = field(default_factory=time.time)  # wall clock
    execution_time_secs: float = 0.0
    reasoning_mode: str = "balanced"

    # --- Retrieval layer ---------------------------------------------------
    # (fact_id, dist, score) for every candidate considered
    candidates: List[Tuple[str, int, float]] = field(default_factory=list)
    anchor_ids: List[str] = field(default_factory=list)

    # --- Bundle summary ----------------------------------------------------
    # fiber_count, total_paths, max_degeneracy, fact_ids
    bundle_summary: dict = field(default_factory=dict)

    # --- Stability (Lyapunov) dimensions -----------------------------------
    # Keys: temporal_consistency, contradiction_score, path_diversity,
    #       degeneracy, pattern_lock_score
    lyapunov_dimensions: dict = field(default_factory=dict)
    stability_score: float = 0.0
    stability_status: str = "no_evidence"

    # --- Escape mechanism --------------------------------------------------
    escape_triggered: bool = False
    escape_surfaced: List[str] = field(default_factory=list)

    # --- Dialectic result --------------------------------------------------
    # Populated when a DialecticResult was involved in this pass.
    # Keys: converged_fact_id, converged_score, opposition_challenges (int),
    #       reopened (bool), final_status
    dialectic_result_summary: Optional[dict] = None

    # --- Recursive loop fields ---------------------------------------------
    # Populated by the discovery engine; None on a fresh (iteration 0) trace.
    discovery_result_summary: Optional[dict] = None
    iteration: int = 0

    # --- Extensibility -----------------------------------------------------
    metadata: dict = field(default_factory=dict)

    # ------------------------------------------------------------------
    # Serialization helpers
    # ------------------------------------------------------------------

    def to_dict(self) -> dict:
        """Return a JSON-serialisable dict representation."""
        return {
            "trace_id": self.trace_id,
            "parent_trace_id": self.parent_trace_id,
            "query": self.query,
            "temporal_context": self.temporal_context,
            "query_time": self.query_time,
            "executed_at": self.executed_at,
            "execution_time_secs": self.execution_time_secs,
            "reasoning_mode": self.reasoning_mode,
            # Tuples are not JSON-native; serialise as lists-of-lists.
            "candidates": [list(c) for c in self.candidates],
            "anchor_ids": list(self.anchor_ids),
            "bundle_summary": dict(self.bundle_summary),
            "lyapunov_dimensions": dict(self.lyapunov_dimensions),
            "stability_score": self.stability_score,
            "stability_status": self.stability_status,
            "escape_triggered": self.escape_triggered,
            "escape_surfaced": list(self.escape_surfaced),
            "dialectic_result_summary": self.dialectic_result_summary,
            "discovery_result_summary": self.discovery_result_summary,
            "iteration": self.iteration,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict) -> QueryTrace:
        """Reconstruct a QueryTrace from a previously serialised dict."""
        # Candidates are stored as lists-of-lists; restore as tuples.
        raw_candidates = data.get("candidates", [])
        candidates: List[Tuple[str, int, float]] = [
            (str(c[0]), int(c[1]), float(c[2])) for c in raw_candidates
        ]
        return cls(
            trace_id=data.get("trace_id", str(uuid.uuid4())),
            parent_trace_id=data.get("parent_trace_id"),
            query=data.get("query", ""),
            temporal_context=data.get("temporal_context"),
            query_time=float(data["query_time"]) if data.get("query_time") is not None else None,
            executed_at=float(data.get("executed_at", 0.0)),
            execution_time_secs=float(data.get("execution_time_secs", 0.0)),
            reasoning_mode=data.get("reasoning_mode", "balanced"),
            candidates=candidates,
            anchor_ids=list(data.get("anchor_ids", [])),
            bundle_summary=dict(data.get("bundle_summary", {})),
            lyapunov_dimensions=dict(data.get("lyapunov_dimensions", {})),
            stability_score=float(data.get("stability_score", 0.0)),
            stability_status=data.get("stability_status", "no_evidence"),
            escape_triggered=bool(data.get("escape_triggered", False)),
            escape_surfaced=list(data.get("escape_surfaced", [])),
            dialectic_result_summary=data.get("dialectic_result_summary"),
            discovery_result_summary=data.get("discovery_result_summary"),
            iteration=int(data.get("iteration", 0)),
            metadata=dict(data.get("metadata", {})),
        )
