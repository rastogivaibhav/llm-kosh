# Recursive Self-Healing Discovery Loop: Implementation Plan

**Status:** Blueprint for v1.1 release  
**Priority:** High—enables self-model building  
**Effort:** 3-4 sprints (40-50 engineering days)

---

## Problem: Current State

The system currently has a **single-pass query pipeline**:

```
query → retrieve candidates → build fiber bundle → lyapunov critique
        → escape (if unstable) → return result
```

**Gap:** No **self-observation** → no **self-model building** → system doesn't learn its own reasoning patterns.

The PDF Section 7.6 describes the full loop:
```
query
  → answer
  → observe trace
  → critique trace
  → safe repair proposals
  → discovery questions
  → executable discovery tasks
  → memory update (marked low-confidence)
  → update self-model
  → query again (with updated self-model)
```

---

## Solution: Recursive Self-Healing Discovery Loop

A **multi-pass reasoning system** that:
1. Executes a query
2. Observes its own reasoning trace
3. Critiques the trace for weaknesses
4. Proposes safe repairs (no external side effects)
5. Generates discovery questions
6. Executes discovery tasks locally
7. Updates memory with new discoveries (marked as speculative)
8. Updates self-model with learned patterns
9. Re-runs query with enhanced self-model
10. Terminates when stability + discovery thresholds met

---

## Architecture Design

### Layer 1: Query Tracing (New)

**File:** `llm_kosh/engine/reasoning/tracer.py`

Track every step of the reasoning process:

```python
@dataclass
class QueryTrace:
    """Complete record of one query execution."""
    query: str
    query_time: float
    
    # Execution steps
    retrieval_candidates: List[TemporalFact]
    anchors_selected: List[str]
    fiber_bundle: FiberBundle
    stability: StabilityResult
    escape_triggered: bool
    escape_strategies_used: List[str]
    
    # Diagnostics
    temporal_consistency: float
    contradiction_count: int
    path_diversity: int
    pattern_lock_detected: bool
    
    # Outcome
    final_answer_fibers: Dict[str, Fiber]
    confidence_product: float
    
    # Metadata
    execution_time_ms: float
    trace_id: str
    parent_trace_id: Optional[str] = None  # For recursive passes


class QueryTracer:
    """Instrument the reasoning engine to capture traces."""
    
    def __init__(self, engine: ReasoningEngine):
        self.engine = engine
        self.traces: List[QueryTrace] = []
    
    def trace_query(self, query: str, ...) -> Tuple[QueryResult, QueryTrace]:
        """Execute query with full tracing."""
        trace = QueryTrace(...)
        # Instrument each step, capture state
        result = self.engine.query(query, ...)
        return result, trace
```

### Layer 2: Trace Critique (New)

**File:** `llm_kosh/engine/reasoning/trace_critic.py`

Analyze the trace for weaknesses:

```python
@dataclass
class TraceWeakness:
    """Identified problem in reasoning trace."""
    weakness_type: str  # "low_temporal_consistency" | "contradiction_unresolved" |
                        # "single_path_dominance" | "missing_temporal_context" | etc.
    severity: float     # [0.0, 1.0]
    location: str       # "retrieval" | "bundling" | "critique" | "escape"
    description: str
    suggested_repair: str


class TraceCritic:
    """Diagnose weaknesses in a reasoning trace."""
    
    def critique_trace(self, trace: QueryTrace) -> List[TraceWeakness]:
        """Return list of identified weaknesses."""
        weaknesses = []
        
        # Check 1: Temporal consistency too low
        if trace.temporal_consistency < 0.6:
            weaknesses.append(TraceWeakness(
                weakness_type="low_temporal_consistency",
                severity=1.0 - trace.temporal_consistency,
                location="critique",
                description=f"Temporal consistency {trace.temporal_consistency:.2f} suggests time-ordering issues",
                suggested_repair="Widen temporal window or re-anchor at different time"
            ))
        
        # Check 2: Contradictions not resolved
        if trace.contradiction_count > 2 and not trace.escape_triggered:
            weaknesses.append(TraceWeakness(
                weakness_type="contradiction_unresolved",
                severity=min(1.0, trace.contradiction_count / 5),
                location="escape",
                description=f"Found {trace.contradiction_count} contradictions but escape didn't trigger",
                suggested_repair="Explicitly surface contradictory facts in next pass"
            ))
        
        # Check 3: Single path dominance (pattern lock)
        if trace.pattern_lock_detected and len(trace.anchors_selected) < 3:
            weaknesses.append(TraceWeakness(
                weakness_type="single_path_dominance",
                severity=0.7,
                location="retrieval",
                description="Result dominated by single path; few alternative routes found",
                suggested_repair="Retrieve more diverse candidates or widen resonance profile"
            ))
        
        # Check 4: Missing temporal context
        max_hops = max((len(fiber.paths) for fiber in trace.fiber_bundle.fibers.values()), default=1)
        if max_hops == 1 and trace.query_time > 0:
            # Might benefit from deeper traversal
            weaknesses.append(TraceWeakness(
                weakness_type="shallow_temporal_context",
                severity=0.4,
                location="bundling",
                description="All paths have ≤1 hop; deeper traversal might reveal context",
                suggested_repair="Increase depth parameter and re-query"
            ))
        
        return weaknesses
```

