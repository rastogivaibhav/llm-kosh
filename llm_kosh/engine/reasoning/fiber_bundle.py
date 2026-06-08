from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple

from llm_kosh.engine.reasoning.causal_dag import CausalDAG, CausalEdge, TemporalFact, _ts


@dataclass
class CausalPath:
    """One causal derivation path: an ordered sequence of edges."""
    edges: List[CausalEdge]
    confidence_product: float   # product of all edge confidences
    temporal_consistency: float # 1.0 if all edges respect time ordering, else 0.5


@dataclass
class Fiber:
    """All paths reaching a single target fact."""
    fact: TemporalFact
    paths: List[CausalPath]
    degeneracy: int        # number of independent paths
    max_confidence: float  # highest confidence_product across paths


@dataclass
class FiberBundle:
    """The full path bundle — never collapsed."""
    fibers: Dict[str, Fiber]   # fact_id -> Fiber


def build_fiber_bundle(
    dag: CausalDAG,
    candidates: List[Tuple[TemporalFact, int, float]],
    anchor_ids: List[str],
    query_time: float,
    max_hops: int = 3,
) -> FiberBundle:
    """
    Enumerate all valid causal paths from anchor_ids to each candidate fact.
    Uses both forward and backward path enumeration for complete temporal chains.
    Groups by target fact into fibers. Never collapses to a single path.
    """
    target_ids = {fact.id for fact, _, _ in candidates}
    fibers: Dict[str, Fiber] = {}

    for anchor_id in anchor_ids:
        # Forward paths (anchor → candidate)
        paths_to = _enumerate_paths(dag, anchor_id, target_ids, max_hops, query_time)
        # Backward paths (candidate → anchor, reversed) — penalised 0.5x
        backward_paths_to = _enumerate_paths_backward(dag, anchor_id, target_ids, max_hops, query_time)

        for target_id, path_list in paths_to.items():
            target_fact = dag.get_fact(target_id)
            if target_fact is None:
                continue
            if target_id not in fibers:
                fibers[target_id] = Fiber(fact=target_fact, paths=[], degeneracy=0, max_confidence=0.0)
            fibers[target_id].paths.extend(path_list)

        for target_id, backward_path_list in backward_paths_to.items():
            target_fact = dag.get_fact(target_id)
            if target_fact is None:
                continue
            if target_id not in fibers:
                fibers[target_id] = Fiber(fact=target_fact, paths=[], degeneracy=0, max_confidence=0.0)
            for path in backward_path_list:
                fibers[target_id].paths.append(CausalPath(
                    edges=path.edges,
                    confidence_product=path.confidence_product * 0.5,
                    temporal_consistency=0.5,
                ))

    for fiber in fibers.values():
        fiber.degeneracy = len(fiber.paths)
        fiber.max_confidence = max(
            (p.confidence_product for p in fiber.paths), default=0.0
        )

    return FiberBundle(fibers=fibers)


def _enumerate_paths(
    dag: CausalDAG,
    start_id: str,
    targets: Set[str],
    max_hops: int,
    query_time: float,
) -> Dict[str, List[CausalPath]]:
    """
    DFS from start_id to any target in targets.
    Returns {target_id: [CausalPath, ...]}.
    """
    result: Dict[str, List[CausalPath]] = {}

    # Stack items: (current_fact_id, edges_so_far, confidence_so_far, temporal_ok, visited_ids)
    stack: List[Tuple[str, List[CausalEdge], float, bool, Set[str]]] = [
        (start_id, [], 1.0, True, {start_id})
    ]

    while stack:
        current_id, edge_path, conf, t_ok, visited = stack.pop()

        if len(edge_path) > max_hops:
            continue

        if edge_path and current_id in targets:
            path = CausalPath(
                edges=list(edge_path),
                confidence_product=round(conf, 6),
                temporal_consistency=1.0 if t_ok else 0.5,
            )
            result.setdefault(current_id, []).append(path)
            # Don't continue from here — target reached

        if len(edge_path) >= max_hops:
            continue

        for edge in dag.get_outgoing_edges(current_id, query_time):
            if edge.target_id in visited:
                continue  # no cycles

            # Check temporal consistency: source.valid_from <= target.valid_from
            source_fact = dag.get_fact(current_id)
            target_fact = dag.get_fact(edge.target_id)
            new_t_ok = t_ok
            if source_fact and target_fact:
                sf_ts = _ts(source_fact.valid_from) or 0.0
                tf_ts = _ts(target_fact.valid_from) or 0.0
                new_t_ok = t_ok and (sf_ts <= tf_ts)

            stack.append((
                edge.target_id,
                edge_path + [edge],
                conf * edge.confidence,
                new_t_ok,
                visited | {edge.target_id},
            ))

    return result


def _enumerate_paths_backward(
    dag: "CausalDAG",
    start_id: str,
    targets: "Set[str]",
    max_hops: int,
    query_time: float,
) -> "Dict[str, List[CausalPath]]":
    """
    DFS backward from start_id using incoming edges.
    Finds ancestor facts that causally precede start_id.
    Returns {target_id: [CausalPath, ...]} where targets are ancestor facts found.
    """
    result: Dict[str, List[CausalPath]] = {}

    # Stack: (current_fact_id, edges_so_far, confidence_so_far, temporal_ok, visited_ids)
    stack: List[Tuple[str, List[CausalEdge], float, bool, Set[str]]] = [
        (start_id, [], 1.0, True, {start_id})
    ]

    while stack:
        current_id, edge_path, conf, t_ok, visited = stack.pop()

        if len(edge_path) > max_hops:
            continue

        if edge_path and current_id in targets:
            path = CausalPath(
                edges=list(edge_path),
                confidence_product=round(conf, 6),
                temporal_consistency=1.0 if t_ok else 0.5,
            )
            result.setdefault(current_id, []).append(path)

        if len(edge_path) >= max_hops:
            continue

        for edge in dag.get_incoming_edges(current_id, query_time):
            if edge.source_id in visited:
                continue

            source_fact = dag.get_fact(edge.source_id)
            current_fact = dag.get_fact(current_id)
            new_t_ok = t_ok
            if source_fact and current_fact:
                sf_ts = _ts(source_fact.valid_from) or 0.0
                cf_ts = _ts(current_fact.valid_from) or 0.0
                new_t_ok = t_ok and (sf_ts <= cf_ts)

            stack.append((
                edge.source_id,
                edge_path + [edge],
                conf * edge.confidence,
                new_t_ok,
                visited | {edge.source_id},
            ))

    return result
