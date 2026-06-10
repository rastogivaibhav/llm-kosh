from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from llm_kosh.engine.reasoning.causal_dag import EdgeOrigin, EdgeRole
from llm_kosh.engine.reasoning.fiber_bundle import CausalPath, FiberBundle


@dataclass
class ConvergedPath:
    """The selected compressed/executable path after convergence."""

    fact_ids: List[str]
    edge_ids: List[str]
    confidence: float
    temporal_consistency: float
    origin_counts: Dict[str, int] = field(default_factory=dict)
    role_counts: Dict[str, int] = field(default_factory=dict)


@dataclass
class CompressionCandidate:
    """A safe candidate for A -> C compression derived from a mechanistic path."""

    source_id: str
    target_id: str
    derived_from_edges: List[str]
    recommended_origin: str = EdgeOrigin.INFERRED.value
    recommended_role: str = EdgeRole.COMPRESSED.value
    warning: str = "compressed shortcut; not discovered truth unless promoted by evidence"


@dataclass
class ConvergedAnswer:
    """Convergent output: one selected answer plus preserved losses."""

    primary_fact_id: Optional[str]
    primary_content: Optional[str]
    selected_path: Optional[ConvergedPath]
    score: float
    discarded_fact_ids: List[str]
    discarded_path_count: int
    compression_candidates: List[CompressionCandidate]
    compression_gain: float
    evidence_loss: float
    notes: List[str] = field(default_factory=list)

    @property
    def has_answer(self) -> bool:
        return self.primary_fact_id is not None


class ConvergentEngine:
    """
    Cognitive substrate for convergent reasoning.

    It compresses a non-convergent FiberBundle into the strongest provisional
    answer while preserving what was discarded. It never promotes inferred or
    compressed paths into discovered truth; it only recommends compression
    candidates with provenance warnings.
    """

    def converge(self, bundle: FiberBundle) -> ConvergedAnswer:
        if not bundle.fibers:
            return ConvergedAnswer(
                primary_fact_id=None,
                primary_content=None,
                selected_path=None,
                score=0.0,
                discarded_fact_ids=[],
                discarded_path_count=0,
                compression_candidates=[],
                compression_gain=0.0,
                evidence_loss=1.0,
                notes=["no evidence available for convergence"],
            )

        ranked = sorted(
            bundle.fibers.items(),
            key=lambda item: self._fiber_score(item[1]),
            reverse=True,
        )
        primary_id, primary_fiber = ranked[0]
        selected_path = self._select_path(primary_fiber.paths)
        total_paths = sum(len(f.paths) for f in bundle.fibers.values())
        selected_path_count = 1 if selected_path is not None else 0
        discarded_path_count = max(0, total_paths - selected_path_count)
        discarded_fact_ids = [fid for fid, _ in ranked[1:]]
        compression_candidates = []
        if selected_path is not None:
            compression_candidates = self._compression_candidates(primary_id, selected_path)

        score = self._fiber_score(primary_fiber)
        compression_gain = self._compression_gain(bundle, selected_path_count)
        evidence_loss = discarded_path_count / total_paths if total_paths else 0.0
        notes: List[str] = []
        if evidence_loss > 0:
            notes.append("convergence discarded alternative paths; run opposition before final answer")
        if compression_candidates:
            notes.append("mechanistic path can be compressed, but only as inferred/compressed unless promoted")

        return ConvergedAnswer(
            primary_fact_id=primary_id,
            primary_content=primary_fiber.fact.content,
            selected_path=selected_path,
            score=round(score, 4),
            discarded_fact_ids=discarded_fact_ids,
            discarded_path_count=discarded_path_count,
            compression_candidates=compression_candidates,
            compression_gain=round(compression_gain, 4),
            evidence_loss=round(evidence_loss, 4),
            notes=notes,
        )

    def _fiber_score(self, fiber) -> float:
        # Confidence + degeneracy bonus. This intentionally compresses; the
        # OppositionEngine later attacks what compression loses.
        degeneracy_bonus = min(0.25, 0.05 * max(0, fiber.degeneracy - 1))
        fact_conf = getattr(fiber.fact, "confidence", 0.0)
        return min(1.0, 0.65 * fiber.max_confidence + 0.25 * fact_conf + degeneracy_bonus)

    def _select_path(self, paths: List[CausalPath]) -> Optional[ConvergedPath]:
        if not paths:
            return None
        path = max(paths, key=lambda p: (p.confidence_product, p.temporal_consistency, len(p.edges)))
        fact_ids: List[str] = []
        if path.edges:
            fact_ids.append(path.edges[0].source_id)
            fact_ids.extend(edge.target_id for edge in path.edges)
        origin_counts: Dict[str, int] = {}
        role_counts: Dict[str, int] = {}
        for edge in path.edges:
            origin = edge.provenance.origin.value
            role = edge.provenance.role.value
            origin_counts[origin] = origin_counts.get(origin, 0) + 1
            role_counts[role] = role_counts.get(role, 0) + 1
        return ConvergedPath(
            fact_ids=fact_ids,
            edge_ids=[edge.id for edge in path.edges],
            confidence=path.confidence_product,
            temporal_consistency=path.temporal_consistency,
            origin_counts=origin_counts,
            role_counts=role_counts,
        )

    def _compression_candidates(self, target_id: str, path: ConvergedPath) -> List[CompressionCandidate]:
        # A path A -> B -> C may be compressed into A -> C, but this remains an
        # inferred/compressed shortcut unless independent evidence promotes it.
        if len(path.fact_ids) < 3:
            return []
        return [
            CompressionCandidate(
                source_id=path.fact_ids[0],
                target_id=target_id,
                derived_from_edges=list(path.edge_ids),
            )
        ]

    def _compression_gain(self, bundle: FiberBundle, selected_path_count: int) -> float:
        total_paths = sum(len(f.paths) for f in bundle.fibers.values())
        if total_paths <= 1:
            return 0.0
        return max(0.0, 1.0 - (selected_path_count / total_paths))
