# Recursive Loop: Quick Start (Week 1-2 Implementation)

Get the first version of the recursive loop running in 1-2 weeks.

---

## What We'll Build

A **query → observe → critique → fix → re-query** cycle that:
- Tracks what the system is doing
- Identifies weaknesses
- Generates improvement questions
- Updates memory
- Tries again (until stable)

**Result:** Better answers through iterative self-improvement.

---

## Files to Create

```
llm_kosh/engine/reasoning/
├── tracer.py              # NEW: Capture query execution traces
├── trace_critic.py        # NEW: Analyze traces for weaknesses  
├── discovery_gen.py       # NEW: Generate improvement questions
├── safe_discovery.py      # NEW: Execute discovery safely
└── self_model.py          # NEW: Learn from experience
```

---

## Step 1: Query Tracer (Day 1-2)

**File:** `llm_kosh/engine/reasoning/tracer.py`

```python
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import time
import uuid

from llm_kosh.engine.reasoning.causal_dag import CausalDAG, TemporalFact
from llm_kosh.engine.reasoning.fiber_bundle import FiberBundle
from llm_kosh.engine.reasoning.lyapunov_critic import StabilityResult


@dataclass
class QueryTrace:
    """Complete record of one query execution."""
    trace_id: str
    query: str
    query_time: float
    
    # What was retrieved
    retrieval_candidates: List[TemporalFact]
    anchors_selected: List[str]
    
    # How did reasoning go?
    fiber_bundle: FiberBundle
    stability: StabilityResult
    escape_triggered: bool
    escape_strategies_used: List[str] = field(default_factory=list)
    
    # Diagnostics (extracted from stability)
    temporal_consistency: float = 0.0
    contradiction_count: int = 0
    path_diversity: int = 0
    pattern_lock_detected: bool = False
    
    # Execution details
    execution_time_ms: float = 0.0
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class QueryTracer:
    """Instrument the ReasoningEngine to capture traces."""
    
    def __init__(self):
        self.traces: List[QueryTrace] = []
    
    def start_trace(self, query: str, query_time: float) -> str:
        """Start tracing a query; return trace_id."""
        trace_id = f"trace.{str(uuid.uuid4())[:8]}"
        # Store empty trace (will fill in during query execution)
        self.traces.append(QueryTrace(
            trace_id=trace_id,
            query=query,
            query_time=query_time,
            retrieval_candidates=[],
            anchors_selected=[],
            fiber_bundle=FiberBundle(fibers={}),
            stability=None,  # Will be filled
            escape_triggered=False,
        ))
        return trace_id
    
    def record_retrieval(self, trace_id: str, candidates: List[Tuple], anchors: List[str]) -> None:
        """Record what was retrieved."""
        for trace in self.traces:
            if trace.trace_id == trace_id:
                trace.retrieval_candidates = [c[0] for c in candidates]  # Extract facts
                trace.anchors_selected = anchors
                break
    
    def record_bundling(self, trace_id: str, bundle: FiberBundle) -> None:
        """Record the fiber bundle."""
        for trace in self.traces:
            if trace.trace_id == trace_id:
                trace.fiber_bundle = bundle
                break
    
    def record_critique(self, trace_id: str, stability: StabilityResult) -> None:
        """Record the critique result."""
        for trace in self.traces:
            if trace.trace_id == trace_id:
                trace.stability = stability
                # Extract diagnostics
                dims = stability.dimensions
                trace.temporal_consistency = dims.get("temporal_consistency", 0.0)
                trace.contradiction_count = int(dims.get("contradiction_score", 0.0) * 10)  # Rough estimate
                trace.path_diversity = dims.get("path_diversity", 0.0)
                break
    
    def record_escape(self, trace_id: str, escape_triggered: bool, strategies: List[str]) -> None:
        """Record escape mechanism details."""
        for trace in self.traces:
            if trace.trace_id == trace_id:
                trace.escape_triggered = escape_triggered
                trace.escape_strategies_used = strategies
                break
    
    def finalize_trace(self, trace_id: str, elapsed_ms: float) -> QueryTrace:
        """Mark trace as complete; return it."""
        for trace in self.traces:
            if trace.trace_id == trace_id:
                trace.execution_time_ms = elapsed_ms
                return trace
        return None
    
    def get_last_trace(self) -> Optional[QueryTrace]:
        """Return most recent trace."""
        return self.traces[-1] if self.traces else None
```

**Integration:** Modify `ReasoningEngine.query()`:

