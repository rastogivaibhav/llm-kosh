"""Discovery Generator - Creates improvement questions."""
from __future__ import annotations

from dataclasses import dataclass
from typing import List

from llm_kosh.engine.reasoning.v1_1_critic import TraceWeakness


@dataclass
class DiscoveryQuestion:
    """A question to help fix identified weaknesses."""

    question: str
    target_weakness: str
    execution_strategy: str
    expected_output: str


class DiscoveryGenerator:
    """Generate discovery questions to address trace weaknesses."""

    QUESTION_TEMPLATES = {
        "low_temporal_consistency": [
            DiscoveryQuestion(
                question="Which facts in the bundle have inconsistent timestamps?",
                target_weakness="temporal_mismatch",
                execution_strategy="local_analysis",
                expected_output="List of (fact_id, valid_from, valid_until) tuples"
            ),
        ],
        "high_contradiction": [
            DiscoveryQuestion(
                question="What are the sources of contradiction in the bundle?",
                target_weakness="conflicting_facts",
                execution_strategy="local_analysis",
                expected_output="List of (fact_id_a, fact_id_b, contradiction_type)"
            ),
        ],
        "low_path_diversity": [
            DiscoveryQuestion(
                question="What alternative paths exist between the same anchor pairs?",
                target_weakness="low_alternatives",
                execution_strategy="graph_search",
                expected_output="List of alternative causal paths"
            ),
        ],
        "no_evidence": [
            DiscoveryQuestion(
                question="What constructs should logically precede the target?",
                target_weakness="retrieval_failure",
                execution_strategy="local_analysis",
                expected_output="List of prerequisite construct IDs"
            ),
        ],
    }

    def generate_questions(self, weaknesses: List[TraceWeakness]) -> List[DiscoveryQuestion]:
        """Generate discovery questions for identified weaknesses."""
        questions = []

        for weakness in weaknesses:
            templates = self.QUESTION_TEMPLATES.get(weakness.category, [])
            for template in templates:
                # Adjust severity based on weakness severity
                if weakness.severity > 0.7:
                    questions.append(template)

        # Remove duplicates while preserving order
        seen = set()
        unique_questions = []
        for q in questions:
            if q.question not in seen:
                seen.add(q.question)
                unique_questions.append(q)

        return unique_questions

    def prioritize_questions(self, questions: List[DiscoveryQuestion]) -> List[DiscoveryQuestion]:
        """Sort questions by execution cost and expected impact."""
        # Local analysis is cheaper, do those first
        local = [q for q in questions if q.execution_strategy == "local_analysis"]
        graph = [q for q in questions if q.execution_strategy == "graph_search"]
        external = [q for q in questions if q.execution_strategy == "external_lookup"]

        return local + graph + external
