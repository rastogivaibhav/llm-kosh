"""Discovery generation layer — convert weaknesses into exploration questions.

This module provides the discovery layer for the recursive self-healing loop,
building on the discovery execution capabilities defined in discovery.py.

The discovery layer converts identified weaknesses into concrete questions that
probe the causal graph to find evidence that repairs reasoning gaps.

Exports:
- DiscoveryGenerator: Maps weaknesses to discovery questions
- DiscoveryQuestion: A question to explore in memory
- DiscoveryType: Enum of discovery strategies
- DiscoveryResult: Result of executing a discovery question
- SafeDiscovery: Executes discovery questions read-only against the DAG
"""
from __future__ import annotations

# Re-export the main components from discovery.py for convenience
from llm_kosh.engine.reasoning.discovery import (
    DiscoveryGenerator,
    DiscoveryQuestion,
    DiscoveryType,
    DiscoveryResult,
    SafeDiscovery,
)

__all__ = [
    "DiscoveryGenerator",
    "DiscoveryQuestion",
    "DiscoveryType",
    "DiscoveryResult",
    "SafeDiscovery",
]
