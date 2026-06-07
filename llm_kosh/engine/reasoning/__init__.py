from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from llm_kosh.engine.reasoning.causal_dag import CausalDAG, EdgeType, TrajectoryState
from llm_kosh.engine.reasoning.causal_retrieval import CausalRetrieval
from llm_kosh.engine.reasoning.escape import EscapeMechanism
from llm_kosh.engine.reasoning.fiber_bundle import FiberBundle, build_fiber_bundle
from llm_kosh.engine.reasoning.lyapunov_critic import LyapunovCritic, StabilityResult


@dataclass
class QueryResult:
    anchors: List[str]
    bundle: FiberBundle
    stability: StabilityResult
    escape_triggered: bool
    escape_surfaced: List[str]


class ReasoningEngine:
    """
    Public API for the Temporal Causal Reasoning Engine.
    Initialize once per cartridge root; call query/ingest/critique/explore.
    """

    def __init__(self, root: Path) -> None:
        self.root = root
        self.dag = CausalDAG(root)
        self._retrieval = CausalRetrieval(self.dag)
        self._critic = LyapunovCritic(self.dag)
        self._escape = EscapeMechanism(self.dag)

    # ------------------------------------------------------------------ public API

    def ingest(
        self,
        content: str,
        documented_at: datetime,
        valid_from: datetime,
        valid_until: Optional[datetime],
        confidence: float,
        causal_edges: List[dict],
    ) -> str:
        """
        Add a fact to the causal graph.
        causal_edges: list of {"target_id": str, "edge_type": str, "confidence": float}
        Returns the new fact_id.
        """
        now = datetime.now(timezone.utc)
        fact_id = self.dag.add_fact(
            content=content,
            ingested_at=now,
            documented_at=documented_at,
            valid_from=valid_from,
            valid_until=valid_until,
            confidence=confidence,
            source="agent",
        )
        for edge_spec in causal_edges:
            try:
                self.dag.add_edge(
                    source_id=fact_id,
                    target_id=edge_spec["target_id"],
                    edge_type=EdgeType(edge_spec.get("edge_type", "ENABLES")),
                    confidence=float(edge_spec.get("confidence", 0.7)),
                    valid_from=valid_from,
                    valid_until=valid_until,
                    established_by="agent",
                )
            except (KeyError, ValueError):
                pass
        # Refresh retrieval index
        self._retrieval = CausalRetrieval(self.dag)
        return fact_id

    def query(
        self,
        query: str,
        temporal_context: Optional[str] = None,
        depth: int = 3,
    ) -> QueryResult:
        """
        Full pipeline: retrieve -> bundle -> critique -> escape if needed -> return.
        temporal_context: ISO 8601 datetime string, Unix timestamp str, or None (uses now).
        """
        query_time = self._parse_temporal_context(temporal_context)
        trajectory = TrajectoryState(session_id=f"q-{int(query_time)}")

        candidates = self._retrieval.retrieve(query, query_time, depth=depth)
        anchor_ids = [c[0].id for c in candidates[:5]]

        bundle = build_fiber_bundle(
            self.dag, candidates, anchor_ids=anchor_ids,
            query_time=query_time, max_hops=depth,
        )
        diagnosis = self._critic.evaluate(bundle)

        escaped = False
        escape_surfaced: List[str] = []

        if diagnosis.status in ("unstable", "marginal"):
            query_profile = {}  # resonance profile not needed by escape strategies directly
            prev_ids = set(bundle.fibers.keys())
            bundle = self._escape.escape(bundle, diagnosis, trajectory, query_time, query_profile, depth)
            escape_surfaced = [fid for fid in bundle.fibers if fid not in prev_ids and fid != "__deep_instability__"]
            diagnosis = self._critic.evaluate(bundle)
            escaped = True

        return QueryResult(
            anchors=anchor_ids,
            bundle=bundle,
            stability=diagnosis,
            escape_triggered=escaped,
            escape_surfaced=escape_surfaced,
        )

    def critique(self, fact_ids: List[str]) -> StabilityResult:
        """Run the Lyapunov critic on a specific set of facts (no path enumeration)."""
        from llm_kosh.engine.reasoning.fiber_bundle import Fiber, CausalPath
        fibers = {}
        for fid in fact_ids:
            fact = self.dag.get_fact(fid)
            if fact:
                path = CausalPath(edges=[], confidence_product=fact.confidence,
                                  temporal_consistency=1.0)
                fibers[fid] = Fiber(fact=fact, paths=[path], degeneracy=1,
                                    max_confidence=fact.confidence)
        bundle = FiberBundle(fibers=fibers)
        return self._critic.evaluate(bundle)

    def explore(
        self, from_fact_id: str, to_fact_id: str, max_hops: int = 5
    ) -> FiberBundle:
        """Enumerate all causal paths between two known facts."""
        from llm_kosh.engine.reasoning.fiber_bundle import _enumerate_paths, Fiber
        query_time = time.time()
        to_fact = self.dag.get_fact(to_fact_id)
        if to_fact is None:
            return FiberBundle(fibers={})
        paths = _enumerate_paths(
            self.dag, from_fact_id, {to_fact_id}, max_hops, query_time
        )
        fibers = {}
        if to_fact_id in paths:
            path_list = paths[to_fact_id]
            fibers[to_fact_id] = Fiber(
                fact=to_fact,
                paths=path_list,
                degeneracy=len(path_list),
                max_confidence=max((p.confidence_product for p in path_list), default=0.0),
            )
        return FiberBundle(fibers=fibers)

    # ------------------------------------------------------------------ helpers

    @staticmethod
    def _parse_temporal_context(ctx: Optional[str]) -> float:
        if ctx is None:
            return time.time()
        try:
            return float(ctx)
        except (TypeError, ValueError):
            pass
        try:
            return datetime.fromisoformat(ctx.replace("Z", "+00:00")).timestamp()
        except Exception:
            return time.time()
