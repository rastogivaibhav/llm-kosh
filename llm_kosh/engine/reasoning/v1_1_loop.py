"""Recursive Loop Orchestrator - Main loop logic."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional
import time

from llm_kosh.engine.reasoning.v1_1_tracer import QueryTracer, QueryTrace
from llm_kosh.engine.reasoning.v1_1_critic import TraceCritic
from llm_kosh.engine.reasoning.v1_1_generator import DiscoveryGenerator
from llm_kosh.engine.reasoning.v1_1_executor import SafeDiscoveryExecutor
from llm_kosh.engine.reasoning.v1_1_self_model import SelfModel


@dataclass
class LoopIteration:
    """Single iteration of the recursive loop."""

    iteration: int
    query: str
    trace: QueryTrace
    weaknesses: list
    discoveries: list
    self_model_updated: bool
    stability_improved: bool
    confidence_improved: bool


class RecursiveLoopEngine:
    """Orchestrate the recursive self-healing loop."""

    def __init__(self, reasoning_engine, enable_learning=True):
        self.engine = reasoning_engine
        self.enable_learning = enable_learning

        self.tracer = QueryTracer()
        self.critic = TraceCritic()
        self.generator = DiscoveryGenerator()
        self.executor = SafeDiscoveryExecutor(reasoning_engine.dag)
        self.self_model = SelfModel()

        self.iterations: list[LoopIteration] = []

    def query_with_learning(
        self,
        query: str,
        max_iterations: int = 5,
        improvement_threshold: float = 0.05
    ):
        """Execute query with iterative self-improvement."""

        # Initial query
        t0 = time.time()
        trace_id = self.tracer.start_trace(query, 0.0)

        result = self.engine.query(query, depth=3)

        elapsed_ms = (time.time() - t0) * 1000
        trace = self.tracer.finalize_trace(trace_id, elapsed_ms)

        previous_confidence = result.confidence_product if hasattr(result, 'confidence_product') else 0.0

        for iteration_num in range(1, max_iterations + 1):
            # Critique
            weaknesses = self.critic.analyze_trace(trace)

            if not weaknesses:
                break  # No issues found

            # Discover
            questions = self.generator.generate_questions(weaknesses)
            questions = self.generator.prioritize_questions(questions)

            discoveries = []
            for question in questions[:3]:  # Limit discoveries per iteration
                result_obj = self.executor.execute_discovery(question)
                self.executor.integrate_result(result_obj)
                discoveries.append(result_obj)

            # Learn
            if self.enable_learning:
                for discovery in discoveries:
                    pattern = LearnedPattern(
                        pattern=discovery.question,
                        applies_to="all_reasoning",
                        improvement=discovery.confidence * 0.1
                    )
                    self.self_model.register_pattern(pattern)

            # Re-query
            trace_id = self.tracer.start_trace(query, 0.0)
            new_result = self.engine.query(query, depth=3)
            elapsed_ms = (time.time() - t0) * 1000
            new_trace = self.tracer.finalize_trace(trace_id, elapsed_ms)

            new_confidence = new_result.confidence_product if hasattr(new_result, 'confidence_product') else 0.0
            confidence_improved = new_confidence > previous_confidence

            iteration = LoopIteration(
                iteration=iteration_num,
                query=query,
                trace=new_trace,
                weaknesses=weaknesses,
                discoveries=discoveries,
                self_model_updated=self.enable_learning,
                stability_improved=new_trace.stability.status != trace.stability.status if new_trace.stability and trace.stability else False,
                confidence_improved=confidence_improved
            )

            self.iterations.append(iteration)

            # Check convergence
            if not confidence_improved:
                break

            previous_confidence = new_confidence
            trace = new_trace

        return new_result if iteration_num > 0 else result
