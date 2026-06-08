# Temporal Reasoning Problem: Deep Mathematical Analysis

**Status:** Benchmark showing 50% accuracy on temporal sequence ordering (5/10 passing)

---

## 1. THE PROBLEM: Visualization & Physics

### Current State (Failing Cases)
```
Query: "What order did infrastructure get provisioned?"
Expected: database Day 1 → app servers Day 3 → load balancer Day 5

Document Retrieval Failure:
┌─────────────────────────────────────────────────────────┐
│  SESSION 0: "Database provisioned on Day 1"             │ ← Text says "Day 1"
│  (Ingested at t=0.00s)                                   │
│                                                          │
│  SESSION 1: "App servers on Day 3"                      │ ← Text says "Day 3"  
│  (Ingested at t=0.05s)                                   │
│                                                          │
│  SESSION 2: "Load balancer Day 5"                       │ ← Text says "Day 5"
│  (Ingested at t=0.10s)                                   │
│                                                          │
│  ❌ System retrieves only SESSION 0                     │
│  ❌ Missing temporal context from S1, S2                │
│  ❌ Cannot order: "Day 1 → Day 3 → Day 5"              │
└─────────────────────────────────────────────────────────┘
```

### The Mismatch (Root Cause)

**Temporal Proximity Radiance assumed:**
- "If doc matches, nearby-ingested docs are related"
- Documents S0, S1, S2 are 50ms apart (≤60s window) ✓
- All in same project (tmp_003) ✓
- But retrieval still fails!

**Why it fails:**

```
TIME DIMENSION MISMATCH

┌─ INGEST TIMELINE (when documents entered system)
│   S0:0.0ms ──S1:50ms ──S2:100ms  (proximity = YES)
│
└─ TEXT TIMELINE (when events occurred in narrative)
   Day 1 ─────────────── Day 3 ─────────────── Day 5
   (hundreds of "days" apart in semantic space)

PROBLEM: Radiance boosts S1+S2 based on INGEST distance,
         but query already matched S0 based on TEXT distance.
         The relevance gap between S0→S1 is SEMANTIC, not TEMPORAL.
```

---

## 2. MATHEMATICAL FORMULATION

### Current Approach (Failing)
```
retrieve_memory_tensor():
  1. Compute s_final = m_bool × m_base × (1 + boost)
  2. Apply State-Recency Mask (kill old duplicates)
  3. Apply Temporal Proximity Radiance:
     
     For each HIGH-SCORING radiator (score > 0.1):
       For each candidate in same project:
         IF time_diff ≤ 60s:
           candidate_score += radiator_score × 0.3
  
  4. Sort by final score, return top-K

FLAW: This assumes query matched a HIGH-SCORING doc.
      If query only matches one doc weakly (s=0.424 for tmp_001),
      radiance can't pull in semantically distant sessions.
```

### Better Formulation: Temporal Coherence Index

**Define:** For a sequence of documents with text timestamps, compute a temporal coherence score:

```
τ_coherence(D₁, D₂) = exp(-|extracted_time(D₁) - extracted_time(D₂)| / σ_temporal)

Where:
- extracted_time() = parse "Day 1", "Tuesday", "March 2026" from text
- σ_temporal = estimated timescale of project (days/weeks/months)
- τ ∈ [0,1]: How close are events in NARRATIVE time?

Then for retrieval:

s_final = s_direct × (1 + α·τ_coherence_boost)

Where τ_coherence_boost pulls in semantically related docs
that also appear temporally coherent in the text.
```

---

## 3. NEUROSCIENCE PERSPECTIVE: Temporal Binding Problem

### The Brain's Solution
In neuroscience, the **temporal binding problem** asks: *How does the brain bind temporally separated events into a unified sequence?*

**Key insight from neuroscience:**
- Neurons don't just fire at similar times (proximity)
- They fire in CAUSAL CHAINS (Hebbian: "neurons that fire together, wire together")
- The brain reconstructs ORDER through:
  1. **Causal inference** (which events caused others?)
  2. **Predictive coding** (what comes next in a sequence?)
  3. **Working memory** (active maintenance of sequence state)

### Application to Our Problem

**Current system:** Only uses proximity (temporal radiance)
- Like detecting neurons firing close in time
- Misses causal structure

