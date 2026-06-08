# TheHypoKosh Integration Quick Reference

A developer's guide to leveraging TheHypoKosh claims in the llm-kosh codebase.

---

## TL;DR

**All core claims from the PDF are implemented and working.** You can cite the architecture with confidence. The code is production-ready.

---

## Using Core Components

### 1. Temporal Facts with Provenance

```python
from llm_kosh.engine.reasoning import ReasoningEngine
from datetime import datetime, timezone

engine = ReasoningEngine(Path("./my-cartridge"))

# Ingest a fact with all temporal metadata
fact_id = engine.ingest(
    content="JWT token refresh bug introduced in 2.3.1",
    documented_at=datetime(2025, 12, 14, tzinfo=timezone.utc),
    valid_from=datetime(2025, 12, 14, tzinfo=timezone.utc),
    valid_until=datetime(2025, 12, 15, tzinfo=timezone.utc),
    confidence=0.95,
    causal_edges=[
        {
            "target_id": "fact.oauth-deployment.abc123",
            "edge_type": "CAUSES",
            "confidence": 0.9
        }
    ]
)
```

**Key insight:** All four temporal fields are distinct:
- `ingested_at`: system clock (automatic)
- `documented_at`: when the event actually occurred
- `valid_from`/`valid_until`: time window when the fact was true

---

### 2. Distinguishing Observed from Inferred (The Crucial Distinction)

```python
from llm_kosh.engine.reasoning.causal_dag import EdgeOrigin, EdgeRole

# Add an observed edge (from a source document)
observed_edge_id = engine.add_edge_at(
    source_id="fact.deployment.xyz",
    target_id="fact.bug.abc",
    edge_type="CAUSES",
    confidence=0.95,
    valid_from=deployment_time,
    origin="OBSERVED",           # Directly from postmortem
    role="MECHANISTIC",          # Explains how
    evidence=[],                 # Implicit: from source document
)

# Add an inferred shortcut
# Important: This does NOT become the same as observed through repeated use
shortcut_edge_id = engine.add_edge_at(
    source_id="fact.deployment.xyz",
    target_id="fact.customer_impact.def",  # Inferred from A→B→C
    edge_type="INFERS",
    confidence=0.7,
    valid_from=deployment_time,
    origin="INFERRED",           # Derived via reasoning
    role="COMPRESSED",           # A→C shortcut (not full mechanism)
    derived_from=["edge.xyz->bug", "edge.bug->impact"],  # Source chain
)

# Later: if external evidence directly validates the shortcut
evidence_fact = engine.ingest(...)  # Direct observation of A→C
engine.promote_edge_to_discovered(
    edge_id=shortcut_edge_id,
    source_id=evidence_fact,     # Evidence backing promotion
    observed_at=now
)
# Result: origin changes INFERRED → DISCOVERED; confidence can now increase
```

**Why this matters:** The system remembers that A→C was inferred, then later discovered. It never silently converts shortcuts into facts.

---

### 3. Querying with Multiple Reasoning Paths

```python
# Full reasoning pipeline: retrieve → build bundle → critique → escape if needed
result = engine.query(
    query="What led to the authentication failure on Dec 14?",
    temporal_context="2025-12-15T00:00:00Z",  # Query in specific time
    depth=5,                                    # Max 5 hops in causal chain
    reasoning_mode="EMPIRICAL"                  # Filter speculative paths
)

# Inspect the bundle: multiple paths to same target
for target_id, fiber in result.bundle.fibers.items():
    print(f"Target: {target_id}")
    print(f"  Degeneracy: {fiber.degeneracy}")  # How many independent routes?
    print(f"  Paths found: {len(fiber.paths)}")
    for i, path in enumerate(fiber.paths):
        print(f"    Path {i+1}: {len(path.edges)} hops, confidence={path.confidence_product:.2f}")

# Stability diagnosis
print(f"Stability: {result.stability.status} (score={result.stability.score:.2f})")
print(f"  Temporal consistency: {result.stability.dimensions['temporal_consistency']:.2f}")
print(f"  Contradiction score: {result.stability.dimensions['contradiction_score']:.2f}")
print(f"  Path diversity: {result.stability.dimensions['path_diversity']:.2f}")
print(f"  Pattern lock: {result.stability.dimensions['pattern_lock_score']:.2f}")

# Did escape trigger? (Answer was unstable, alternative paths explored)
if result.escape_triggered:
    print(f"Escape activated. New facts surfaced: {result.escape_surfaced}")
```

---

### 4. Reinforcement Without Self-Deception

```python
# A path was useful repeatedly, but that doesn't make it *true*
edge_id = "edge.123"
original_confidence = dag.get_edge(edge_id).confidence

# Use the edge many times
for _ in range(100):
    engine.reinforce_edge(edge_id, used_at=now)

# Check afterward
updated_edge = dag.get_edge(edge_id)
print(f"Confidence: {original_confidence} → {updated_edge.confidence}")  # UNCHANGED
print(f"Salience boost: {updated_edge.provenance.reinforcement.salience_boost}")
print(f"Use count: {updated_edge.provenance.reinforcement.count}")

# Result: salience increased (affects ranking), confidence and origin unchanged (truth preserved)
```