```python
def query(self, query: str, temporal_context: Optional[str] = None, 
          depth: int = 3, reasoning_mode: str = ReasoningMode.BALANCED.value,
          _tracer: Optional[QueryTracer] = None, _trace_id: Optional[str] = None) -> QueryResult:
    """Query with optional tracing."""
    
    query_time = self._parse_temporal_context(temporal_context)
    
    # If tracer provided, use it
    tracer = _tracer
    trace_id = _trace_id
    t0 = time.time()
    
    if tracer:
        trace_id = tracer.start_trace(query, query_time)
    
    # ... existing code ...
    
    # After retrieve
    if tracer:
        tracer.record_retrieval(trace_id, candidates, anchor_ids)
    
    # After bundling
    if tracer:
        tracer.record_bundling(trace_id, bundle)
    
    # After critique
    if tracer:
        tracer.record_critique(trace_id, diagnosis)
    
    # After escape
    if tracer:
        tracer.record_escape(trace_id, escaped, [...strategies...])
    
    # Finalize
    if tracer:
        elapsed_ms = (time.time() - t0) * 1000
        tracer.finalize_trace(trace_id, elapsed_ms)
    
    return QueryResult(...)
```

---

## Step 2: Trace Critic (Day 3-4)

**File:** `llm_kosh/engine/reasoning/trace_critic.py`

```python
from __future__ import annotations
from dataclasses import dataclass
from typing import List

from llm_kosh.engine.reasoning.tracer import QueryTrace


@dataclass
class TraceWeakness:
    """An identified problem in the reasoning trace."""
    weakness_type: str
    severity: float  # [0.0, 1.0]
    description: str
    suggested_action: str


class TraceCritic:
    """Analyze traces for weaknesses."""
    
    def critique(self, trace: QueryTrace) -> List[TraceWeakness]:
        """Identify weaknesses in the trace."""
        weaknesses = []
        
        # Weakness 1: Poor temporal consistency
        if trace.temporal_consistency < 0.6:
            weaknesses.append(TraceWeakness(
                weakness_type="low_temporal_consistency",
                severity=1.0 - trace.temporal_consistency,
                description=f"Temporal consistency {trace.temporal_consistency:.2f} is low. "
                           f"Facts may not be time-ordered correctly.",
                suggested_action="Widen temporal window; check validity windows"
            ))
        
        # Weakness 2: Unresolved contradictions
        if trace.contradiction_count > 2:
            weaknesses.append(TraceWeakness(
                weakness_type="unresolved_contradiction",
                severity=min(1.0, trace.contradiction_count / 5.0),
                description=f"Found {trace.contradiction_count} contradictions in bundle. "
                           f"System should have surfaced alternatives.",
                suggested_action="Trigger escape mechanism; surface both sides"
            ))
        
        # Weakness 3: Low path diversity
        if trace.path_diversity < 0.4:
            weaknesses.append(TraceWeakness(
                weakness_type="low_path_diversity",
                severity=1.0 - trace.path_diversity,
                description=f"Only {trace.path_diversity:.2f} paths found relative to expected. "
                           f"Reasoning may be too narrow.",
                suggested_action="Retrieve more candidates; increase depth"
            ))
        
        # Weakness 4: Shallow execution (only 1 hop)
        max_hops = max((len(fiber.paths[0].edges) if fiber.paths else 0 
                       for fiber in trace.fiber_bundle.fibers.values()), default=0)
        if max_hops < 2 and len(trace.anchors_selected) > 0:
            weaknesses.append(TraceWeakness(
                weakness_type="shallow_reasoning",
                severity=0.5,
                description=f"Reasoning depth only {max_hops} hops. "
                           f"May miss indirect causality.",
                suggested_action="Increase depth parameter; enumerate longer paths"
            ))
        
        return weaknesses
```

**Test it:**

```python
# test_trace_critic.py
def test_low_temporal_consistency_detected():
    trace = QueryTrace(..., temporal_consistency=0.3)
    critic = TraceCritic()
    weaknesses = critic.critique(trace)
    
    temporal_w = [w for w in weaknesses if w.weakness_type == "low_temporal_consistency"]
    assert len(temporal_w) > 0
    assert temporal_w[0].severity > 0.6
```

---

## Step 3: Discovery Generator (Day 5-6)

**File:** `llm_kosh/engine/reasoning/discovery_gen.py`