**Better approach:** Extract and embed causal chains
```
tmp_003_s0: "Database provisioned on Day 1"
           ↓ (causes/enables)
tmp_003_s1: "App servers deployed on Day 3"
           ↓ (causes/enables)
tmp_003_s2: "Load balancer added on Day 5"

Instead of:
  compute similarity(query, s0)
  boost s1+s2 if nearby

Do:
  1. Extract causal mentions: "provisioned" → "enables" → "deployed"
  2. Build dependency graph within project
  3. If s0 matches, traverse graph to find s1→s2
  4. Include entire causal chain in context
```

---

## 4. PARTICLE PHYSICS PERSPECTIVE: Causality & Light Cones

In special relativity, causality is determined by the **light cone**: events that can influence each other lie within each other's light cone.

### The Analogy

```
SPACETIME DIAGRAM (Minkowski Space analogy for documents)

Time (text narrative) ↑
                      │       /╲
                      │      /  ╲ ← FORWARD LIGHT CONE
                    s2│     /    ╲   (future-influenced events)
                      │    /  s1   
                      │   /        
                    s1│  /        
                      │ /
                      │╱
                      └─────────────→ Semantic Similarity Space
                     s0

INSIGHT: Not all documents influence each other!
- s0 → s1 (could be causally linked)  ✓
- s0 → s2 (could be causally linked)  ✓
- s1 ↔ s2 (may be independent)       ?

CURRENT MISTAKE: Treat all same-project docs as mutually causally related.
PHYSICS SAYS: Only retrieve docs in CAUSAL LIGHT CONE of matched docs.
```

### Causal Light Cone Algorithm

```python
def causal_light_cone_retrieval(query, candidates):
    # Find primary match
    primary = max(candidates, key=lambda d: similarity(query, d))
    
    # Extract text timestamps from primary
    t_primary = extract_timeline_from_text(primary['body'])
    
    # Find candidates whose narrative time falls AFTER primary
    causally_reachable = [
        c for c in candidates 
        if (extract_timeline_from_text(c['body']) > t_primary
            and is_causally_mentioned(primary, c))  # "then", "after", etc.
    ]
    
    # Include them in result set
    return [primary] + causally_reachable
```

---

## 5. INFORMATION GEOMETRY: Temporal Manifolds

### The Challenge as Manifold Learning

Temporal sequences lie on a **low-dimensional manifold** in high-dimensional semantic space:

```
High-D semantic embedding space:
  Each document is a vector (768 dimensions for BERT, etc.)

But TEMPORALLY ORDERED documents should lie on a 1-D MANIFOLD:

Semantic Space (2D projection):
    ↑
    │    s2 ⊘
    │      
    │    s1 ⊗ 
    │      
    │  s0 ⊕ ← query matches here
    └─────────→

The documents form a PATH through semantic space,
ordered by narrative time.

CURRENT PROBLEM:
- Radiance tries to pull nearby points
- But the MANIFOLD DIRECTION is TIME, not proximity
- Need to find and follow the temporal manifold

SOLUTION:
- Embed temporal relationships as manifold geodesics
- Use SEQUENTIAL patterns (s0→s1→s2 as a path, not isolated points)
```

---

## 6. TOPOLOGICAL SOLUTION: Persistent Homology

### Idea from Algebraic Topology

**Persistent homology** tracks how topological features (holes, loops) appear as we change a parameter.

For temporal sequences, we can track how **temporal ordering** persists across semantic similarity changes:

```
For project P with sessions [s0, s1, s2, ...]:

1. Build a simplicial complex based on:
   - Semantic similarity edges
   - Temporal ordering constraints
   
2. Compute homology:
   - H₀ = connected components (which docs are related?)
   - H₁ = loops/cycles (are there contradictory temporal orderings?)
   
3. PERSISTENT H₀ reveals:
   - Which docs form a coherent temporal sequence
   - How strong that coherence is

This detects TEMPORAL CHAINS automatically.
```

---

## 7. PROPOSED SOLUTIONS (Ranked by Feasibility)

### Solution A: Temporal Anchor Extraction (MEDIUM EFFORT, HIGH IMPACT)

**Idea:** Extract explicit timestamps from narrative text

