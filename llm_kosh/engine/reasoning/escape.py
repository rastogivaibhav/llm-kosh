from __future__ import annotations

from typing import Dict

from llm_kosh.engine.reasoning.causal_dag import (
    CausalDAG, TrajectoryState, _ts
)
from llm_kosh.engine.reasoning.fiber_bundle import (
    CausalPath, Fiber, FiberBundle, _enumerate_paths
)
from llm_kosh.engine.reasoning.lyapunov_critic import StabilityResult

_LOW_CONF_THRESHOLD = 0.4   # edges below this are "in the dark"
_TEMPORAL_WIDEN_SECS = 86400  # widen validity window by 24h on temporal escape


class EscapeMechanism:
    """
    Targeted escape from coherence traps.
    Acts only when LyapunovCritic returns unstable or marginal.
    Each escape strategy targets a specific failure dimension.
    """

    def __init__(self, dag: CausalDAG) -> None:
        self.dag = dag

    def escape(
        self,
        bundle: FiberBundle,
        diagnosis: StabilityResult,
        trajectory: TrajectoryState,
        query_time: float,
        query_profile: dict,
        depth: int,
    ) -> FiberBundle:
        """
        Targeted escape based on diagnosis dimensions.
        Modifies the bundle in place and returns it.
        Increments trajectory.escape_count.
        """
        if trajectory.escape_count >= 3:
            trajectory.escape_count += 1
            # Signal deep instability — structural problem in the causal graph
            bundle.fibers["__deep_instability__"] = Fiber(
                fact=None,  # type: ignore[arg-type]
                paths=[],
                degeneracy=0,
                max_confidence=0.0,
            )
            return bundle

        dims = diagnosis.dimensions

        if dims.get("temporal_consistency", 1.0) < 0.5:
            bundle = self._escape_temporal(bundle, query_time)

        if dims.get("contradiction_score", 0.0) > 0.3:
            bundle = self._escape_contradiction(bundle, query_time)

        if dims.get("path_diversity", 1.0) < 0.4:
            bundle = self._escape_low_confidence(bundle, query_time, depth)

        if dims.get("degeneracy", 1.0) < 0.4:
            bundle = self._escape_alternative_routes(bundle, query_time, depth)

        trajectory.escape_count += 1
        return bundle

    # ------------------------------------------------------------------ strategies

    def _escape_temporal(self, bundle: FiberBundle, query_time: float) -> FiberBundle:
        """Widen the temporal window to surface facts just outside validity."""
        widened_time = query_time + _TEMPORAL_WIDEN_SECS
        extra_ids = set(self.dag.interval_tree.query_valid_at(widened_time))
        current_ids = set(bundle.fibers.keys())
        for fid in extra_ids - current_ids:
            fact = self.dag.get_fact(fid)
            if fact:
                bundle.fibers[fid] = Fiber(
                    fact=fact, paths=[], degeneracy=0, max_confidence=fact.confidence
                )
        return bundle

    def _escape_contradiction(self, bundle: FiberBundle, query_time: float) -> FiberBundle:
        """Surface both sides of active contradictions explicitly."""
        fact_ids = list(bundle.fibers.keys())
        for i, fid_a in enumerate(fact_ids):
            for fid_b in fact_ids[i + 1 :]:
                if self.dag.has_contradiction(fid_a, fid_b):
                    # Both are already in the bundle — mark them by adding a zero path
                    for fid in (fid_a, fid_b):
                        fiber = bundle.fibers.get(fid)
                        if fiber is not None and not fiber.paths:
                            fact = self.dag.get_fact(fid)
                            if fact:
                                fiber.paths.append(
                                    CausalPath(edges=[], confidence_product=fact.confidence,
                                               temporal_consistency=1.0)
                                )
        return bundle

    def _escape_low_confidence(
        self, bundle: FiberBundle, query_time: float, depth: int
    ) -> FiberBundle:
        """Traverse low-confidence edges (< threshold) from existing bundle anchors."""
        current_ids = set(bundle.fibers.keys())
        to_add: Dict[str, Fiber] = {}

        for fid in list(current_ids):
            for edge in self.dag.edges.get(fid, []):
                if edge.confidence < _LOW_CONF_THRESHOLD:
                    target_id = edge.target_id
                    if target_id in current_ids or target_id in to_add:
                        continue
                    fact = self.dag.get_fact(target_id)
                    if fact is None:
                        continue
                    vf = _ts(fact.valid_from) or 0.0
                    vu = _ts(fact.valid_until)
                    if vf <= query_time and (vu is None or vu > query_time):
                        path = CausalPath(
                            edges=[edge],
                            confidence_product=edge.confidence,
                            temporal_consistency=1.0,
                        )
                        to_add[target_id] = Fiber(
                            fact=fact, paths=[path], degeneracy=1,
                            max_confidence=edge.confidence,
                        )

        bundle.fibers.update(to_add)
        return bundle

    def _escape_alternative_routes(
        self, bundle: FiberBundle, query_time: float, depth: int
    ) -> FiberBundle:
        """Search for alternative causal paths to high-confidence targets."""
        high_conf_targets = {
            fid for fid, fiber in bundle.fibers.items()
            if fiber.max_confidence >= 0.6 and fiber.degeneracy < 2
        }
        if not high_conf_targets:
            return bundle

        # BFS from all facts, look for new paths to high_conf_targets
        for start_id in list(self.dag.nodes.keys()):
            if start_id in bundle.fibers:
                continue
            paths_to = _enumerate_paths(
                self.dag, start_id, high_conf_targets, depth, query_time
            )
            for target_id, new_paths in paths_to.items():
                if target_id in bundle.fibers:
                    bundle.fibers[target_id].paths.extend(new_paths)
                    fiber = bundle.fibers[target_id]
                    fiber.degeneracy = len(fiber.paths)
                    fiber.max_confidence = max(
                        (p.confidence_product for p in fiber.paths), default=0.0
                    )

        return bundle