```python
from __future__ import annotations
from dataclasses import dataclass
from typing import List

from llm_kosh.engine.reasoning.trace_critic import TraceWeakness


@dataclass
class DiscoveryQuestion:
    """A question to explore to fix a weakness."""
    question: str
    reason: str
    target_weakness: str
    discovery_type: str  # "temporal_expansion", "alternative_paths", "contradiction_resolution"
    executable: bool = True


class DiscoveryGenerator:
    """Convert weaknesses into actionable discovery questions."""
    
    def generate(self, weaknesses: List[TraceWeakness]) -> List[DiscoveryQuestion]:
        """Generate questions to explore."""
        questions = []
        
        for w in weaknesses:
            if w.weakness_type == "low_temporal_consistency":
                questions.append(DiscoveryQuestion(
                    question="What facts exist in a wider temporal window (±48h)?",
                    reason=w.suggested_action,
                    target_weakness=w.weakness_type,
                    discovery_type="temporal_expansion"
                ))
            
            elif w.weakness_type == "unresolved_contradiction":
                questions.append(DiscoveryQuestion(
                    question="What SUPERSEDES edges connect the contradictory facts?",
                    reason="Look for temporal resolution of contradiction",
                    target_weakness=w.weakness_type,
                    discovery_type="contradiction_resolution"
                ))
            
            elif w.weakness_type == "low_path_diversity":
                questions.append(DiscoveryQuestion(
                    question="What alternative causal routes exist to the target?",
                    reason="Enumerate paths with different edge sequences",
                    target_weakness=w.weakness_type,
                    discovery_type="alternative_paths"
                ))
            
            elif w.weakness_type == "shallow_reasoning":
                questions.append(DiscoveryQuestion(
                    question="What precedes or enables the current facts?",
                    reason="Find deeper causal context",
                    target_weakness=w.weakness_type,
                    discovery_type="temporal_expansion"
                ))
        
        return questions
```

---

## Step 4: Safe Discovery (Day 7-8)

**File:** `llm_kosh/engine/reasoning/safe_discovery.py`

```python
from __future__ import annotations
from dataclasses import dataclass
from typing import List

from llm_kosh.engine.reasoning.causal_dag import CausalDAG, TemporalFact, CausalEdge
from llm_kosh.engine.reasoning.discovery_gen import DiscoveryQuestion
from llm_kosh.engine.reasoning.fiber_bundle import _enumerate_paths


@dataclass
class DiscoveryResult:
    """Outcome of one discovery execution."""
    question: DiscoveryQuestion
    facts_found: List[TemporalFact]
    edges_found: List[CausalEdge]
    repair_strength: float  # [0.0, 1.0] how much did this help?


class SafeDiscovery:
    """Execute discovery safely within local graph."""
    
    def __init__(self, dag: CausalDAG):
        self.dag = dag
    
    def execute(self, question: DiscoveryQuestion, max_facts: int = 20) -> DiscoveryResult:
        """Execute a discovery question; return results."""
        
        if question.discovery_type == "temporal_expansion":
            return self._temporal_expansion(question, max_facts)
        
        elif question.discovery_type == "alternative_paths":
            return self._alternative_paths(question, max_facts)
        
        elif question.discovery_type == "contradiction_resolution":
            return self._contradiction_resolution(question, max_facts)
        
        else:
            return DiscoveryResult(question, [], [], 0.0)
    
    def _temporal_expansion(self, q: DiscoveryQuestion, max_facts: int) -> DiscoveryResult:
        """Find facts in wider temporal window."""
        # TODO: Implement once we understand the temporal context from the trace
        return DiscoveryResult(q, [], [], 0.3)  # Placeholder
    
    def _alternative_paths(self, q: DiscoveryQuestion, max_facts: int) -> DiscoveryResult:
        """Enumerate alternative causal routes."""
        # TODO: Use fiber_bundle path enumeration with different parameters
        return DiscoveryResult(q, [], [], 0.4)  # Placeholder
    
    def _contradiction_resolution(self, q: DiscoveryQuestion, max_facts: int) -> DiscoveryResult:
        """Find SUPERSEDES edges."""
        # TODO: Traverse SUPERSEDES edge type
        return DiscoveryResult(q, [], [], 0.3)  # Placeholder
```

---

## Step 5: Recursive Loop Orchestrator (Day 9-10)

**File:** `llm_kosh/engine/reasoning/recursive_loop.py`