### Layer 3: Discovery Question Generation (New)

**File:** `llm_kosh/engine/reasoning/discovery_generator.py`

Convert weaknesses into discovery tasks:

```python
@dataclass
class DiscoveryQuestion:
    """A question to explore in memory to repair reasoning."""
    question: str
    reason: str  # Why this question matters
    target_weakness: str
    discovery_type: str  # "temporal_expansion" | "contradiction_resolution" |
                         # "path_diversification" | "analogy_search" | "gap_filling"
    expected_outcome: str
    executable: bool = True  # Can be executed locally


class DiscoveryGenerator:
    """Generate discovery questions from identified weaknesses."""
    
    def generate_from_weaknesses(
        self,
        trace: QueryTrace,
        weaknesses: List[TraceWeakness],
    ) -> List[DiscoveryQuestion]:
        """Convert each weakness into a discovery question."""
        questions = []
        
        for weakness in weaknesses:
            if weakness.weakness_type == "low_temporal_consistency":
                questions.append(DiscoveryQuestion(
                    question=f"What events occur ±48h around {trace.query_time}?",
                    reason="Widen temporal window to find facts outside current validity",
                    target_weakness=weakness.weakness_type,
                    discovery_type="temporal_expansion",
                    expected_outcome="Additional temporally-adjacent facts"
                ))
            
            elif weakness.weakness_type == "contradiction_unresolved":
                questions.append(DiscoveryQuestion(
                    question=f"What supersedes the contradictory facts identified?",
                    reason="Contradictions may be resolved by temporal updates",
                    target_weakness=weakness.weakness_type,
                    discovery_type="contradiction_resolution",
                    expected_outcome="SUPERSEDES edges linking old → new states"
                ))
            
            elif weakness.weakness_type == "single_path_dominance":
                questions.append(DiscoveryQuestion(
                    question=f"What alternative routes exist from anchors to target?",
                    reason="Low degeneracy suggests underexploration",
                    target_weakness=weakness.weakness_type,
                    discovery_type="path_diversification",
                    expected_outcome="Additional causal paths with different edge sequences"
                ))
            
            elif weakness.weakness_type == "shallow_temporal_context":
                questions.append(DiscoveryQuestion(
                    question=f"What facts precede or enable the query target?",
                    reason="Deeper context may reveal indirect causality",
                    target_weakness=weakness.weakness_type,
                    discovery_type="path_diversification",
                    expected_outcome="Facts further back in causal chain"
                ))
        
        return questions
```

### Layer 4: Safe Discovery Execution (New)

**File:** `llm_kosh/engine/reasoning/safe_discovery.py`

Execute discovery tasks WITHOUT external side effects:

```python
@dataclass
class DiscoveryResult:
    """Outcome of one discovery execution."""
    question: DiscoveryQuestion
    facts_found: List[TemporalFact]
    edges_found: List[CausalEdge]
    new_hypotheses: List[str]  # Speculative bridges (marked HYPOTHETICAL)
    repair_strength: float  # [0.0, 1.0] how much does this repair the weakness?


class SafeDiscovery:
    """Execute discovery tasks locally within memory graph."""
    
    def __init__(self, dag: CausalDAG):
        self.dag = dag
    
    def execute_discovery(
        self,
        question: DiscoveryQuestion,
        max_facts: int = 20,
    ) -> DiscoveryResult:
        """Execute discovery question; return findings."""
        
        if question.discovery_type == "temporal_expansion":
            return self._temporal_expansion(question, max_facts)
        elif question.discovery_type == "contradiction_resolution":
            return self._contradiction_resolution(question, max_facts)
        elif question.discovery_type == "path_diversification":
            return self._path_diversification(question, max_facts)
        elif question.discovery_type == "analogy_search":
            return self._analogy_search(question, max_facts)
        elif question.discovery_type == "gap_filling":
            return self._gap_filling(question, max_facts)
        else:
            return DiscoveryResult(question, [], [], [], 0.0)
    
    def _temporal_expansion(self, question: DiscoveryQuestion, max_facts: int) -> DiscoveryResult:
        """Find facts in wider temporal window."""
        facts_found = []
        # Query interval tree with wider window
        # Return adjacent facts not in original query
        return DiscoveryResult(
            question=question,
            facts_found=facts_found,
            edges_found=[],
            new_hypotheses=[],
            repair_strength=len(facts_found) / max_facts  # Heuristic
        )
    
    def _contradiction_resolution(self, question: DiscoveryQuestion, max_facts: int) -> DiscoveryResult:
        """Find SUPERSEDES edges linking contradictory facts."""
        edges_found = []
        # Traverse SUPERSEDES edges from contradictory facts
        # Return chain showing temporal resolution
        return DiscoveryResult(
            question=question,
            facts_found=[],
            edges_found=edges_found,
            new_hypotheses=[],
            repair_strength=len(edges_found) / 5  # Heuristic
        )
    
    def _path_diversification(self, question: DiscoveryQuestion, max_facts: int) -> DiscoveryResult:
        """Enumerate additional causal paths."""
        facts_found = []
        new_hypotheses = []
        # Run fiber bundle enumeration with different parameters
        # Propose speculative bridges (analogies, inferences) as HYPOTHETICAL
        return DiscoveryResult(
            question=question,
            facts_found=facts_found,
            edges_found=[],
            new_hypotheses=new_hypotheses,
            repair_strength=len(new_hypotheses) / 10  # Heuristic
        )
    
    def _analogy_search(self, question: DiscoveryQuestion, max_facts: int) -> DiscoveryResult:
        """Find structurally similar patterns in other domains."""
        new_hypotheses = []
        # Search for facts with STRUCTURALLY_SIMILAR edges
        # Propose ANALOGY bridges as HYPOTHETICAL
        return DiscoveryResult(
            question=question,
            facts_found=[],
            edges_found=[],
            new_hypotheses=new_hypotheses,
            repair_strength=len(new_hypotheses) / 5  # Heuristic
        )
    
    def _gap_filling(self, question: DiscoveryQuestion, max_facts: int) -> DiscoveryResult:
        """Identify and mark knowledge gaps."""
        new_hypotheses = []
        # Traverse graph, find missing edges (explicit gaps)
        # Create HYPOTHETICAL "unknown" facts with confidence=0.0
        return DiscoveryResult(
            question=question,
            facts_found=[],
            edges_found=[],
            new_hypotheses=new_hypotheses,
            repair_strength=0.3  # Gap-filling is preparatory
        )
```

### Layer 5: Self-Model Building (New)

**File:** `llm_kosh/engine/reasoning/self_model.py`

Learn patterns from reasoning traces:

```python
@dataclass
class ReasoningPattern:
    """A learned pattern in the system's reasoning."""
    pattern_type: str  # "high_success_query_profile" | "common_weakness" | 
                       # "effective_escape_strategy" | "discovery_effectiveness"
    description: str
    supporting_traces: List[str]  # IDs of traces that demonstrate this pattern
    confidence: float  # [0.0, 1.0] how confident is this pattern?
    effectiveness_score: float  # [0.0, 1.0] how much does this pattern help?


class SelfModel:
    """Tracks the system's reasoning patterns and learned behaviors."""
    
    def __init__(self, root: Path):
        self.root = root
        self.patterns: Dict[str, ReasoningPattern] = {}
        self.trace_history: List[QueryTrace] = []
        self.discovery_effectiveness: Dict[str, float] = {}  # question_type → avg repair_strength
    
    def observe(self, trace: QueryTrace) -> None:
        """Record a new reasoning trace."""
        self.trace_history.append(trace)
        
        # Extract patterns
        if trace.stability.status == "stable":
            self._record_success_pattern(trace)
        
        if trace.escape_triggered:
            self._record_escape_effectiveness(trace)
        
        if trace.escape_surfaced:
            self._record_discovery_value(trace)
    
    def update_from_discovery(self, discovery_results: List[DiscoveryResult]) -> None:
        """Learn effectiveness of discovery strategies."""
        for result in discovery_results:
            q_type = result.question.discovery_type
            if q_type not in self.discovery_effectiveness:
                self.discovery_effectiveness[q_type] = []
            self.discovery_effectiveness[q_type].append(result.repair_strength)
    
    def get_recommended_resonance_profile(self) -> dict:
        """Return resonance profile learned from successful patterns."""
        # Aggregate success patterns → recommend better resonance weights
        # E.g., if temporal_context_width=7d works well, recommend it
        profile = {
            "temporal_depth": self._learned_temporal_depth(),
            "semantic_reach": self._learned_semantic_reach(),
            "diversity_weight": self._learned_diversity_weight(),
        }
        return profile
    
    def _record_success_pattern(self, trace: QueryTrace) -> None:
        """Record what made this query succeed."""
        pass  # Implementation
    
    def _record_escape_effectiveness(self, trace: QueryTrace) -> None:
        """Record which escape strategies worked."""
        pass  # Implementation
    
    def _record_discovery_value(self, trace: QueryTrace) -> None:
        """Record what discovery questions yielded insight."""
        pass  # Implementation
    
    def _learned_temporal_depth(self) -> float:
        """Infer optimal temporal window from past successes."""
        pass  # Implementation


class SelfModelController:
    """Manages self-model updates and query re-planning."""
    
    def __init__(self, self_model: SelfModel):
        self.self_model = self_model
    
    def adapt_next_query(self, original_query: str, previous_trace: QueryTrace) -> dict:
        """Propose modifications to query execution based on self-model."""
        params = {
            "depth": 3,                                    # default
            "reasoning_mode": ReasoningMode.BALANCED,      # default
            "resonance_profile": {},                       # default
            "escape_threshold": 0.4,                       # default
        }
        
        # If trace showed shallow paths, increase depth
        if previous_trace.path_diversity < 0.3:
            params["depth"] = 5
        
        # If contradictions dominate, switch to empirical mode
        if previous_trace.contradiction_count > 3:
            params["reasoning_mode"] = ReasoningMode.EMPIRICAL
        
        # Apply learned resonance profile
        params["resonance_profile"] = self.self_model.get_recommended_resonance_profile()
        
        return params
```

### Layer 6: Recursive Loop Orchestrator (New)

**File:** `llm_kosh/engine/reasoning/recursive_loop.py`

Coordinate the full recursive cycle:

```python
@dataclass
class LoopState:
    """Track progress through recursive discovery cycle."""
    iteration: int
    query: str
    traces: List[QueryTrace]
    all_weaknesses: List[TraceWeakness]
    all_discovery_results: List[DiscoveryResult]
    
    stability_progression: List[float]  # Stability score each iteration
    discovery_strength_progression: List[float]  # Avg repair strength each iteration
    
    should_continue: bool = True
    termination_reason: Optional[str] = None


class RecursiveReasoningLoop:
    """Execute the full recursive self-healing discovery loop."""
    
    def __init__(self, engine: ReasoningEngine):
        self.engine = engine
        self.tracer = QueryTracer(engine)
        self.critic = TraceCritic()
        self.discovery_gen = DiscoveryGenerator()
        self.safe_discovery = SafeDiscovery(engine.dag)
        self.self_model = SelfModel(engine.root)
        self.controller = SelfModelController(self.self_model)
    
    def execute_recursive_query(
        self,
        query: str,
        temporal_context: Optional[str] = None,
        max_iterations: int = 5,
        stability_threshold: float = 0.75,
        discovery_gain_threshold: float = 0.15,
        reasoning_mode: str = ReasoningMode.BALANCED.value,
    ) -> Tuple[QueryResult, LoopState]:
        """
        Execute recursive discovery loop until stable or max iterations.
        
        Returns: (final_result, loop_state with full history)
        """
        state = LoopState(
            iteration=0,
            query=query,
            traces=[],
            all_weaknesses=[],
            all_discovery_results=[],
            stability_progression=[],
            discovery_strength_progression=[]
        )
        
        for iteration in range(max_iterations):
            state.iteration = iteration
            
            # ─────────────────────────────────────────
            # STEP 1: Execute query with current parameters
            # ─────────────────────────────────────────
            
            query_params = self.controller.adapt_next_query(query, state.traces[-1] if state.traces else None)
            result, trace = self.tracer.trace_query(
                query,
                temporal_context=temporal_context,
                depth=query_params["depth"],
                reasoning_mode=query_params["reasoning_mode"],
            )
            state.traces.append(trace)
            state.stability_progression.append(result.stability.score)
            
            # ─────────────────────────────────────────
            # STEP 2: Observe and critique the trace
            # ─────────────────────────────────────────
            
            weaknesses = self.critic.critique_trace(trace)
            state.all_weaknesses.extend(weaknesses)
            
            # Check termination: stability threshold met
            if result.stability.score >= stability_threshold:
                state.should_continue = False
                state.termination_reason = f"Stability threshold {stability_threshold} reached (score={result.stability.score:.2f})"
                break
            
            # ─────────────────────────────────────────
            # STEP 3: Generate discovery questions
            # ─────────────────────────────────────────
            
            discovery_questions = self.discovery_gen.generate_from_weaknesses(trace, weaknesses)
            
            if not discovery_questions:
                state.should_continue = False
                state.termination_reason = "No remediable weaknesses identified"
                break
            
            # ─────────────────────────────────────────
            # STEP 4: Execute discovery tasks (safely, locally)
            # ─────────────────────────────────────────
            
            discovery_results = [
                self.safe_discovery.execute_discovery(q, max_facts=20)
                for q in discovery_questions
            ]
            state.all_discovery_results.extend(discovery_results)
            
            # Calculate avg repair strength
            avg_repair = sum(r.repair_strength for r in discovery_results) / len(discovery_results) if discovery_results else 0.0
            state.discovery_strength_progression.append(avg_repair)
            
            # Check termination: insufficient discovery gain
            if avg_repair < discovery_gain_threshold:
                state.should_continue = False
                state.termination_reason = f"Discovery gain {avg_repair:.2f} below threshold {discovery_gain_threshold}"
                break
            
            # ─────────────────────────────────────────
            # STEP 5: Update memory with discovered facts
            # ─────────────────────────────────────────
            
            for result in discovery_results:
                # Add facts as HYPOTHETICAL (speculative, marked low-confidence)
                for fact in result.facts_found:
                    new_id = self.engine.ingest(
                        content=f"[DISCOVERED] {fact.content}",
                        documented_at=fact.documented_at,
                        valid_from=fact.valid_from,
                        valid_until=fact.valid_until,
                        confidence=fact.confidence * 0.7,  # Discount speculative discovery
                        causal_edges=[]  # Will be inferred
                    )
                
                # Add new hypotheses as HYPOTHETICAL edges
                for hypothesis in result.new_hypotheses:
                    # Parse hypothesis and create edge (implementation detail)
                    pass
            
            # ─────────────────────────────────────────
            # STEP 6: Update self-model
            # ─────────────────────────────────────────
            
            self.self_model.observe(trace)
            self.self_model.update_from_discovery(discovery_results)
            
            # ─────────────────────────────────────────
            # STEP 7: Continue to next iteration
            # ─────────────────────────────────────────
            
            print(f"[Recursive Loop] Iteration {iteration+1}: stability={result.stability.score:.2f}, "
                  f"weaknesses={len(weaknesses)}, discovery_gain={avg_repair:.2f}")
        
        # Return final result after all iterations
        final_result = result  # The last result from the loop
        return final_result, state
```