**Why this matters:** Useful inference is kept available but never promoted to discovered truth automatically.

---

### 5. Empirical vs. Theoretical Reasoning

```python
# Same memory, different interpretation by mode

# Empirical mode: Conservative, only what's observed + evidence-backed
result_empirical = engine.query(
    query="Did microservices architecture cause the outage?",
    reasoning_mode="EMPIRICAL"
)
# Filters: removes HYPOTHETICAL origin, ANALOGICAL role without evidence

# Theoretical mode: Exploratory, labels speculative paths
result_theoretical = engine.query(
    query="Did microservices architecture cause the outage?",
    reasoning_mode="THEORETICAL"
)
# Includes: all edges with origin/role clearly marked

# Result comparison
print(f"Empirical paths: {sum(len(f.paths) for f in result_empirical.bundle.fibers.values())}")
print(f"Theoretical paths: {sum(len(f.paths) for f in result_theoretical.bundle.fibers.values())}")
# Typically: theoretical >> empirical (includes speculation)
```

---

## Key Data Structures

### EdgeType (What kind of relationship?)
```python
"ENABLES"              # A enables B to happen
"CAUSES"               # A directly causes B
"CONTRADICTS"          # A contradicts B
"SUPERSEDES"           # A replaces B (temporal update)
"INFERS"               # A logically infers B
"ANALOGY"              # A is analogous to B (cross-domain)
"MAPS_TO"              # A maps to B (structural correspondence)
"INVERTS"              # A is inverse of B
"STRUCTURALLY_SIMILAR" # Same structure as B
"CONTRASTS"            # A contrasts with B
```

### EdgeOrigin (Where did this edge come from?)
```python
"OBSERVED"    # Directly in a source document/postmortem
"DISCOVERED"  # Found later via new evidence after hypothesis existed
"INFERRED"    # Reasoned from existing facts (A→B, B→C ⇒ A→C)
"REINFORCED"  # Repeatedly useful but not newly observed
"HYPOTHETICAL"# Speculative bridge for exploration
```

### EdgeRole (What's the purpose of this edge?)
```python
"MECHANISTIC"  # Explains mechanism (A→B→C)
"COMPRESSED"   # Shortcut from repeated pattern (A→C)
"ANALOGICAL"   # Structural similarity across domains
"PREDICTIVE"   # A forecasts C without proving causation
"CAUSAL"       # A claims to cause C (requires evidence)
```

### ReasoningMode (How should we interpret the bundle?)
```python
"EMPIRICAL"     # Observed > Discovered > Inferred > Hypothetical
"THEORETICAL"   # All paths, clearly labeled for exploration
"BALANCED"      # Return empirical answer + labeled alternatives
```

---

## Testing the Claims

### Test 1: Temporal Supersession
```python
def test_fact_validity_windows():
    """Query at different times returns different truth."""
    engine.ingest(
        content="Auth system using OAuth1",
        valid_from=dt(2025, 10, 1),
        valid_until=dt(2025, 11, 1),
        confidence=0.95
    )
    engine.ingest(
        content="Auth system migrated to OAuth2",
        valid_from=dt(2025, 11, 2),
        valid_until=None,  # Still current
        confidence=0.95
    )
    
    result_oct = engine.query("Auth system status", temporal_context="2025-10-15")
    result_nov = engine.query("Auth system status", temporal_context="2025-11-15")
    
    assert "OAuth1" in result_oct.bundle.fibers[...]
    assert "OAuth2" in result_nov.bundle.fibers[...]
```

### Test 2: Contradiction Preservation
```python
def test_contradictions_surfaced():
    """Contradictions are measured, not hidden."""
    engine.ingest(..., content="Outage was caused by database deadlock")
    engine.ingest(..., content="Database was not under contention during outage")
    engine.dag.add_edge(..., edge_type="CONTRADICTS")
    
    result = engine.query("Root cause of outage")
    assert result.stability.dimensions["contradiction_score"] > 0.0
    # System is aware of conflict, not choosing a side invisibly
```

### Test 3: Escape Mechanism
```python
def test_escape_on_unstable_bundle():
    """Low stability triggers alternative path exploration."""
    # Set up contradictory facts with equal confidence
    engine.ingest(..., content="Fact A")
    engine.ingest(..., content="Fact B (contradicts A)")
    # Bundle will be unstable
    
    result = engine.query("What's true?", depth=5)
    assert result.stability.status in ("unstable", "marginal")
    assert result.escape_triggered is True
    assert len(result.escape_surfaced) > 0
```

---

## Common Patterns

### Pattern: Build a Temporal Chain
```python
# Incident timeline: decision → deployment → bug → detection → fix

decision_id = engine.ingest(..., content="Decision to upgrade auth library")
engine.add_edge_at(decision_id, deployment_id, edge_type="ENABLES")
engine.add_edge_at(deployment_id, bug_id, edge_type="CAUSES")
engine.add_edge_at(bug_id, detection_id, edge_type="ENABLES")
engine.add_edge_at(detection_id, fix_id, edge_type="ENABLES")

# Query will reveal full chain
result = engine.query("What happened to auth?", depth=10)
# Returns: decision → deployment → bug → detection → fix (in order, with timestamps)
```