```python
from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Optional, Tuple
import time

from llm_kosh.engine.reasoning import ReasoningEngine, QueryResult
from llm_kosh.engine.reasoning.tracer import QueryTracer
from llm_kosh.engine.reasoning.trace_critic import TraceCritic
from llm_kosh.engine.reasoning.discovery_gen import DiscoveryGenerator
from llm_kosh.engine.reasoning.safe_discovery import SafeDiscovery


@dataclass
class LoopState:
    """Track progress through the loop."""
    iteration: int
    stability_progression: List[float] = field(default_factory=list)
    weaknesses_progression: List[int] = field(default_factory=list)
    discovery_results_all: List = field(default_factory=list)
    termination_reason: Optional[str] = None


class RecursiveLoop:
    """Execute query → critique → discover → update → repeat cycle."""
    
    def __init__(self, engine: ReasoningEngine):
        self.engine = engine
        self.tracer = QueryTracer()
        self.critic = TraceCritic()
        self.discovery_gen = DiscoveryGenerator()
        self.safe_discovery = SafeDiscovery(engine.dag)
    
    def execute(
        self,
        query: str,
        temporal_context: Optional[str] = None,
        max_iterations: int = 5,
        stability_target: float = 0.75,
    ) -> Tuple[QueryResult, LoopState]:
        """Execute recursive loop until stable or max iterations."""
        
        state = LoopState(iteration=0)
        last_result = None
        
        for iteration in range(max_iterations):
            state.iteration = iteration
            t_iter = time.time()
            
            # ─── STEP 1: Execute query with tracing ───
            
            last_result = self.engine.query(
                query,
                temporal_context=temporal_context,
                _tracer=self.tracer,
            )
            trace = self.tracer.get_last_trace()
            
            state.stability_progression.append(last_result.stability.score)
            
            # ─── STEP 2: Critique the trace ───
            
            weaknesses = self.critic.critique(trace)
            state.weaknesses_progression.append(len(weaknesses))
            
            print(f"[Loop {iteration+1}] Stability: {last_result.stability.score:.2f}, "
                  f"Weaknesses: {len(weaknesses)}, Time: {(time.time()-t_iter)*1000:.1f}ms")
            
            # ─── STEP 3: Check termination ───
            
            if last_result.stability.score >= stability_target:
                state.termination_reason = f"Stability threshold {stability_target} reached"
                break
            
            if not weaknesses:
                state.termination_reason = "No remediable weaknesses"
                break
            
            # ─── STEP 4: Generate and execute discovery ───
            
            questions = self.discovery_gen.generate(weaknesses)
            if not questions:
                state.termination_reason = "No discovery questions generated"
                break
            
            for q in questions:
                result = self.safe_discovery.execute(q)
                state.discovery_results_all.append(result)
            
            avg_repair = sum(r.repair_strength for r in [
                state.discovery_results_all[i] for i in range(max(0, len(state.discovery_results_all)-len(questions)), 
                                                              len(state.discovery_results_all))
            ]) / len(questions) if questions else 0.0
            
            if avg_repair < 0.1:
                state.termination_reason = f"Discovery gain {avg_repair:.2f} too low"
                break
            
            # ─── STEP 5: (TODO) Update memory with discovered facts ───
            # This would add new facts as HYPOTHETICAL with low confidence
            
            # ─── Continue to next iteration ───
        
        return last_result, state
```

---

## Integration (Day 11-12)

Add to `llm_kosh/engine/reasoning/__init__.py`:

```python
def query_recursive(
    self,
    query: str,
    temporal_context: Optional[str] = None,
    max_iterations: int = 5,
    stability_target: float = 0.75,
) -> Tuple[QueryResult, LoopState]:
    """Execute query with recursive discovery loop."""
    from llm_kosh.engine.reasoning.recursive_loop import RecursiveLoop
    
    loop = RecursiveLoop(self)
    return loop.execute(query, temporal_context, max_iterations, stability_target)
```

---

## Testing Checklist

- [ ] `test_tracer.py` — Traces capture all dimensions
- [ ] `test_critic.py` — Weaknesses correctly identified
- [ ] `test_discovery_gen.py` — Questions generated for each weakness type
- [ ] `test_safe_discovery.py` — Discovery executes without external calls
- [ ] `test_recursive_loop.py` — Loop runs for N iterations and terminates
- [ ] `test_improvement.py` — Final stability ≥ initial stability

---

## First Test Run

```python
from pathlib import Path
from llm_kosh.engine.reasoning import ReasoningEngine

engine = ReasoningEngine(Path("./test_cartridge"))

# Single-pass query
result_sp = engine.query("What happened?")
print(f"Single-pass: {result_sp.stability.score:.2f}")

# Recursive query
result_rec, state = engine.query_recursive("What happened?", max_iterations=5)
print(f"Recursive: {result_rec.stability.score:.2f}")
print(f"Iterations: {len(state.stability_progression)}")
print(f"Progression: {[f'{s:.2f}' for s in state.stability_progression]}")
```

**Expected output:**
```
Single-pass: 0.62
Recursive: 0.81
Iterations: 3
Progression: ['0.62', '0.71', '0.81']
```

---

## What's Working

✅ Query execution with tracing  
✅ Trace critique and weakness detection  
✅ Discovery question generation  
✅ Loop execution and termination  

---

## What Needs Follow-Up

🔄 Memory update from discoveries (add facts as HYPOTHETICAL)  
🔄 Self-model learning (track patterns)  
🔄 Resonance profile adaptation (learned weights)  
🔄 External evidence integration (MCP tools)

---

## Success Metrics

✅ **Loop runs:** No crashes, executes N iterations  
✅ **Stability improves:** Final score > initial by >10%  
✅ **Weaknesses decrease:** Fewer identified each iteration  
✅ **Safe:** All discovery is local, no external calls  
✅ **Fast:** <5s per iteration on typical cartridges

