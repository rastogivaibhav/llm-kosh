"""Trace criticism layer — analyze reasoning traces for weaknesses.

This module provides the critique layer for the recursive self-healing loop,
building on the trace analysis capabilities defined in critique.py.

Exports:
- TraceCritic: Analyzes individual QueryTrace objects for weaknesses
- TraceWeakness: Represents a single identified weakness
- WeaknessType: Enum of weakness categories
- WeaknessReport: Aggregated report of per-trace and session weaknesses
"""
from __future__ import annotations

# Re-export the main components from critique.py for convenience
from llm_kosh.engine.reasoning.critique import (
    TraceCritic,
    TraceWeakness,
    WeaknessType,
    WeaknessReport,
    CrossQueryCritic,
)

__all__ = [
    "TraceCritic",
    "TraceWeakness",
    "WeaknessType",
    "WeaknessReport",
    "CrossQueryCritic",
]
