from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from llm_kosh.engine.reasoning.causal_dag import ReasoningMode
from llm_kosh.engine.reasoning.convergent import ConvergedAnswer, ConvergentEngine
from llm_kosh.engine.reasoning.opposition import OppositionEngine, OppositionResult


@dataclass
class DialecticResult:
    query: str
    initial_result: Any
    converged: ConvergedAnswer
    opposition: OppositionResult
    reopened_result: Optional[Any]
    final_status: str
    iterations: int
    synthesis: Dict[str, Any] = field(default_factory=dict)


class DialecticController:
    """
    Run the cognitive rhythm:

    non-convergent -> convergent -> opposition -> re-open -> synthesis.

    This is intentionally a controller around ReasoningEngine rather than a
    replacement for it. It converts TheHypoKosh into a bi-modal/dialectical
    reasoning system.
    """

    def __init__(self, engine: Any) -> None:
        self.engine = engine
        self.convergent = ConvergentEngine()
        self.opposition = OppositionEngine()

    def run(
        self,
        query: str,
        temporal_context: Optional[str] = None,
        depth: int = 3,
        reopen_on_challenge: bool = True,
    ) -> DialecticResult:
        initial = self.engine.query(
            query,
            temporal_context=temporal_context,
            depth=depth,
            reasoning_mode=ReasoningMode.BALANCED.value,
        )
        converged = self.convergent.converge(initial.bundle)
        opposed = self.opposition.oppose(converged, initial.bundle, dag=self.engine.dag)

        reopened = None
        iterations = 1
        if reopen_on_challenge and opposed.challenged and opposed.reopened_fact_ids:
            # Re-open the same question in theoretical mode. This does not make
            # speculative paths final; it deliberately widens the search after
            # convergence is challenged.
            reopened = self.engine.query(
                query,
                temporal_context=temporal_context,
                depth=max(depth, 4),
                reasoning_mode=ReasoningMode.THEORETICAL.value,
            )
            iterations += 1

        final_status = self._final_status(initial, converged, opposed, reopened)
        synthesis = {
            "primary_fact_id": converged.primary_fact_id,
            "primary_content": converged.primary_content,
            "convergence_score": converged.score,
            "evidence_loss": converged.evidence_loss,
            "opposition_status": opposed.status,
            "opposition_score": opposed.opposition_score,
            "reopened_fact_ids": opposed.reopened_fact_ids,
            "abstain": getattr(initial.stability, "abstain", False),
            "missing_evidence_questions": opposed.falsification_questions,
        }
        return DialecticResult(
            query=query,
            initial_result=initial,
            converged=converged,
            opposition=opposed,
            reopened_result=reopened,
            final_status=final_status,
            iterations=iterations,
            synthesis=synthesis,
        )

    def _final_status(self, initial, converged, opposed, reopened) -> str:
        if getattr(initial.stability, "abstain", False):
            return "no_evidence"
        if not converged.has_answer:
            return "needs_evidence"
        if opposed.status == "survived_initial_opposition":
            return "survived_opposition"
        if opposed.status == "needs_evidence":
            return "needs_evidence"
        if reopened is not None and not getattr(reopened.stability, "abstain", False):
            return "reopened_for_non_convergent_review"
        return "challenged"
