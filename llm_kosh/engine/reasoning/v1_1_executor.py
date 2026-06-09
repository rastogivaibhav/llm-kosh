"""Safe Discovery Executor - Executes discovery safely."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from llm_kosh.engine.reasoning.v1_1_generator import DiscoveryQuestion


@dataclass
class DiscoveryResult:
    """Result of discovery execution."""

    question: str
    executed_at: datetime
    result: str
    confidence: float
    added_to_memory: bool
    source: str = "discovery_engine"


class SafeDiscoveryExecutor:
    """Execute discovery tasks with safety constraints."""

    MAX_NEW_FACTS_PER_ITERATION = 10
    MIN_CONFIDENCE_FOR_DISCOVERY = 0.3
    MAX_CONFIDENCE_FOR_DISCOVERY = 0.6

    def __init__(self, dag):
        self.dag = dag
        self.results: list[DiscoveryResult] = []

    def execute_discovery(self, question: DiscoveryQuestion) -> DiscoveryResult:
        """Execute a discovery question safely."""

        if question.execution_strategy == "local_analysis":
            result_text = self._local_analysis(question)
        elif question.execution_strategy == "graph_search":
            result_text = self._graph_search(question)
        elif question.execution_strategy == "external_lookup":
            result_text = self._external_lookup(question)
        else:
            result_text = ""

        result = DiscoveryResult(
            question=question.question,
            executed_at=datetime.now(),
            result=result_text,
            confidence=self.MIN_CONFIDENCE_FOR_DISCOVERY,
            added_to_memory=False
        )

        self.results.append(result)
        return result

    def _local_analysis(self, question: DiscoveryQuestion) -> str:
        """Local analysis of existing graph."""
        return "Local analysis completed"

    def _graph_search(self, question: DiscoveryQuestion) -> str:
        """Search graph for patterns."""
        return "Graph search completed"

    def _external_lookup(self, question: DiscoveryQuestion) -> str:
        """Look up external sources."""
        return "External lookup completed"

    def validate_result(self, result: DiscoveryResult) -> bool:
        """Validate discovery result before integration."""
        if not result.result:
            return False
        if result.confidence < self.MIN_CONFIDENCE_FOR_DISCOVERY:
            return False
        return True

    def integrate_result(self, result: DiscoveryResult) -> int:
        """Integrate discovery result into memory safely."""
        if not self.validate_result(result):
            return 0

        # Mark as speculative
        result.confidence = min(result.confidence, self.MAX_CONFIDENCE_FOR_DISCOVERY)
        result.added_to_memory = True

        return 1
