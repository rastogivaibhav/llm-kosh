from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from llm_kosh.engine.reasoning.causal_dag import (
    CausalDAG, EdgeOrigin, EdgeProvenance, EdgeRole, EdgeType, EvidenceRef, ReasoningMode, TrajectoryState
)
from llm_kosh.engine.reasoning.causal_retrieval import CausalRetrieval
from llm_kosh.engine.reasoning.escape import EscapeMechanism
from llm_kosh.engine.reasoning.fiber_bundle import FiberBundle, build_fiber_bundle
from llm_kosh.engine.reasoning.lyapunov_critic import LyapunovCritic, StabilityResult
from llm_kosh.engine.reasoning.convergent import ConvergedAnswer, ConvergentEngine
from llm_kosh.engine.reasoning.opposition import OppositionEngine, OppositionResult
from llm_kosh.engine.reasoning.dialectic import DialecticController, DialecticResult
from llm_kosh.engine.reasoning.model_world import ModelWorld, ModelWorldNode, ModelWorldNodeKind
from llm_kosh.engine.reasoning.trace import TraceStore, QueryTrace


@dataclass
class QueryResult:
    anchors: List[str]
    bundle: FiberBundle
    stability: StabilityResult
    escape_triggered: bool
    escape_surfaced: List[str]
    reasoning_mode: str = ReasoningMode.BALANCED.value