---

## Integration with ReasoningEngine

Add to `llm_kosh/engine/reasoning/__init__.py`:

```python
class ReasoningEngine:
    """Extended with recursive loop capability."""
    
    def __init__(self, root: Path, enable_recursive: bool = False):
        self.root = root
        self.dag = CausalDAG(root)
        self._retrieval = CausalRetrieval(self.dag)
        self._critic = LyapunovCritic(self.dag)
        self._escape = EscapeMechanism(self.dag)
        
        # New: recursive loop (optional, can be expensive)
        if enable_recursive:
            self._recursive_loop = RecursiveReasoningLoop(self)
        else:
            self._recursive_loop = None
    
    def query_recursive(
        self,
        query: str,
        temporal_context: Optional[str] = None,
        depth: int = 3,
        reasoning_mode: str = ReasoningMode.BALANCED.value,
        max_iterations: int = 5,
        stability_threshold: float = 0.75,
    ) -> Tuple[QueryResult, LoopState]:
        """Execute query with full recursive discovery loop."""
        if self._recursive_loop is None:
            raise RuntimeError("Recursive loop not enabled. Initialize with enable_recursive=True")
        
        return self._recursive_loop.execute_recursive_query(
            query,
            temporal_context=temporal_context,
            max_iterations=max_iterations,
            stability_threshold=stability_threshold,
            reasoning_mode=reasoning_mode,
        )
```

---

## Usage Examples

### Example 1: Simple Recursive Query

```python
engine = ReasoningEngine(Path("./cartridge"), enable_recursive=True)

result, loop_state = engine.query_recursive(
    query="What caused the authentication system failure?",
    temporal_context="2025-12-15T00:00:00Z",
    max_iterations=5,
    stability_threshold=0.8,
)

print(f"Query completed in {len(loop_state.traces)} iterations")
print(f"Final stability: {loop_state.stability_progression[-1]:.2f}")
print(f"Discovered {len(loop_state.all_discovery_results)} alternative explanations")

for i, weakness in enumerate(loop_state.all_weaknesses):
    print(f"  Weakness {i+1}: {weakness.description}")
```

### Example 2: Self-Model Introspection

```python
# Query using self-model recommendations
result, loop_state = engine.query_recursive("What is the system status?")

# Inspect what the system learned about itself
self_model = loop_state.controller.self_model
print(f"Learned patterns: {len(self_model.patterns)}")
print(f"Most effective discovery type: {max(self_model.discovery_effectiveness.items(), key=lambda x: x[1])}")

# Next query will use these learned patterns automatically
```

### Example 3: Compare Single-Pass vs. Recursive

```python
# Single-pass (fast but shallow)
result_sp = engine.query("Diagnose the incident")
print(f"Single-pass stability: {result_sp.stability.score:.2f}")

# Recursive (slower but deeper)
result_rec, state = engine.query_recursive("Diagnose the incident", max_iterations=5)
print(f"Recursive stability: {result_rec.stability.score:.2f}")
print(f"Improvement: +{(result_rec.stability.score - result_sp.stability.score):.2f}")
print(f"Cost: {len(state.traces)} query passes")
```

---

## Implementation Sequence

### Sprint 1: Tracing & Critique (Week 1-2)
- [ ] Implement `tracer.py` — QueryTrace + QueryTracer
- [ ] Implement `trace_critic.py` — TraceWeakness + TraceCritic
- [ ] Write tests for trace instrumentation
- [ ] Verify traces capture all needed dimensions

### Sprint 2: Discovery Generation & Safe Execution (Week 3-4)
- [ ] Implement `discovery_generator.py` — DiscoveryQuestion + DiscoveryGenerator
- [ ] Implement `safe_discovery.py` — All 5 discovery strategies
- [ ] Write tests for discovery execution
- [ ] Verify no external side effects

### Sprint 3: Self-Model Building (Week 5-6)
- [ ] Implement `self_model.py` — ReasoningPattern + SelfModel
- [ ] Add pattern learning from traces
- [ ] Implement resonance profile adaptation
- [ ] Test self-model growth over multiple queries