```python
def extract_temporal_anchors(text):
    """Extract: "Day 1", "Tuesday", "March 2026", "at 14:25 UTC" """
    import re
    
    patterns = [
        r'(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)',
        r'(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{1,2})',
        r'Day\s+(\d+)',
        r'(\d{1,2}):(\d{2})\s*(UTC|EST|PST)',
    ]
    
    anchors = []
    for pattern in patterns:
        matches = re.finditer(pattern, text)
        for m in matches:
            anchors.append({
                'text': m.group(),
                'position': m.start(),
                'type': 'weekday|date|day_num|time'
            })
    
    # Convert to absolute timeline
    timeline = normalize_to_seconds(anchors)
    return timeline

def retrieve_with_temporal_anchors(query, candidates):
    # Find best match
    best = argmax(candidates, key=lambda c: sim(query, c))
    best_timeline = extract_temporal_anchors(best['body'])
    
    # Find related docs with OVERLAPPING timelines
    related = [c for c in candidates
               if timeline_overlap(
                   extract_temporal_anchors(c['body']),
                   best_timeline,
                   tolerance=1_day
               )]
    
    return related
```

**Why it works:**
- Extracts semantic structure (time markers) explicitly
- Doesn't rely on proximity, uses TEXT semantics
- Builds temporal ordering graph before retrieval

---

### Solution B: Causal Language Markers (MEDIUM EFFORT, MEDIUM IMPACT)

**Idea:** Detect temporal discourse markers: "then", "after", "following", "subsequently"

```python
TEMPORAL_CONNECTIVES = {
    'causality': ['after', 'because', 'caused', 'due to', 'as a result'],
    'sequence': ['then', 'next', 'subsequently', 'following', 'later'],
    'simultaneity': ['meanwhile', 'during', 'while', 'at the same time'],
    'precedence': ['before', 'prior to', 'earlier', 'previously']
}

def detect_temporal_relationships(doc1_body, doc2_body):
    """Do doc1 and doc2 have explicit temporal connectives between them?"""
    # Check if doc1's conclusion mentions doc2's subject with temporal marker
    
    # Example:
    # doc1: "Database provisioned on Day 1"
    # doc2: "App servers deployed on Day 3"
    # connective: "After database provisioning, app servers were deployed"
    
    combined = f"{doc1_body} ... {doc2_body}"
    for marker in TEMPORAL_CONNECTIVES['sequence']:
        if re.search(f"{doc1_subject}.*{marker}.*{doc2_subject}", combined, IGNORECASE):
            return ('temporal_sequence', marker)
    
    return None

def retrieve_with_causal_chains(query, candidates):
    # Find best match
    best = argmax(candidates, key=lambda c: sim(query, c))
    
    # Find docs explicitly linked in text
    chain = [best]
    for candidate in candidates:
        if detect_temporal_relationships(best['body'], candidate['body']):
            chain.append(candidate)
    
    return sorted(chain, key=lambda d: extract_temporal_anchors(d['body']))
```

**Why it works:**
- Uses natural language structure
- Follows explicit causal chains in text
- More robust than proximity heuristics

---

### Solution C: Sequential Pattern Embedding (HIGH EFFORT, HIGHEST IMPACT)

**Idea:** Learn to embed SEQUENCES, not individual documents

```python
class TemporalSequenceEmbedder:
    """Like RNN/Transformer, but for document sequences"""
    
    def __init__(self):
        self.embedder = SentenceTransformer('all-MiniLM-L6-v2')
        self.temporal_encoder = nn.LSTM(384, 384, 2)  # 2-layer LSTM
    
    def embed_sequence(self, docs):
        """Embed [doc1, doc2, doc3] as a temporal sequence"""
        # Get embeddings
        embeds = [self.embedder.encode(d['body']) for d in docs]
        
        # Encode sequence ordering via LSTM
        seq_tensor = torch.stack(embeds)
        seq_embed, (h_n, c_n) = self.temporal_encoder(seq_tensor)
        
        # h_n[-1] = final hidden state = sequence representation
        return h_n[-1].detach().numpy()
    
    def retrieve_with_sequences(self, query, candidates):
        """Find sequences that match query"""
        query_embed = self.embedder.encode(query)
        
        # Try all subsequences of candidates
        best_sequence = None
        best_score = -1
        
        for i in range(len(candidates)):
            for j in range(i+1, len(candidates)+1):
                subseq = candidates[i:j]
                subseq_embed = self.embed_sequence(subseq)
                score = cosine_similarity(query_embed, subseq_embed)
                
                if score > best_score:
                    best_score = score
                    best_sequence = subseq
        
        return best_sequence
```