class ReasoningEngine:
    """
    Public API for the Temporal Causal Reasoning Engine.
    Initialize once per cartridge root; call query/ingest/critique/explore.
    """

    def __init__(self, root: Path, enable_recursive: bool = True) -> None:
        self.root = root
        self._enable_recursive = enable_recursive
        self.dag = CausalDAG(root)
        self._retrieval = CausalRetrieval(self.dag)
        self._critic = LyapunovCritic(self.dag)
        self._escape = EscapeMechanism(self.dag)
        self._dialectic = DialecticController(self)
        self._trace_store = TraceStore(root)
        from llm_kosh.engine.reasoning.self_model import SelfModel
        self._self_model = SelfModel(root)

    # ------------------------------------------------------------------ public API

    def ingest(
        self,
        content: str,
        documented_at: datetime,
        valid_from: datetime,
        valid_until: Optional[datetime],
        confidence: float,
        causal_edges: List[dict],
    ) -> str:
        """
        Add a fact to the causal graph.
        causal_edges: list of {"target_id": str, "edge_type": str, "confidence": float}
        Returns the new fact_id.
        """
        now = datetime.now(timezone.utc)
        fact_id = self.dag.add_fact(
            content=content,
            ingested_at=now,
            documented_at=documented_at,
            valid_from=valid_from,
            valid_until=valid_until,
            confidence=confidence,
            source="agent",
        )
        for edge_spec in causal_edges:
            try:
                self.dag.add_edge(
                    source_id=fact_id,
                    target_id=edge_spec["target_id"],
                    edge_type=EdgeType(edge_spec.get("edge_type", "ENABLES")),
                    confidence=float(edge_spec.get("confidence", 0.7)),
                    valid_from=valid_from,
                    valid_until=valid_until,
                    established_by="agent",
                )
            except (KeyError, ValueError):
                pass
        # Refresh retrieval index
        self._retrieval = CausalRetrieval(self.dag)
        return fact_id

    def query(
        self,
        query: str,
        temporal_context: Optional[str] = None,
        depth: int = 3,
        reasoning_mode: str = ReasoningMode.BALANCED.value,
    ) -> QueryResult:
        """
        Full pipeline: retrieve -> bundle -> critique -> escape if needed -> return.
        temporal_context: ISO 8601 datetime string, Unix timestamp str, or None (uses now).
        """
        query_time = self._parse_temporal_context(temporal_context)
        trajectory = TrajectoryState(session_id=f"q-{int(query_time)}")

        candidates = self._retrieval.retrieve(query, query_time, depth=depth)
        anchor_ids = self._select_anchors(candidates)

        bundle = build_fiber_bundle(
            self.dag, candidates, anchor_ids=anchor_ids,
            query_time=query_time, max_hops=depth,
        )
        mode = ReasoningMode(reasoning_mode)
        bundle = self._apply_reasoning_mode(bundle, mode)
        diagnosis = self._critic.evaluate(bundle)

        escaped = False
        escape_surfaced: List[str] = []

        if diagnosis.status in ("unstable", "marginal"):
            query_profile = {}  # resonance profile not needed by escape strategies directly
            prev_ids = set(bundle.fibers.keys())
            bundle = self._escape.escape(bundle, diagnosis, trajectory, query_time, query_profile, depth)
            escape_surfaced = [fid for fid in bundle.fibers if fid not in prev_ids and fid != "__deep_instability__"]
            bundle = self._apply_reasoning_mode(bundle, mode)
            diagnosis = self._critic.evaluate(bundle)
            escaped = True

        return QueryResult(
            anchors=anchor_ids,
            bundle=bundle,
            stability=diagnosis,
            escape_triggered=escaped,
            escape_surfaced=escape_surfaced,
            reasoning_mode=mode.value,
        )

    def query_with_trace(
        self,
        query: str,
        temporal_context: Optional[str] = None,
        depth: int = 3,
        reasoning_mode: str = ReasoningMode.BALANCED.value,
    ) -> Tuple[QueryResult, QueryTrace]:
        """
        Like query(), but also builds and auto-saves a QueryTrace.
        Candidates are retrieved before query() so they can be recorded.
        """
        query_time = self._parse_temporal_context(temporal_context)
        # Capture candidates before calling query() (cheap, idempotent)
        raw_candidates = self._retrieval.retrieve(query, query_time, depth=depth)
        candidates = [(fact.id, dist, score) for fact, dist, score in raw_candidates]

        executed_at = time.time()
        t0 = time.time()
        result = self.query(query, temporal_context=temporal_context, depth=depth, reasoning_mode=reasoning_mode)
        execution_time_secs = time.time() - t0

        bundle = result.bundle
        bundle_summary = {
            "fiber_count": len(bundle.fibers),
            "total_paths": sum(len(f.paths) for f in bundle.fibers.values()),
            "max_degeneracy": max((f.degeneracy for f in bundle.fibers.values()), default=0),
            "fact_ids": list(bundle.fibers.keys()),
        }

        trace = QueryTrace(
            query=query,
            temporal_context=temporal_context,
            query_time=query_time,
            executed_at=executed_at,
            execution_time_secs=execution_time_secs,
            reasoning_mode=result.reasoning_mode,
            candidates=candidates,
            anchor_ids=result.anchors,
            bundle_summary=bundle_summary,
            lyapunov_dimensions=result.stability.dimensions,
            stability_score=result.stability.score,
            stability_status=result.stability.status,
            escape_triggered=result.escape_triggered,
            escape_surfaced=result.escape_surfaced,
        )
        self._trace_store.save(trace)
        return result, trace

    def dialectic_query_with_trace(
        self,
        query: str,
        temporal_context: Optional[str] = None,
        depth: int = 3,
        reopen_on_challenge: bool = True,
    ) -> Tuple["DialecticResult", QueryTrace]:
        """
        Like dialectic_query(), but also builds and auto-saves a QueryTrace.
        """
        query_time = self._parse_temporal_context(temporal_context)
        raw_candidates = self._retrieval.retrieve(query, query_time, depth=depth)
        candidates = [(fact.id, dist, score) for fact, dist, score in raw_candidates]

        executed_at = time.time()
        t0 = time.time()
        dialectic_result = self.dialectic_query(
            query, temporal_context=temporal_context, depth=depth, reopen_on_challenge=reopen_on_challenge
        )
        execution_time_secs = time.time() - t0

        initial = dialectic_result.initial_result
        bundle = initial.bundle
        bundle_summary = {
            "fiber_count": len(bundle.fibers),
            "total_paths": sum(len(f.paths) for f in bundle.fibers.values()),
            "max_degeneracy": max((f.degeneracy for f in bundle.fibers.values()), default=0),
            "fact_ids": list(bundle.fibers.keys()),
        }

        opposition = dialectic_result.opposition
        opposition_challenges = (
            len(opposition.challenges) if hasattr(opposition, "challenges")
            else len(opposition.findings) if hasattr(opposition, "findings")
            else 0
        )
        dialectic_result_summary = {
            "converged_fact_id": dialectic_result.converged.primary_fact_id,
            "converged_score": dialectic_result.converged.score,
            "opposition_challenges": opposition_challenges,
            "reopened": dialectic_result.reopened_result is not None,
            "final_status": dialectic_result.final_status,
        }

        trace = QueryTrace(
            query=query,
            temporal_context=temporal_context,
            query_time=query_time,
            executed_at=executed_at,
            execution_time_secs=execution_time_secs,
            reasoning_mode=initial.reasoning_mode,
            candidates=candidates,
            anchor_ids=initial.anchors,
            bundle_summary=bundle_summary,
            lyapunov_dimensions=initial.stability.dimensions,
            stability_score=initial.stability.score,
            stability_status=initial.stability.status,
            escape_triggered=initial.escape_triggered,
            escape_surfaced=initial.escape_surfaced,
            dialectic_result_summary=dialectic_result_summary,
        )
        self._trace_store.save(trace)
        return dialectic_result, trace

    def add_edge_at(
        self,
        source_id: str,
        target_id: str,
        edge_type: str,
        confidence: float,
        valid_from: datetime,
        valid_until: Optional[datetime] = None,
        established_by: str = "user",
        origin: str = "OBSERVED",
        role: str = "MECHANISTIC",
        derived_from: Optional[List[str]] = None,
    ) -> str:
        """Add a typed edge with explicit temporal validity and provenance."""
        provenance = EdgeProvenance(
            origin=EdgeOrigin(origin),
            role=EdgeRole(role),
            derived_from=derived_from or [],
            promotion_status="unpromoted",
        )
        return self.dag.add_edge(
            source_id=source_id,
            target_id=target_id,
            edge_type=EdgeType(edge_type),
            confidence=confidence,
            valid_from=valid_from,
            valid_until=valid_until,
            established_by=established_by,
            provenance=provenance,
        )

    def reinforce_edge(self, edge_id: str, used_at: Optional[datetime] = None) -> None:
        """Increase salience without promoting an inferred edge into discovered truth."""
        self.dag.reinforce_edge(edge_id, used_at=used_at)

    def promote_edge_to_discovered(
        self, edge_id: str, source_id: str, span: Optional[str] = None, observed_at: Optional[datetime] = None
    ) -> None:
        """Promote an edge only when an explicit evidence reference is supplied."""
        self.dag.promote_edge_to_discovered(
            edge_id, [EvidenceRef(source_id=source_id, span=span, observed_at=observed_at or datetime.now(timezone.utc))]
        )

    def critique(self, fact_ids: List[str]) -> StabilityResult:
        """Run the Lyapunov critic on a specific set of facts (no path enumeration)."""
        from llm_kosh.engine.reasoning.fiber_bundle import Fiber, CausalPath
        fibers = {}
        for fid in fact_ids:
            fact = self.dag.get_fact(fid)
            if fact:
                path = CausalPath(edges=[], confidence_product=fact.confidence,
                                  temporal_consistency=1.0)
                fibers[fid] = Fiber(fact=fact, paths=[path], degeneracy=1,
                                    max_confidence=fact.confidence)
        bundle = FiberBundle(fibers=fibers)
        return self._critic.evaluate(bundle)

    def explore(
        self, from_fact_id: str, to_fact_id: str, max_hops: int = 5
    ) -> FiberBundle:
        """Enumerate all causal paths between two known facts."""
        from llm_kosh.engine.reasoning.fiber_bundle import _enumerate_paths, Fiber
        query_time = time.time()
        to_fact = self.dag.get_fact(to_fact_id)
        if to_fact is None:
            return FiberBundle(fibers={})
        paths = _enumerate_paths(
            self.dag, from_fact_id, {to_fact_id}, max_hops, query_time
        )
        fibers = {}
        if to_fact_id in paths:
            path_list = paths[to_fact_id]
            fibers[to_fact_id] = Fiber(
                fact=to_fact,
                paths=path_list,
                degeneracy=len(path_list),
                max_confidence=max((p.confidence_product for p in path_list), default=0.0),
            )
        return FiberBundle(fibers=fibers)

    def dialectic_query(
        self,
        query: str,
        temporal_context: Optional[str] = None,
        depth: int = 3,
        reopen_on_challenge: bool = True,
    ) -> DialecticResult:
        """Run non-convergent -> convergent -> opposition -> re-open synthesis."""
        return self._dialectic.run(
            query=query,
            temporal_context=temporal_context,
            depth=depth,
            reopen_on_challenge=reopen_on_challenge,
        )

    def query_recursive(
        self,
        query: str,
        temporal_context: Optional[str] = None,
        depth: int = 3,
        max_iterations: int = 5,
        stability_threshold: float = 0.8,
    ) -> Tuple["QueryResult", "LoopState"]:
        """Run the recursive self-healing loop."""
        from llm_kosh.engine.reasoning.recursive_loop import LoopState
        if not self._enable_recursive:
            # Fall back to single-pass query
            result = self.query(query, temporal_context=temporal_context, depth=depth)
            state = LoopState(
                query=query,
                iteration_count=1,
                traces=[],
                termination_reason="recursive_disabled",
            )
            return result, state

        loop = self._make_recursive_loop()
        return loop.run(self, query, temporal_context, max_iterations, stability_threshold, depth)

    def query_dialectic_recursive(
        self,
        query: str,
        temporal_context: Optional[str] = None,
        depth: int = 3,
        max_iterations: int = 5,
        stability_threshold: float = 0.8,
        reopen_on_challenge: bool = True,
    ) -> Tuple["DialecticResult", "LoopState"]:
        """Run the dialectic query as the inner engine, recursive loop as outer wrapper."""
        from llm_kosh.engine.reasoning.recursive_loop import (
            RecursiveReasoningLoop,
            LoopState,
        )
        from llm_kosh.engine.reasoning.critique import TraceCritic, CrossQueryCritic
        from llm_kosh.engine.reasoning.healer import HealingExecutor, QueryParams
        from llm_kosh.engine.reasoning.discovery import DiscoveryGenerator, SafeDiscovery
        from llm_kosh.engine.reasoning.self_model import SelfModelController
        from llm_kosh.engine.reasoning.critique import WeaknessReport

        trace_critic = TraceCritic()
        cross_query_critic = CrossQueryCritic()
        healing_executor = HealingExecutor()
        discovery_generator = DiscoveryGenerator()
        safe_discovery = SafeDiscovery()
        self_model_controller = SelfModelController()

        state = LoopState(query=query)
        current_params = QueryParams(depth=depth)

        last_dialectic_result = None
        last_trace = None

        for iteration in range(max_iterations):
            if state.iteration_count >= max_iterations:
                state.termination_reason = "max_iterations_reached"
                break

            # Adapt
            adapted_params = self_model_controller.adapt_params(
                current_params, self._self_model
            )

            # Query (dialectic variant)
            dialectic_result, trace = self.dialectic_query_with_trace(
                query,
                temporal_context=temporal_context,
                depth=adapted_params.depth,
                reopen_on_challenge=reopen_on_challenge,
            )
            trace.iteration = iteration
            last_dialectic_result = dialectic_result
            last_trace = trace

            # Observe
            self._self_model.observe(trace)

            # Critique
            per_trace_weaknesses = trace_critic.analyze(trace)
            session_weaknesses = cross_query_critic.analyze_session(state.traces)
            weakness_report = WeaknessReport(
                trace_id=trace.trace_id,
                per_trace_weaknesses=per_trace_weaknesses,
                session_weaknesses=session_weaknesses,
            )

            # Heal
            next_params = healing_executor.heal(weakness_report, base_params=current_params)

            # Discover
            questions = discovery_generator.generate(weakness_report)
            iteration_discovery_results = []
            query_time = trace.query_time if trace.query_time is not None else 0.0
            for question in questions:
                dr = safe_discovery.execute(question, self.dag, dialectic_result.initial_result.bundle, query_time)
                iteration_discovery_results.append(dr)

            # Update state
            state.traces.append(trace)
            state.all_weaknesses.append(per_trace_weaknesses + session_weaknesses)
            state.discovery_results.extend(iteration_discovery_results)
            state.stability_progression.append(trace.stability_score)
            gain = (
                sum(dr.repair_strength for dr in iteration_discovery_results) / len(iteration_discovery_results)
                if iteration_discovery_results else 0.0
            )
            state.discovery_gain_progression.append(gain)
            state.iteration_count += 1
            current_params = next_params

            # Stopping conditions
            if trace.stability_score >= stability_threshold:
                state.termination_reason = "stability_threshold_reached"
                break

            if len(state.stability_progression) >= 3:
                s = state.stability_progression
                if s[-2] > s[-3] and s[-1] < s[-2] - 0.03:
                    state.termination_reason = "oscillation_detected"
                    break

            if iteration > 0 and iteration_discovery_results:
                if all(dr.repair_strength < 0.05 for dr in iteration_discovery_results):
                    state.termination_reason = "no_discovery_gain"
                    break
        else:
            state.termination_reason = "max_iterations_reached"

        return last_dialectic_result, state

    def _make_recursive_loop(self) -> "RecursiveReasoningLoop":
        """Construct the RecursiveReasoningLoop from the engine's components."""
        from llm_kosh.engine.reasoning.recursive_loop import RecursiveReasoningLoop
        from llm_kosh.engine.reasoning.critique import TraceCritic, CrossQueryCritic
        from llm_kosh.engine.reasoning.healer import HealingExecutor
        from llm_kosh.engine.reasoning.discovery import DiscoveryGenerator, SafeDiscovery
        from llm_kosh.engine.reasoning.self_model import SelfModelController
        return RecursiveReasoningLoop(
            trace_critic=TraceCritic(),
            cross_query_critic=CrossQueryCritic(),
            healing_executor=HealingExecutor(),
            discovery_generator=DiscoveryGenerator(),
            safe_discovery=SafeDiscovery(),
            self_model=self._self_model,
            self_model_controller=SelfModelController(),
        )

    # ------------------------------------------------------------------ helpers

    def _apply_reasoning_mode(self, bundle: FiberBundle, mode: ReasoningMode) -> FiberBundle:
        """Apply lightweight empirical/theoretical/balanced path policy."""
        if mode != ReasoningMode.EMPIRICAL:
            return bundle

        for fid, fiber in list(bundle.fibers.items()):
            filtered = []
            for path in fiber.paths:
                speculative = False
                for edge in path.edges:
                    if edge.provenance.origin == EdgeOrigin.HYPOTHETICAL:
                        speculative = True
                    if edge.provenance.role == EdgeRole.ANALOGICAL and not edge.provenance.evidence_refs:
                        speculative = True
                if not speculative:
                    filtered.append(path)
            fiber.paths = filtered
            fiber.degeneracy = len(filtered)
            fiber.max_confidence = max((p.confidence_product for p in filtered), default=0.0)
            if not filtered and fid not in self.dag.nodes:
                bundle.fibers.pop(fid, None)
        return bundle

    def _select_anchors(
        self,
        candidates: List[Tuple["TemporalFact", int, float]],
        score_threshold: float = 0.25,
    ) -> List[str]:
        """
        Select anchor fact IDs from retrieval candidates by score threshold.

        Replaces the former hard top-5 limit. All candidates with score >=
        score_threshold are included; if none clear the bar, the single
        highest-scoring candidate is used as a fallback.

        A simple deduplication pass removes anchors whose score is within 0.05
        of an already-selected anchor AND whose ID shares the same 4-character
        prefix (same synthetic project shard).
        """
        above = [(fact, dist, score) for fact, dist, score in candidates
                 if score >= score_threshold]

        if not above:
            if candidates:
                return [candidates[0][0].id]
            return []

        selected: List[str] = []
        selected_scores: List[float] = []

        for fact, _dist, score in above:
            # Deduplicate: skip if a nearly-identical anchor already selected.
            # Use fact.id[5:9] — the first 4 chars of the hash segment after the
            # "fact." prefix — so facts from the same synthetic shard are deduped
            # while facts from different shards (distinct hash prefixes) are kept.
            fact_prefix = fact.id[5:9] if len(fact.id) > 9 else fact.id
            duplicate = any(
                fact_prefix == (sel_id[5:9] if len(sel_id) > 9 else sel_id)
                and abs(score - sel_score) < 0.05
                for sel_id, sel_score in zip(selected, selected_scores)
            )
            if not duplicate:
                selected.append(fact.id)
                selected_scores.append(score)

        return selected

    @staticmethod
    def _parse_temporal_context(ctx: Optional[str]) -> float:
        if ctx is None:
            return time.time()
        try:
            return float(ctx)
        except (TypeError, ValueError):
            pass
        try:
            return datetime.fromisoformat(ctx.replace("Z", "+00:00")).timestamp()
        except Exception:
            return time.time()


# Temporal evidence layer: lets TheHypoKosh reason when exact timestamps are absent.
from llm_kosh.engine.reasoning.temporal_evidence import (  # noqa: E402,F401
    TemporalAuditResult,
    TemporalConstraint,
    TemporalEvidence,
    TemporalEvidenceEngine,
    TemporalPrecision,
    TemporalSource,
    TemporalStatus,
)