### Sprint 4: Recursive Loop & Integration (Week 7-8)
- [ ] Implement `recursive_loop.py` — RecursiveReasoningLoop
- [ ] Integrate with ReasoningEngine
- [ ] Add loop termination conditions
- [ ] Write benchmarks: stability improvement vs. iteration cost
- [ ] Documentation + examples

---

## Testing Strategy

### Unit Tests

```python
# test_tracer.py
def test_query_trace_captures_stability():
    # Verify trace.stability matches result.stability

def test_trace_captures_escape_strategies():
    # Verify escape methods are recorded

# test_trace_critic.py
def test_temporal_consistency_weakness_detected():
    # Create trace with low consistency, verify weakness reported

def test_contradiction_weakness_detected():
    # Verify contradictions surface as weaknesses

# test_safe_discovery.py
def test_temporal_expansion_finds_adjacent_facts():
    # Verify temporal expansion strategy works

def test_discovery_stays_local():
    # Verify no external API calls made

# test_self_model.py
def test_self_model_learns_from_traces():
    # Verify patterns accumulate

def test_resonance_profile_adaptation():
    # Verify learned profiles are returned

# test_recursive_loop.py
def test_single_iteration_improvement():
    # Verify first iteration improves stability

def test_max_iterations_termination():
    # Verify loop stops at max_iterations

def test_stability_threshold_termination():
    # Verify loop stops when stable
```

### Integration Tests

```python
def test_recursive_loop_vs_single_pass():
    """Compare stability improvement across multiple real queries."""
    queries = [
        "What caused the outage?",
        "What is the system status?",
        "Root cause analysis of incident X"
    ]
    
    for q in queries:
        sp_result = engine.query(q)
        rec_result, _ = engine.query_recursive(q, max_iterations=5)
        
        improvement = rec_result.stability.score - sp_result.stability.score
        print(f"{q}: {improvement:+.2f} stability improvement")
        
        assert improvement >= 0.0  # Recursive should not regress
```

### Benchmarks

```python
def benchmark_loop_cost_vs_benefit():
    """Measure iteration cost vs. stability gain."""
    # Run query_recursive on temporal reasoning corpus
    # Track: iterations, time per iteration, stability improvement
    # Report: ROI (stability gain / time cost)
```

---

## Success Criteria

✅ **Implementation is complete when:**

1. **Tracing works:** Every query execution is captured in full detail
2. **Critique works:** Weaknesses are correctly identified in traces
3. **Discovery works:** Questions are generated and executed safely
4. **Self-model works:** Patterns are learned and applied
5. **Recursion works:** Loop converges to stable, high-quality answers
6. **No external calls:** All discovery happens locally in the graph
7. **Benchmarks show improvement:** Recursive queries >10% more stable than single-pass on test corpus
8. **Termination is robust:** Loop exits cleanly under all conditions

---

## Example Output

```
$ python -c "
engine = ReasoningEngine(Path('.'), enable_recursive=True)
result, state = engine.query_recursive(
    'What caused authentication failures on 2025-12-14?',
    max_iterations=5,
    stability_threshold=0.80
)
"

[Recursive Loop] Iteration 1: stability=0.58, weaknesses=3, discovery_gain=0.42
[Recursive Loop] Iteration 2: stability=0.71, weaknesses=2, discovery_gain=0.55
[Recursive Loop] Iteration 3: stability=0.82, weaknesses=1, discovery_gain=0.38
Stability threshold 0.80 reached (score=0.82)

Final Result:
  Stability: 0.82 (stable)
  Primary cause: OAuth2 migration + timeout bug interaction
  Alternative causes: (2 minor paths surfaced)
  Contradictions resolved: Yes (temporal supersession confirmed)
  Iterations: 3
  Time: 142ms
  Self-model update: +2 new patterns learned
```

---

## Next Phase: External Evidence Integration (v1.2)

Once recursive loop is stable, extend to:
- MCP fetch tools (web search, API calls)
- Safe execution guards (rate limits, validation)
- Evidence citation tracking
- Fact-checking loops

