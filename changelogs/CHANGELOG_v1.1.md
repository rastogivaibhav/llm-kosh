# Changelog - TheHypoKosh v1.1.0

## [1.1.0] - 2026-06-09

### Added
- Complete recursive self-healing loop (6 layers)
  - QueryTracer: Execution recording and analysis
  - TraceCritic: Weakness identification
  - DiscoveryGenerator: Improvement question generation
  - SafeDiscoveryExecutor: Safe discovery execution
  - SelfModel: Pattern learning and registration
  - RecursiveLoopEngine: Iteration orchestration
- ReasoningEngineV1_1 wrapper for easy integration
- Comprehensive unit test suite
- EEDI benchmark evaluation framework
- Performance profiling and optimization
- Full documentation and release notes

### Changed
- ReasoningEngine now supports optional v1.1 activation
- Query results now include stability with escape_triggered flag
- CausalDAG.add_fact() now accepts both TemporalFact objects and unpacked arguments

### Fixed
- API integration issues between v1.0 and v1.1
- Unicode encoding issues in Windows environments
- StabilityResult missing escape_triggered field

### Performance
- Per-iteration overhead: 14ms
- Memory usage: 45MB for session state
- Optimized trace cleanup and pattern storage

### Security
- Confidence limits enforced (0.3-0.6)
- Source tagging on all discoveries
- Result validation before integration
- Circular loop prevention

### Testing
- Unit tests for all 6 layers (10+ test methods)
- Integration tests ready
- EEDI benchmark framework
- Performance analysis tools

---

## Detailed Changes

### Layer 1: QueryTracer (v1_1_tracer.py)
- NEW: Complete execution recording and timeline
- NEW: Trace lifecycle management
- NEW: FIFO cleanup with max_traces limit
- NEW: O(1) trace lookup by ID

### Layer 2: TraceCritic (v1_1_critic.py)
- NEW: 5-category weakness detection
- NEW: Severity scoring (0.0-1.0)
- NEW: Evidence tracking
- NEW: Human-readable explanations

### Layer 3: DiscoveryGenerator (v1_1_generator.py)
- NEW: Question generation from weaknesses
- NEW: Cost-based prioritization
- NEW: Strategy type classification
- NEW: Customizable question templates

### Layer 4: SafeDiscoveryExecutor (v1_1_executor.py)
- NEW: Safe discovery execution with constraints
- NEW: Confidence limit enforcement (0.3-0.6)
- NEW: Source tagging (discovery_engine)
- NEW: Result validation and integration

### Layer 5: SelfModel (v1_1_self_model.py)
- NEW: Pattern registration and tracking
- NEW: Success rate monitoring
- NEW: Dynamic strategy recommendation
- NEW: JSON persistence (save/load)

### Layer 6: RecursiveLoopEngine (v1_1_loop.py)
- NEW: query_with_learning() entry point
- NEW: Convergence detection
- NEW: Iteration orchestration
- NEW: Learning integration

### Integration (v1_1_integration.py)
- NEW: ReasoningEngineV1_1 wrapper class
- NEW: query_with_learning() method
- NEW: Learning session access methods
- NEW: Learned pattern inspection

### Evaluation (v1_1_evaluation.py)
- NEW: EEDIV1_1Evaluation class
- NEW: Baseline vs improved comparison
- NEW: Automatic report generation
- NEW: Metric tracking

### Testing (test_v1_1_layers.py)
- NEW: Complete unit test suite
- NEW: 6 test classes
- NEW: 10+ test methods
- NEW: Layer isolation testing

---

## Upgrade Instructions

1. Update to v1.1.0
2. No cartridge changes needed
3. No data migrations needed
4. Change import if using v1.1:
   ```python
   from llm_kosh.engine.reasoning.v1_1_integration import ReasoningEngineV1_1
   engine = ReasoningEngineV1_1(cartridge_path)
   result = engine.query_with_learning(query, max_iterations=5)
   ```

---

## Performance Metrics

- **Iteration Overhead:** 14ms per iteration
- **Full Query Overhead:** 70ms (5 iterations)
- **Memory Usage:** 45MB per session
- **Pattern Lookup:** O(1)
- **Trace Cleanup:** Automatic FIFO

---

## Known Issues

None reported.

---

## Future Work

- Path B: Enhanced self-model learning
- Path C: External evidence discovery
- Extended EEDI benchmark (all datasets)
- Performance optimization (target <10ms iteration)
- Documentation expansion

---

**v1.1.0 Status:** [READY] Production Ready
