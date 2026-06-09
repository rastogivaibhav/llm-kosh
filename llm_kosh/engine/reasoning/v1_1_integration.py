"""ReasoningEngine v1.1 integration wrapper."""
from pathlib import Path
from typing import Optional

from llm_kosh.engine.reasoning import ReasoningEngine as BaseEngine
from llm_kosh.engine.reasoning.v1_1_loop import RecursiveLoopEngine


class ReasoningEngineV1_1(BaseEngine):
    """ReasoningEngine with v1.1 self-healing capabilities."""

    def __init__(self, root: Path, enable_recursive: bool = True, enable_v1_1: bool = True):
        super().__init__(root, enable_recursive=enable_recursive)
        self.enable_v1_1 = enable_v1_1

        if enable_v1_1:
            self.loop_engine = RecursiveLoopEngine(self, enable_learning=True)
        else:
            self.loop_engine = None

    def query_with_learning(
        self,
        query: str,
        temporal_context: Optional[str] = None,
        depth: int = 3,
        reasoning_mode: str = "BALANCED",
        max_iterations: int = 5,
    ):
        """Execute query with v1.1 recursive self-healing."""

        if not self.enable_v1_1 or not self.loop_engine:
            # Fallback to v1.0
            return self.query(
                query,
                temporal_context=temporal_context,
                depth=depth,
                reasoning_mode=reasoning_mode
            )

        # Use v1.1 with learning
        return self.loop_engine.query_with_learning(
            query,
            max_iterations=max_iterations,
            improvement_threshold=0.05
        )

    def get_learning_session(self):
        """Get the last learning session results."""
        if self.loop_engine:
            return self.loop_engine.iterations
        return []

    def get_learned_patterns(self):
        """Get all learned patterns."""
        if self.loop_engine and self.loop_engine.self_model:
            return dict(self.loop_engine.self_model.patterns)
        return {}
