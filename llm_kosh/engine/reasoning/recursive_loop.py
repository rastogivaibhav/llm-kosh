"""
RecursiveReasoningLoop — T7.1–T7.5

Wires TraceCritic, CrossQueryCritic, HealingExecutor, DiscoveryGenerator,
SafeDiscovery, SelfModel, and SelfModelController into a self-healing loop
around ReasoningEngine.query_with_trace().
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Callable, List, Optional, Tuple

from llm_kosh.engine.reasoning.trace import QueryTrace
from llm_kosh.engine.reasoning.critique import (
    TraceCritic,
    CrossQueryCritic,
    TraceWeakness,
    WeaknessReport,
)
from llm_kosh.engine.reasoning.healer import HealingExecutor, QueryParams
from llm_kosh.engine.reasoning.discovery import (
    DiscoveryGenerator,
    SafeDiscovery,
    DiscoveryResult,
)
from llm_kosh.engine.reasoning.self_model import SelfModel, SelfModelController

if TYPE_CHECKING:
    from llm_kosh.engine.reasoning import ReasoningEngine, QueryResult


# ---------------------------------------------------------------------------
# LoopState
# ---------------------------------------------------------------------------

@dataclass
class LoopState:
    """Accumulates all per-iteration data produced by RecursiveReasoningLoop.run()."""

    query: str
    iteration_count: int = 0
    traces: List[QueryTrace] = field(default_factory=list)
    all_weaknesses: List[List[TraceWeakness]] = field(default_factory=list)
    discovery_results: List[DiscoveryResult] = field(default_factory=list)
    stability_progression: List[float] = field(default_factory=list)
    discovery_gain_progression: List[float] = field(default_factory=list)
    termination_reason: Optional[str] = None
    # str enum: "stability_threshold_reached" | "max_iterations_reached" |
    #           "no_discovery_gain" | "oscillation_detected" | "recursive_disabled"


# ---------------------------------------------------------------------------
# RecursiveReasoningLoop
# ---------------------------------------------------------------------------

class RecursiveReasoningLoop:
    """
    The capstone 7-step self-healing loop.

    Per iteration:
    1. Adapt  — SelfModelController counteracts known biases
    2. Query  — engine.query_with_trace() with adapted params
    3. Observe — SelfModel records the trace
    4. Critique — TraceCritic + CrossQueryCritic → WeaknessReport
    5. Heal   — HealingExecutor → next QueryParams
    6. Discover — DiscoveryGenerator + SafeDiscovery
    7. Update  — LoopState update + stopping-condition checks
    """

    def __init__(
        self,
        trace_critic: TraceCritic,
        cross_query_critic: CrossQueryCritic,
        healing_executor: HealingExecutor,
        discovery_generator: DiscoveryGenerator,
        safe_discovery: SafeDiscovery,
        self_model: SelfModel,
        self_model_controller: SelfModelController,
    ) -> None:
        self._trace_critic = trace_critic
        self._cross_query_critic = cross_query_critic
        self._healing_executor = healing_executor
        self._discovery_generator = discovery_generator
        self._safe_discovery = safe_discovery
        self._self_model = self_model
        self._self_model_controller = self_model_controller

    def run(
        self,
        engine: "ReasoningEngine",
        query: str,
        temporal_context: Optional[str] = None,
        max_iterations: int = 5,
        stability_threshold: float = 0.8,
        depth: int = 3,
        query_fn: Optional[Callable] = None,
    ) -> Tuple["QueryResult", LoopState]:
        """
        Run the recursive self-healing loop.

        Returns (result, state) from the last completed iteration.

        query_fn: optional callable(query, temporal_context, depth=...) -> (result, trace).
                  When None, uses engine.query_with_trace().
        """
        if max_iterations < 1:
            raise ValueError("max_iterations must be >= 1")

        state = LoopState(query=query)
        current_params = QueryParams(depth=depth)

        # Holds the most recent (result, trace) pair so we can return them on exit.
        last_result = None
        last_trace = None

        for iteration in range(max_iterations):
            # ---- Safety catch (condition 4) — checked at top of loop ----
            if state.iteration_count >= max_iterations:
                state.termination_reason = "max_iterations_reached"
                break

            # ----------------------------------------------------------------
            # Step 1: Adapt
            # ----------------------------------------------------------------
            adapted_params = self._self_model_controller.adapt_params(
                current_params, self._self_model
            )

            # ----------------------------------------------------------------
            # Step 2: Query
            # ----------------------------------------------------------------
            if query_fn is not None:
                result, trace = query_fn(query, temporal_context, depth=adapted_params.depth)
            else:
                result, trace = engine.query_with_trace(
                    query,
                    temporal_context=temporal_context,
                    depth=adapted_params.depth,
                    reasoning_mode="BALANCED",
                )
            trace.iteration = iteration
            last_result = result
            last_trace = trace

            # ----------------------------------------------------------------
            # Step 3: Observe
            # ----------------------------------------------------------------
            self._self_model.observe(trace)

            # ----------------------------------------------------------------
            # Step 4: Critique
            # ----------------------------------------------------------------
            per_trace_weaknesses = self._trace_critic.analyze(trace)
            session_weaknesses = self._cross_query_critic.analyze_session(state.traces)

            all_w = per_trace_weaknesses + session_weaknesses
            severity = (
                sum(w.severity for w in all_w) / len(all_w) if all_w else 0.0
            )
            weakness_report = WeaknessReport(
                trace_id=trace.trace_id,
                per_trace_weaknesses=per_trace_weaknesses,
                session_weaknesses=session_weaknesses,
            )
            # WeaknessReport.__post_init__ recomputes total_severity for us.

            # ----------------------------------------------------------------
            # Step 5: Heal
            # ----------------------------------------------------------------
            next_params = self._healing_executor.heal(
                weakness_report, base_params=current_params
            )

            # ----------------------------------------------------------------
            # Step 6: Discover
            # ----------------------------------------------------------------
            questions = self._discovery_generator.generate(weakness_report)
            iteration_discovery_results: List[DiscoveryResult] = []
            query_time = trace.query_time if trace.query_time is not None else 0.0

            # Support both QueryResult (has .bundle) and DialecticResult (has .initial_result.bundle)
            result_bundle = result.bundle if hasattr(result, "bundle") else result.initial_result.bundle

            for question in questions:
                discovery_result = self._safe_discovery.execute(
                    question, engine.dag, result_bundle, query_time
                )
                iteration_discovery_results.append(discovery_result)

            # ----------------------------------------------------------------
            # Step 7: Update LoopState
            # ----------------------------------------------------------------
            state.traces.append(trace)
            state.all_weaknesses.append(per_trace_weaknesses + session_weaknesses)
            state.discovery_results.extend(iteration_discovery_results)
            state.stability_progression.append(trace.stability_score)

            # Discovery gain for this iteration = mean repair_strength (or 0)
            if iteration_discovery_results:
                gain = sum(dr.repair_strength for dr in iteration_discovery_results) / len(
                    iteration_discovery_results
                )
            else:
                gain = 0.0
            state.discovery_gain_progression.append(gain)

            state.iteration_count += 1

            # Advance params for next iteration
            current_params = next_params

            # ----------------------------------------------------------------
            # Stopping condition 1: stability_threshold_reached
            # ----------------------------------------------------------------
            if trace.stability_score >= stability_threshold:
                state.termination_reason = "stability_threshold_reached"
                break

            # ----------------------------------------------------------------
            # Stopping condition 2: oscillation_detected
            # ----------------------------------------------------------------
            if len(state.stability_progression) >= 3:
                s = state.stability_progression
                s_prev2, s_prev1, s_curr = s[-3], s[-2], s[-1]
                if s_prev1 > s_prev2 and s_curr < s_prev1 - 0.03:
                    state.termination_reason = "oscillation_detected"
                    break

            # ----------------------------------------------------------------
            # Stopping condition 3: no_discovery_gain
            # ----------------------------------------------------------------
            if iteration > 0 and all(
                dr.repair_strength < 0.05 for dr in iteration_discovery_results
            ):
                state.termination_reason = "no_discovery_gain"
                break

        else:
            # for-loop completed without break → max_iterations_reached
            state.termination_reason = "max_iterations_reached"

        return last_result, state
