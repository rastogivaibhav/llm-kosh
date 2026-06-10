from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Tuple

from llm_kosh.engine.reasoning.causal_dag import EdgeOrigin, EdgeRole
from llm_kosh.engine.reasoning.convergent import ConvergedAnswer
from llm_kosh.engine.reasoning.fiber_bundle import FiberBundle


@dataclass
class OppositionFinding:
    kind: str
    severity: float
    message: str
    fact_ids: List[str] = field(default_factory=list)
    edge_ids: List[str] = field(default_factory=list)


@dataclass
class OppositionResult:
    findings: List[OppositionFinding]
    reopened_fact_ids: List[str]
    contradiction_pairs: List[Tuple[str, str]]
    falsification_questions: List[str]
    opposition_score: float
    status: str

    @property
    def challenged(self) -> bool:
        return bool(self.findings)


class OppositionEngine:
    """
    Cognitive substrate for opposition reasoning.

    It deliberately attacks the converged answer: what did convergence hide,
    compress, assume, discard, or over-promote?
    """

    def oppose(self, converged: ConvergedAnswer, original_bundle: FiberBundle, dag=None) -> OppositionResult:
        findings: List[OppositionFinding] = []
        reopened: List[str] = []
        contradiction_pairs: List[Tuple[str, str]] = []
        falsification_questions: List[str] = []

        if not converged.has_answer:
            findings.append(OppositionFinding(
                kind="no_converged_answer",
                severity=1.0,
                message="convergence produced no answer; evidence must be sought",
            ))
            return OppositionResult(findings, [], [], ["What source could establish first evidence?"], 1.0, "needs_evidence")

        if converged.discarded_fact_ids:
            reopened.extend(converged.discarded_fact_ids)
            findings.append(OppositionFinding(
                kind="discarded_alternatives",
                severity=min(1.0, 0.15 * len(converged.discarded_fact_ids)),
                message="convergence discarded alternative facts that should be reopened",
                fact_ids=list(converged.discarded_fact_ids),
            ))

        if converged.evidence_loss > 0.5:
            findings.append(OppositionFinding(
                kind="high_evidence_loss",
                severity=converged.evidence_loss,
                message="convergence compressed away more than half of available path evidence",
                fact_ids=[converged.primary_fact_id] if converged.primary_fact_id else [],
            ))

        selected_edge_ids = set(converged.selected_path.edge_ids if converged.selected_path else [])
        for fiber in original_bundle.fibers.values():
            for path in fiber.paths:
                for edge in path.edges:
                    if edge.id not in selected_edge_ids:
                        continue
                    if edge.provenance.origin in {EdgeOrigin.INFERRED, EdgeOrigin.HYPOTHETICAL}:
                        findings.append(OppositionFinding(
                            kind="unproven_selected_edge",
                            severity=0.7 if edge.provenance.origin == EdgeOrigin.INFERRED else 0.9,
                            message=f"selected edge is {edge.provenance.origin.value}; do not treat as discovered truth",
                            fact_ids=[edge.source_id, edge.target_id],
                            edge_ids=[edge.id],
                        ))
                        falsification_questions.append(
                            f"What independent evidence would promote {edge.source_id} -> {edge.target_id}?"
                        )
                    if edge.provenance.role in {EdgeRole.COMPRESSED, EdgeRole.ANALOGICAL, EdgeRole.PREDICTIVE}:
                        falsification_questions.append(
                            f"What mechanism is hidden by the {edge.provenance.role.value} edge {edge.id}?"
                        )

        # Surface contradictions among primary and discarded facts.
        if dag is not None and converged.primary_fact_id:
            for fid in original_bundle.fibers:
                if fid == converged.primary_fact_id:
                    continue
                if dag.has_contradiction(converged.primary_fact_id, fid):
                    contradiction_pairs.append((converged.primary_fact_id, fid))
                    reopened.append(fid)
            if contradiction_pairs:
                findings.append(OppositionFinding(
                    kind="contradiction_survived_convergence",
                    severity=min(1.0, 0.4 + 0.2 * len(contradiction_pairs)),
                    message="converged answer has active contradictory alternatives",
                    fact_ids=sorted({x for pair in contradiction_pairs for x in pair}),
                ))

        if converged.compression_candidates:
            for candidate in converged.compression_candidates:
                findings.append(OppositionFinding(
                    kind="compression_requires_provenance",
                    severity=0.45,
                    message="mechanistic path can be compressed only as inferred/compressed until evidence promotes it",
                    fact_ids=[candidate.source_id, candidate.target_id],
                    edge_ids=list(candidate.derived_from_edges),
                ))
                falsification_questions.append(
                    f"Does direct evidence exist for compressed shortcut {candidate.source_id} -> {candidate.target_id}?"
                )

        # Deduplicate reopened facts and questions.
        reopened = list(dict.fromkeys(reopened))
        falsification_questions = list(dict.fromkeys(falsification_questions))
        opposition_score = min(1.0, sum(f.severity for f in findings) / max(1, len(findings)))
        if not findings:
            status = "survived_initial_opposition"
        elif any(f.kind in {"no_converged_answer", "unproven_selected_edge"} and f.severity >= 0.9 for f in findings):
            status = "needs_evidence"
        else:
            status = "challenged"

        return OppositionResult(
            findings=findings,
            reopened_fact_ids=reopened,
            contradiction_pairs=contradiction_pairs,
            falsification_questions=falsification_questions,
            opposition_score=round(opposition_score, 4),
            status=status,
        )