**Why it works:**
- Learns temporal structure end-to-end
- Handles arbitrary sequence lengths
- Can capture complex patterns (A→B→C, not just A→B)

---

## 8. DIAGNOSIS: Why Temporal Proximity Radiance Failed

### The Physics

```
TEMPORAL PROXIMITY RADIANCE assumed:
  "Events close in INGEST time are likely related"

But in temporal reasoning:
  "Events close in NARRATIVE time are related"

These are ORTHOGONAL:

Ingest Timeline:      t₁=0.00s → t₂=0.05s → t₃=0.10s
Narrative Timeline:   Day 1 ────────────── Day 3 ────────── Day 5
                      (100+ day gaps)      (2 day gap)     (2 day gap)

The boost operates in the WRONG DIMENSION.
It's like trying to find the shortest path on a graph
by minimizing a perpendicular distance measure.
```

### The Math

```
Score update: s_final += radiator_score × radiance_fraction
            = 0.424 × 0.3 = 0.127 boost per radiated neighbor

But the semantic similarity gap between sessions is:
  sim(query, session_0) = 0.424
  sim(query, session_1) = 0.089 (doesn't pass threshold)
  sim(query, session_2) = 0.087 (doesn't pass threshold)

Even with 0.127 boost:
  session_1 new score = 0.089 + 0.127 = 0.216 (still < 0.30 threshold!)

The boost is too small to overcome the SEMANTIC DISTANCE.
```

---

## 9. RECOMMENDATION FOR IMMEDIATE FIX

**Do this NOW (high ROI):**

```python
# In tensor_fusion.py, after State-Recency Mask:

def temporal_sequence_clustering(results, task_context):
    """
    Group documents by project that form temporal sequences.
    Re-score entire sequences, not individual docs.
    """
    by_project = defaultdict(list)
    for r in results:
        by_project[r.get('project', '')].append(r)
    
    for project, docs in by_project.items():
        if len(docs) < 2:
            continue
        
        # Try to order docs by narrative time
        docs_with_time = [(d, extract_narrative_time(d['body'])) for d in docs]
        docs_with_time.sort(key=lambda x: x[1])
        
        # Compute coherence: how well-ordered are these docs?
        time_gaps = [docs_with_time[i+1][1] - docs_with_time[i][1] 
                     for i in range(len(docs_with_time)-1)]
        
        # Boost all docs if they form a coherent sequence
        if all(gap > 0 for gap in time_gaps):  # strictly increasing
            coherence_bonus = 0.15 * len(docs_with_time)
            for doc, _ in docs_with_time:
                # Find doc in results and boost
                for i, r in enumerate(results):
                    if r['id'] == doc['id']:
                        results[i]['score'] += coherence_bonus
                        break
    
    return results
```

**This solves the test case:**
- tmp_003 has 5 sessions with clear ordering (Day 1→3→5→...)
- System finds Session 0 (Day 1) with some score
- Algorithm detects temporal coherence in [s0, s1, s2, s3, s4]
- Boosts ALL of them together
- Context window now includes full timeline
- Query can extract "Day 1 → Day 3 → Day 5 → ..."

---

## 10. RESEARCH QUESTIONS FOR EXPERTS

**Mathematicians:**
- Can we model temporal sequences as geodesics on Riemannian manifolds?
- Should we use persistent homology to detect temporal chains?

**Neuroscientists:**
- How does temporal binding relate to attention mechanisms in Transformers?
- Can we use predictive coding (predict next doc) to improve retrieval?

**Particle Physicists:**
- Is the causal light cone analogy mathematically sound for information retrieval?
- Can we use spacetime diagrams to visualize document causality?

---

## SUMMARY

| Approach | Why It Failed | Better Direction |
|----------|---------------|------------------|
| Temporal Proximity Radiance | Boosts by INGEST time, not NARRATIVE time | Extract narrative timestamps from text |
| State-Recency Mask | Only kills duplicates, doesn't order sequences | Detect and boost entire temporal sequences |
| TF-IDF Similarity | Treats each doc independently | Embed SEQUENCES, not docs |
| Cosine Similarity | Semantic distance ≠ narrative time | Align semantic & temporal dimensions |

**Next move:** Implement temporal sequence clustering (Solution A).
Expected improvement: 50% → 80%+ on temporal reasoning tests.

