"""
Discovery Engine — T5.1 + T5.2 + T5.3

Generates and executes discovery questions that probe weaknesses found by the
TraceCritic.  All execution is read-only; the DAG is NEVER modified.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional

from llm_kosh.engine.reasoning.causal_dag import CausalDAG, EdgeOrigin, EdgeType
from llm_kosh.engine.reasoning.fiber_bundle import FiberBundle
from llm_kosh.engine.reasoning.critique import WeaknessReport, WeaknessType


# ---------------------------------------------------------------------------
# T5.1  DiscoveryType enum
# ---------------------------------------------------------------------------

class DiscoveryType(str, Enum):
    temporal_expansion = "What facts exist in validity window ±48h around the query time?"
    contradiction_resolution = "Do any SUPERSEDES edges exist connecting contradictory facts?"
    path_diversification = "What causal paths exist that don't use the dominant edge?"
    gap_marking = "Which concepts adjacent to the anchor set have no edges into the current bundle?"
    evidence_promotion_audit = (
        "Which INFERRED edges in the bundle have the most reinforcement but no evidence refs?"
    )


# ---------------------------------------------------------------------------
# T5.1  DiscoveryQuestion dataclass
# ---------------------------------------------------------------------------

@dataclass
class DiscoveryQuestion:
    question_text: str
    discovery_type: DiscoveryType
    target_weakness: str           # WeaknessType value as string
    expected_outcome: str          # what evidence would repair the weakness
    executable_locally: bool = True  # always True in v1.1

    def to_dict(self) -> dict:
        return {
            "question_text": self.question_text,
            "discovery_type": self.discovery_type.name,
            "target_weakness": self.target_weakness,
            "expected_outcome": self.expected_outcome,
            "executable_locally": self.executable_locally,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "DiscoveryQuestion":
        return cls(
            question_text=str(data["question_text"]),
            discovery_type=DiscoveryType[data["discovery_type"]],
            target_weakness=str(data["target_weakness"]),
            expected_outcome=str(data["expected_outcome"]),
            executable_locally=bool(data.get("executable_locally", True)),
        )


# ---------------------------------------------------------------------------
# T5.2  DiscoveryResult dataclass
# ---------------------------------------------------------------------------

@dataclass
class DiscoveryResult:
    question: DiscoveryQuestion
    facts_found: List[str]            # fact IDs found
    edges_found: List[str]            # edge IDs found
    candidate_hypotheses: List[str]   # speculative fact IDs (conf <= 0.4)
    repair_strength: float            # 0.0–1.0
    executed_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return {
            "question": self.question.to_dict(),
            "facts_found": list(self.facts_found),
            "edges_found": list(self.edges_found),
            "candidate_hypotheses": list(self.candidate_hypotheses),
            "repair_strength": float(self.repair_strength),
            "executed_at": float(self.executed_at),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "DiscoveryResult":
        return cls(
            question=DiscoveryQuestion.from_dict(data["question"]),
            facts_found=list(data.get("facts_found", [])),
            edges_found=list(data.get("edges_found", [])),
            candidate_hypotheses=list(data.get("candidate_hypotheses", [])),
            repair_strength=float(data.get("repair_strength", 0.0)),
            executed_at=float(data.get("executed_at", time.time())),
        )


# ---------------------------------------------------------------------------
# Weakness-type → DiscoveryType mapping
# ---------------------------------------------------------------------------

_WEAKNESS_TO_DISCOVERY: Dict[WeaknessType, DiscoveryType] = {
    WeaknessType.TEMPORAL_CONSISTENCY_LOW: DiscoveryType.temporal_expansion,
    WeaknessType.CONTRADICTION_UNRESOLVED: DiscoveryType.contradiction_resolution,
    WeaknessType.SINGLE_PATH_DOMINANCE: DiscoveryType.path_diversification,
    WeaknessType.SHALLOW_DEPTH: DiscoveryType.path_diversification,
    WeaknessType.HYPOTHETICAL_PROMOTED_SILENTLY: DiscoveryType.evidence_promotion_audit,
    WeaknessType.NOVELTY_DEFICIT: DiscoveryType.gap_marking,
    WeaknessType.COVERAGE_BIAS: DiscoveryType.gap_marking,
}

_EXPECTED_OUTCOMES: Dict[DiscoveryType, str] = {
    DiscoveryType.temporal_expansion: (
        "New facts in the ±48h window that extend or contradict the current bundle"
    ),
    DiscoveryType.contradiction_resolution: (
        "SUPERSEDES edges that resolve active contradictions in the bundle"
    ),
    DiscoveryType.path_diversification: (
        "Alternative causal paths that reduce single-path dominance"
    ),
    DiscoveryType.gap_marking: (
        "Adjacent concepts with no inbound edges that reveal coverage gaps"
    ),
    DiscoveryType.evidence_promotion_audit: (
        "INFERRED edges with high reinforcement but no evidence refs flagged for review"
    ),
}


# ---------------------------------------------------------------------------
# T5.3a  DiscoveryGenerator
# ---------------------------------------------------------------------------

class DiscoveryGenerator:
    """
    Maps a WeaknessReport to a deduplicated, severity-sorted list of
    DiscoveryQuestions — one question per unique weakness type.
    """

    def generate(self, weakness_report: WeaknessReport) -> List[DiscoveryQuestion]:
        seen_types: Dict[WeaknessType, float] = {}  # weakness_type -> max severity

        for weakness in weakness_report.all_weaknesses:
            wt = weakness.weakness_type
            if wt not in _WEAKNESS_TO_DISCOVERY:
                continue
            # Keep highest severity for dedup
            if wt not in seen_types or weakness.severity > seen_types[wt]:
                seen_types[wt] = weakness.severity

        # Sort weakness types by severity descending
        sorted_types = sorted(seen_types.items(), key=lambda kv: kv[1], reverse=True)

        questions: List[DiscoveryQuestion] = []
        for weakness_type, severity in sorted_types:
            disc_type = _WEAKNESS_TO_DISCOVERY[weakness_type]
            questions.append(DiscoveryQuestion(
                question_text=disc_type.value,
                discovery_type=disc_type,
                target_weakness=weakness_type.value,
                expected_outcome=_EXPECTED_OUTCOMES[disc_type],
                executable_locally=True,
            ))

        return questions


# ---------------------------------------------------------------------------
# T5.3b  SafeDiscovery
# ---------------------------------------------------------------------------

_48H = 172800.0   # seconds


class SafeDiscovery:
    """
    Executes a DiscoveryQuestion against a CausalDAG + FiberBundle.

    SAFETY CONTRACT
    ---------------
    - NEVER modifies the DAG (no add_fact, add_edge, reinforce_edge, etc.)
    - NEVER creates facts with confidence > 0.4; all outputs are candidates
    - All DAG access is read-only
    """

    def execute(
        self,
        question: DiscoveryQuestion,
        dag: CausalDAG,
        bundle: FiberBundle,
        query_time: float,
    ) -> DiscoveryResult:
        try:
            dtype = question.discovery_type
            if dtype == DiscoveryType.temporal_expansion:
                return self._temporal_expansion(question, dag, bundle, query_time)
            elif dtype == DiscoveryType.contradiction_resolution:
                return self._contradiction_resolution(question, dag, bundle, query_time)
            elif dtype == DiscoveryType.path_diversification:
                return self._path_diversification(question, dag, bundle, query_time)
            elif dtype == DiscoveryType.gap_marking:
                return self._gap_marking(question, dag, bundle, query_time)
            elif dtype == DiscoveryType.evidence_promotion_audit:
                return self._evidence_promotion_audit(question, dag, bundle, query_time)
            else:
                return self._empty_result(question)
        except Exception:
            return self._empty_result(question)

    # ------------------------------------------------------------------
    # private helpers
    # ------------------------------------------------------------------

    def _empty_result(self, question: DiscoveryQuestion) -> DiscoveryResult:
        return DiscoveryResult(
            question=question,
            facts_found=[],
            edges_found=[],
            candidate_hypotheses=[],
            repair_strength=0.0,
        )

    def _bundle_fact_ids(self, bundle: FiberBundle) -> set:
        return set(bundle.fibers.keys())

    # ------------------------------------------------------------------
    # strategies
    # ------------------------------------------------------------------

    def _temporal_expansion(
        self,
        question: DiscoveryQuestion,
        dag: CausalDAG,
        bundle: FiberBundle,
        query_time: float,
    ) -> DiscoveryResult:
        existing = self._bundle_fact_ids(bundle)

        future_ids = set(dag.interval_tree.query_valid_at(query_time + _48H))
        past_ids = set(dag.interval_tree.query_valid_at(query_time - _48H))
        new_ids = (future_ids | past_ids) - existing

        facts_found = list(new_ids)
        repair_strength = min(1.0, len(facts_found) / 5.0)

        return DiscoveryResult(
            question=question,
            facts_found=facts_found,
            edges_found=[],
            candidate_hypotheses=[],
            repair_strength=repair_strength,
        )

    def _contradiction_resolution(
        self,
        question: DiscoveryQuestion,
        dag: CausalDAG,
        bundle: FiberBundle,
        query_time: float,
    ) -> DiscoveryResult:
        bundle_ids = self._bundle_fact_ids(bundle)
        supersedes_edges: List[str] = []

        # Forward: outgoing SUPERSEDES from bundle facts
        for fact_id in bundle_ids:
            for edge in dag.edges.get(fact_id, []):
                if edge.edge_type == EdgeType.SUPERSEDES:
                    supersedes_edges.append(edge.id)

        # Reverse: scan all edges for SUPERSEDES pointing INTO bundle
        for src_id, edge_list in dag.edges.items():
            for edge in edge_list:
                if (
                    edge.edge_type == EdgeType.SUPERSEDES
                    and edge.target_id in bundle_ids
                    and edge.id not in supersedes_edges
                ):
                    supersedes_edges.append(edge.id)

        repair_strength = min(1.0, len(supersedes_edges) / 3.0)

        return DiscoveryResult(
            question=question,
            facts_found=[],
            edges_found=supersedes_edges,
            candidate_hypotheses=[],
            repair_strength=repair_strength,
        )

    def _path_diversification(
        self,
        question: DiscoveryQuestion,
        dag: CausalDAG,
        bundle: FiberBundle,
        query_time: float,
    ) -> DiscoveryResult:
        bundle_ids = self._bundle_fact_ids(bundle)

        # Top 3 anchors by max_confidence in bundle
        sorted_fibers = sorted(
            bundle.fibers.values(),
            key=lambda f: f.max_confidence,
            reverse=True,
        )
        top_anchors = [f.fact.id for f in sorted_fibers[:3]]

        new_fact_ids: List[str] = []
        seen: set = set(bundle_ids)

        for anchor_id in top_anchors:
            for edge in dag.edges.get(anchor_id, []):
                target = edge.target_id
                if target not in seen and len(new_fact_ids) < 10:
                    new_fact_ids.append(target)
                    seen.add(target)

        repair_strength = min(1.0, len(new_fact_ids) / 5.0)

        return DiscoveryResult(
            question=question,
            facts_found=new_fact_ids,
            edges_found=[],
            candidate_hypotheses=[],
            repair_strength=repair_strength,
        )

    def _gap_marking(
        self,
        question: DiscoveryQuestion,
        dag: CausalDAG,
        bundle: FiberBundle,
        query_time: float,
    ) -> DiscoveryResult:
        bundle_ids = self._bundle_fact_ids(bundle)

        # Collect all neighbors (1-hop out from any bundle fact)
        all_neighbors: set = set()
        for fact_id in bundle_ids:
            for edge in dag.edges.get(fact_id, []):
                if edge.target_id not in bundle_ids:
                    all_neighbors.add(edge.target_id)

        # Build set of fact IDs that have at least one inbound edge FROM the bundle
        has_inbound_from_bundle: set = set()
        for fact_id in bundle_ids:
            for edge in dag.edges.get(fact_id, []):
                has_inbound_from_bundle.add(edge.target_id)

        # Disconnected = neighbors with NO edges INTO the bundle (no edges whose target is in bundle)
        # Re-read spec: "neighbor fact IDs that have NO edges INTO the bundle"
        # i.e. edges from the neighbor pointing back into the bundle are absent
        disconnected: List[str] = []
        for neighbor_id in all_neighbors:
            has_edge_into_bundle = False
            for edge in dag.edges.get(neighbor_id, []):
                if edge.target_id in bundle_ids:
                    has_edge_into_bundle = True
                    break
            if not has_edge_into_bundle:
                disconnected.append(neighbor_id)
                if len(disconnected) >= 15:
                    break

        repair_strength = min(1.0, len(disconnected) / 8.0)

        return DiscoveryResult(
            question=question,
            facts_found=disconnected,
            edges_found=[],
            candidate_hypotheses=[],
            repair_strength=repair_strength,
        )

    def _evidence_promotion_audit(
        self,
        question: DiscoveryQuestion,
        dag: CausalDAG,
        bundle: FiberBundle,
        query_time: float,
    ) -> DiscoveryResult:
        bundle_ids = self._bundle_fact_ids(bundle)

        # Collect all INFERRED edges whose source or target is in the bundle
        inferred_no_evidence: List[str] = []

        for fact_id in bundle_ids:
            for edge in dag.edges.get(fact_id, []):
                if (
                    edge.provenance.origin == EdgeOrigin.INFERRED
                    and not edge.provenance.evidence_refs
                    and edge.id not in inferred_no_evidence
                ):
                    inferred_no_evidence.append(edge.id)

        # Also check edges from all sources that target bundle facts
        for src_id, edge_list in dag.edges.items():
            for edge in edge_list:
                if (
                    edge.target_id in bundle_ids
                    and edge.provenance.origin == EdgeOrigin.INFERRED
                    and not edge.provenance.evidence_refs
                    and edge.id not in inferred_no_evidence
                ):
                    inferred_no_evidence.append(edge.id)

        # Sort by reinforcement count descending (higher reinforcement = more suspicious)
        def _reinf_count(eid: str) -> int:
            edge = dag.get_edge(eid)
            if edge is None:
                return 0
            r = edge.provenance.reinforcement
            return r.count if r is not None else 0

        inferred_no_evidence.sort(key=_reinf_count, reverse=True)
        candidate_hypotheses = inferred_no_evidence[:10]

        repair_strength = min(1.0, len(candidate_hypotheses) / 5.0)

        return DiscoveryResult(
            question=question,
            facts_found=[],
            edges_found=[],
            candidate_hypotheses=candidate_hypotheses,
            repair_strength=repair_strength,
        )
