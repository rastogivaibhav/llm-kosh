"""Self-Model Learner - Learns from discoveries."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List
import json
from pathlib import Path


@dataclass
class LearnedPattern:
    """A pattern learned from successful discoveries."""

    pattern: str
    applies_to: str
    improvement: float
    frequency: int = 1
    success_rate: float = 1.0
    last_used_at: datetime = field(default_factory=datetime.now)


class SelfModel:
    """Learn and recommend patterns based on reasoning success."""

    def __init__(self, model_path: Optional[Path] = None):
        self.patterns: Dict[str, LearnedPattern] = {}
        self.model_path = model_path

        if model_path and model_path.exists():
            self.load_model(model_path)

    def register_pattern(self, pattern: LearnedPattern) -> None:
        """Register a learned pattern."""
        key = f"{pattern.applies_to}:{pattern.pattern}"

        if key in self.patterns:
            existing = self.patterns[key]
            existing.frequency += 1
            existing.improvement = (existing.improvement + pattern.improvement) / 2.0
        else:
            self.patterns[key] = pattern

    def query_patterns(self, reasoning_type: str) -> List[LearnedPattern]:
        """Get patterns applicable to a reasoning type."""
        return [
            p for p in self.patterns.values()
            if p.applies_to == reasoning_type or p.applies_to == "all_reasoning"
        ]

    def recommend_strategy(self, reasoning_type: str) -> str:
        """Recommend a strategy based on learned patterns."""
        patterns = self.query_patterns(reasoning_type)

        if not patterns:
            return "default"

        # Return most successful pattern
        best = max(patterns, key=lambda p: p.success_rate * p.improvement)
        return best.pattern

    def save_model(self, path: Path) -> None:
        """Save model to disk."""
        data = {
            pattern_key: {
                "pattern": p.pattern,
                "applies_to": p.applies_to,
                "improvement": p.improvement,
                "frequency": p.frequency,
                "success_rate": p.success_rate,
            }
            for pattern_key, p in self.patterns.items()
        }

        path.write_text(json.dumps(data, indent=2))

    def load_model(self, path: Path) -> None:
        """Load model from disk."""
        if not path.exists():
            return

        data = json.loads(path.read_text())
        for pattern_key, pattern_data in data.items():
            pattern = LearnedPattern(**pattern_data)
            self.patterns[pattern_key] = pattern

    def __len__(self) -> int:
        return len(self.patterns)
