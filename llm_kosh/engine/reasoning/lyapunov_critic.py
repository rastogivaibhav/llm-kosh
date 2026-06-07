from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional

from llm_kosh.engine.reasoning.causal_dag import CausalDAG, EdgeType, _ts
from llm_kosh.engine.reasoning.fiber_bundle import FiberBundle


@dataclass
class StabilityResult:
    score: float
    status: str            # "stable" | "marginal" | "unstable"
    dimensions: Dict[str, float]
    implicated_facts: List[str]


class LyapunovCritic:
    """
    Computes stability score V for a FiberBundle.

    V = w1·temporal_consistency + w2·path_diversity + w3·degeneracy - w4·contradiction_score

    Default weights and thresholds are configurable.
    """

    DEFAULT_WEIGHTS = {
        "temporal_consistency": 0.35,
        "path_diversity": 0.25,
        "degeneracy": 0.25,
        "contradiction_score": 0.15,
    }
    DEFAULT_STABLE = 0.7
    DEFAULT_UNSTABLE = 0.4

    def __init__(
        self,
        dag: CausalDAG,
        weights: Optional[Dict[str, float]] = None,
        stable_threshold: float = DEFAULT_STABLE,
        unstable_threshold: float = DEFAULT_UNSTABLE,
    ) -> None:
        self.dag = dag
        self.weights = weights or dict(self.DEFAULT_WEIGHTS)
        self.stable_threshold = stable_threshold
        self.unstable_threshold = unstable_threshold

    def evaluate(self, bundle: FiberBundle) -> StabilityResult:
        if not bundle.fibers:
            return StabilityResult(
                score=1.0,
                status="stable",
                dimensions={
                    "temporal_consistency": 1.0,
                    "contradiction_score": 0.0,
                    "path_diversity": 1.0,
                    "degeneracy": 1.0,
                },
                implicated_facts=[],
            )

        temporal_consistency = self._temporal_consistency(bundle)
        contradiction_score = self._contradiction_score(bundle)
        path_diversity = self._path_diversity(bundle)
        degeneracy = self._degeneracy(bundle)

        w = self.weights
        score = (
            w["temporal_consistency"] * temporal_consistency
            + w["path_diversity"] * path_diversity
            + w["degeneracy"] * degeneracy
            - w["contradiction_score"] * contradiction_score
        )
        score = max(0.0, min(1.0, score))

        if score >= self.stable_threshold:
            status = "stable"
        elif score >= self.unstable_threshold:
            status = "marginal"
        else:
            status = "unstable"

        return StabilityResult(
            score=round(score, 4),
            status=status,
            dimensions={
                "temporal_consistency": round(temporal_consistency, 4),
                "contradiction_score": round(contradiction_score, 4),
                "path_diversity": round(path_diversity, 4),
                "degeneracy": round(degeneracy, 4),
            },
            implicated_facts=[],
        )

    # ------------------------------------------------------------------ dimensions

    def _temporal_consistency(self, bundle: FiberBundle) -> float:
        all_edges = [
            edge
            for fiber in bundle.fibers.values()
            for path in fiber.paths
            for edge in path.edges
        ]
        if not all_edges:
            return 1.0
        consistent = sum(1 for e in all_edges if self._edge_temporally_ok(e))
        return consistent / len(all_edges)

    def _edge_temporally_ok(self, edge) -> bool:
        src = self.dag.get_fact(edge.source_id)
        tgt = self.dag.get_fact(edge.target_id)
        if src is None or tgt is None:
            return True
        src_ts = _ts(src.valid_from) or 0.0
        tgt_ts = _ts(tgt.valid_from) or 0.0
        return src_ts <= tgt_ts

    def _contradiction_score(self, bundle: FiberBundle) -> float:
        fact_ids = list(bundle.fibers.keys())
        pairs = 0
        contradictions = 0
        for i, fid_a in enumerate(fact_ids):
            for fid_b in fact_ids[i + 1 :]:
                pairs += 1
                if self.dag.has_contradiction(fid_a, fid_b):
                    contradictions += 1
        return contradictions / pairs if pairs > 0 else 0.0

    def _path_diversity(self, bundle: FiberBundle) -> float:
        total_paths = sum(len(fiber.paths) for fiber in bundle.fibers.values())
        # Normalize: expect at least 1 path per fact
        max_expected = max(len(bundle.fibers) * 2, 1)
        return min(1.0, total_paths / max_expected)

    def _degeneracy(self, bundle: FiberBundle) -> float:
        high_conf = [
            fiber for fiber in bundle.fibers.values()
            if fiber.max_confidence >= 0.6
        ]
        if not high_conf:
            return 0.5  # neutral when no high-confidence facts
        multi = sum(1 for fiber in high_conf if fiber.degeneracy >= 2)
        return multi / len(high_conf)
