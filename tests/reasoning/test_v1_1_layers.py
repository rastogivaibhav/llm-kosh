"""Unit tests for v1.1 layers."""
import pytest
from datetime import datetime, timezone

from llm_kosh.engine.reasoning.v1_1_tracer import QueryTrace, QueryTracer
from llm_kosh.engine.reasoning.v1_1_critic import TraceCritic, TraceWeakness
from llm_kosh.engine.reasoning.v1_1_generator import DiscoveryGenerator
from llm_kosh.engine.reasoning.v1_1_executor import SafeDiscoveryExecutor
from llm_kosh.engine.reasoning.v1_1_self_model import SelfModel, LearnedPattern
from llm_kosh.engine.reasoning.v1_1_loop import RecursiveLoopEngine


class TestQueryTracer:
    def test_trace_creation(self):
        tracer = QueryTracer()
        trace_id = tracer.start_trace("test query", 1000.0)
        assert trace_id is not None
        assert trace_id.startswith("trace.")

    def test_trace_lifecycle(self):
        tracer = QueryTracer()
        trace_id = tracer.start_trace("test", 100.0)
        trace = tracer.finalize_trace(trace_id, 50.0)
        assert trace is not None
        assert trace.execution_time_ms == 50.0

    def test_max_traces(self):
        tracer = QueryTracer(max_traces=5)
        for i in range(10):
            tracer.start_trace(f"query_{i}", float(i))
        assert len(tracer) == 5


class TestTraceCritic:
    def test_weakness_detection(self):
        critic = TraceCritic()
        tracer = QueryTracer()
        trace_id = tracer.start_trace("test", 100.0)
        trace = tracer.finalize_trace(trace_id, 50.0)

        # Create a trace with no stability (should report no_evidence)
        weaknesses = critic.analyze_trace(trace)
        assert len(weaknesses) > 0
        assert any("no_evidence" in w.category for w in weaknesses)


class TestDiscoveryGenerator:
    def test_question_generation(self):
        gen = DiscoveryGenerator()
        weakness = TraceWeakness(
            category="low_temporal_consistency",
            severity=0.8,
            evidence=["consistency: 0.3"],
            recommended_action="test"
        )
        questions = gen.generate_questions([weakness])
        assert len(questions) > 0


class TestSelfModel:
    def test_pattern_registration(self):
        model = SelfModel()
        pattern = LearnedPattern(
            pattern="test_pattern",
            applies_to="all_reasoning",
            improvement=0.1
        )
        model.register_pattern(pattern)
        assert len(model) == 1

    def test_pattern_recommendation(self):
        model = SelfModel()
        pattern = LearnedPattern(
            pattern="good_pattern",
            applies_to="CATE_estimation",
            improvement=0.2,
            success_rate=0.9
        )
        model.register_pattern(pattern)
        rec = model.recommend_strategy("CATE_estimation")
        assert rec == "good_pattern"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