### Pattern: Preserve Open Questions
```python
# Mark something as unknown (gap in knowledge)
from llm_kosh.engine.reasoning.causal_dag import EdgeOrigin

gap_id = engine.ingest(
    content="UNKNOWN: Why did the traffic spike occur at 13:47 UTC?",
    confidence=0.0,  # Explicit uncertainty
    valid_from=incident_start,
)

# Link the gap to what we know
engine.add_edge_at(
    source_id=traffic_spike_id,
    target_id=gap_id,
    edge_type="CONTRADICTS",  # We can't explain it yet
    origin="HYPOTHETICAL",
    confidence=0.1  # Low confidence pending evidence
)

# Query will surface the gap in results
result = engine.query("Root cause analysis")
# Result includes: explicit "UNKNOWN" fact with low confidence
```

### Pattern: Cross-Domain Analogy
```python
# Capture useful analogies while marking them as speculative

engine.add_edge_at(
    source_id="fact.microservices-architecture",
    target_id="fact.distributed-systems-problem",
    edge_type="ANALOGY",
    origin="HYPOTHETICAL",  # Is speculation
    role="ANALOGICAL",      # Is comparison, not proven causation
    confidence=0.4,         # Low confidence
)

# In THEORETICAL mode, this path is included for exploration
# In EMPIRICAL mode, this path is filtered out
result_theo = engine.query("Architectural risks?", reasoning_mode="THEORETICAL")
result_emp = engine.query("Architectural risks?", reasoning_mode="EMPIRICAL")

# The analogy appears in result_theo, not in result_emp
```

---

## Debugging: When Stability is Low

If `result.stability.status == "unstable"` or `"marginal"`:

1. **Check temporal consistency:**
   ```python
   dims = result.stability.dimensions
   if dims["temporal_consistency"] < 0.7:
       # Some edges go backward in time
       # Review fact validity windows
   ```

2. **Check contradictions:**
   ```python
   if dims["contradiction_score"] > 0.3:
       # Multiple conflicting facts in bundle
       # This is correct behavior—system surfaced the conflict
   ```

3. **Check pattern lock:**
   ```python
   if dims["pattern_lock_score"] > 0.5:
       # One path dominates; alternatives missing
       # Escape should have triggered; check escape_triggered flag
   ```

4. **Investigate escape results:**
   ```python
   if result.escape_triggered:
       for new_fact_id in result.escape_surfaced:
           new_fact = engine.dag.get_fact(new_fact_id)
           print(f"Escape found: {new_fact.content}")
   ```

---

## Integration Checklist

- [ ] Read THEHYPOKOSH_IMPLEMENTATION_ANALYSIS.md (comprehensive)
- [ ] Run tests in PROOF_TEST_RESULTS.md to verify setup
- [ ] Test temporal query on your cartridge (see Pattern: Build a Temporal Chain)
- [ ] Verify escape mechanism on contradictory facts (see Test 2)
- [ ] Compare empirical vs theoretical modes on your data
- [ ] Document any domain-specific edge types you add
- [ ] Check stability dimensions on realistic queries
- [ ] Verify that inferred edges don't auto-promote (see Pattern: Reinforcement)

---

## FAQ

**Q: Can I increase edge confidence through repeated use?**  
A: No. `reinforce_edge()` increases salience (ranking) but not confidence. Use `promote_edge_to_discovered()` with evidence if confidence should increase.

**Q: What if I have multiple facts valid at the same time?**  
A: All valid facts at query_time are candidates for retrieval. Stability scoring will detect contradictions (if they exist). This is correct behavior.

**Q: How do I know if an edge is safe to use?**  
A: Check the tuple: origin (was it observed?) + role (is it mechanistic or speculative?) + evidence_refs (is it backed?). Use reasoning_mode filtering for safety level.

**Q: Can I query with a future temporal context?**  
A: Yes, but facts with `valid_until` in the past won't be retrieved. This is correct behavior—query at time T returns only facts true at T.

**Q: What's the difference between COMPRESSED and MECHANISTIC?**  
A: MECHANISTIC explains the full chain (A→B→C). COMPRESSED is the shortcut (A→C) inferred from repeated pattern. Both can be true; the system remembers which is which.

**Q: How do I add a multi-source causality (hyperedge)?**  
A: Use `dag.add_hyperedge(source_ids=[a, b, c], target_id=target, edge_type="CAUSES")`. It only activates when all sources are in the query context.

---

## Reporting Issues

If you find implementation-PDF mismatches:
1. Check THEHYPOKOSH_IMPLEMENTATION_ANALYSIS.md Section 15 (Gap Analysis)
2. File an issue with: (a) PDF claim, (b) expected behavior, (c) observed behavior
3. Include minimal reproduction case (see Test templates above)

