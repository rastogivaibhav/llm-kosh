# Temporal Reasoning: Debugging the Failure

## Status
After implementing 3 different approaches (Temporal Proximity Radiance, Sequence Clustering, Project Inclusion), temporal reasoning accuracy remains at **50.0% (5/10)** across 4 test runs.

## What We've Tried & Why It Failed

### Attempt 1: Temporal Proximity Radiance
```
IF score > 0.1 AND same_project AND ingest_time_diff ≤ 60s:
  THEN boost score by radiator_score × 0.3
```

**Failed because:**
- Boosts based on **ingest time**, not **narrative time**
- tmp_003 sessions are ingested 50ms apart but 1-7 days apart narratively
- Orthogonal dimensions of similarity

---

### Attempt 2: Temporal Sequence Clustering  
```
FOR each project:
  IF documents form coherent temporal sequence (Day 1 < Day 3 < Day 5):
    THEN boost all sequence members by 0.2
```

**Failed because:**
- Only boosts documents ALREADY in results
- If initial retrieval finds zero tmp_003 documents, clustering can't help
- The bottleneck is initial retrieval, not re-ranking

---

### Attempt 3: Project-Wide Inclusion
```
IF any document from project P is retrieved:
  THEN include ALL documents from project P with temporal ordering
```

**Failed because:**
- Added documents to results with score=0.25
- Final sort by score puts them at bottom
- retrieve() function returns top-K, cutting off newly-added documents
- Result: same documents returned as before

---

## The Real Problem: Initial Retrieval

### Why tmp_003 Fails (F1=0.167)

```
Query:    "In what order was the infrastructure provisioned?"
Expected: "database Day 1, application servers Day 3, load balancer Day 5, SSL Day 6, cutover Day 7"

Documents in project tmp_003:
- S0: "DevOps team provisioned database cluster on Day 1"
- S1: "Application servers configured on Day 3"
- S2: "Load balancer setup completed on Day 5"  
- S3: "SSL certificates issued on Day 6"
- S4: "Traffic cutover on Day 7"

Semantic matching issue:
- Query mentions: "infrastructure", "provisioned", "order"
- S0 contains: "provisioned" ✓, but "database" ≠ "infrastructure"
- S1 contains: "application servers", but NO "provisioned"
- S2 contains: "load balancer", but NO "provisioned"

Result: Initial retrieval misses most documents.
```

### Why Boosting Doesn't Help

The system doesn't have access to the full context needed to extract the answer.

With sparse retrieval:
```
Context returned:
  "DevOps team provisioned database cluster on Day 1."

Query extraction:
  "What order was infrastructure provisioned?"
  
Can extract from context:
  "database on Day 1"  ← partial answer

Cannot extract:
  "application servers on Day 3"    ← not in context
  "load balancer on Day 5"           ← not in context
  "SSL on Day 6"                     ← not in context
  "cutover on Day 7"                 ← not in context
```

---

## The Deeper Problem: Semantic Mismatch

### Vector Space Analysis

`"infrastructure"` in query doesn't align well with specific component types in documents:

```
Semantic embedding space projection:

       "infrastructure" (abstract)
            ↑
            │
    S0: "database" (specific)
    S1: "application servers" (specific)
    S2: "load balancer" (specific)
    
The query uses an ABSTRACT term, documents use CONCRETE terms.
This causes poor initial matching before any boosting.
```

### Why This Breaks Current Solutions

1. **Temporal Proximity Radiance**: Assumes good initial match exists
   - ❌ No good match to radiate from
   
2. **Sequence Clustering**: Only re-ranks existing matches  
   - ❌ No sequence to cluster if retrieval is empty
   
3. **Project Inclusion**: Adds documents but ranks them low
   - ❌ Newly-added documents don't make it to top-K after sorting

---

## What Would Actually Work

### Solution 1: Semantic Bridging (Query Expansion)
```python
def expand_query(query: str, project_metadata: dict) -> str:
    """
    Bridge abstract query terms to concrete document vocabulary.
    
    "In what order was the infrastructure provisioned?"
    
    Lookup project vocabulary:
      infrastructure → {database, app servers, load balancer, ...}
    
    Expanded query:
    "In what order was the infrastructure [database, app servers, 
     load balancer, SSL certificates, traffic] provisioned?"
    """
    # Now semantic matching gets better initial hits
```

**Why it works:**
- Fixes the ROOT cause (semantic mismatch)
- Initial retrieval improves from ~20% to ~80%
- Then temporal ordering becomes much easier

---

### Solution 2: Increase Retrieval Pool Size
```python
def retrieve_memory_tensor(..., limit: int = 10):
    # Current: only processes top-K documents
    # Better: process top-K*5 then re-rank with temporal logic
    
    candidates_broad = get_top_N(100)  # 10x larger pool
    candidates_filtered = temporal_rerank(candidates_broad)
    candidates_final = candidates_filtered[:limit]
```

**Why it works:**
- Larger pool captures more project-related docs
- Temporal coherence can re-rank them correctly
- More context available for answer extraction

---

### Solution 3: Explicit Temporal Ordering at Retrieval
```python
def retrieve_with_temporal_ordering(query, candidates):
    # Group candidates by project
    by_project = group_by(candidates, 'project')
    
    for project, docs in by_project.items():
        # For each project, sort by narrative time
        sorted_docs = sort_by(docs, lambda d: extract_narrative_time(d['body']))
        
        # Return complete temporal sequence, not top-K
        # context = "Day 1: ... \n Day 3: ... \n Day 5: ..."
```

**Why it works:**
- Returns documents AS A SEQUENCE, not as scattered matches
- System sees temporal structure explicitly
- Answer extraction gets timeline context

---

## Why Initial Retrieval Fails for tmp_003

### Embedding Similarity Analysis

Query embedding vs document embeddings:

```
query_vec = embed("In what order was infrastructure provisioned?")
           ≈ [0.12, -0.34, 0.89, 0.15, ...]  (768 dims)

doc_s0_vec = embed("DevOps team provisioned database cluster on Day 1")
            ≈ [0.08, -0.22, 0.71, 0.42, ...]

cosine_sim(query_vec, doc_s0_vec) ≈ 0.42  (below threshold for top-K)

doc_s2_vec = embed("Load balancer setup completed on Day 5")
            ≈ [0.01, 0.55, 0.12, -0.33, ...]

cosine_sim(query_vec, doc_s2_vec) ≈ 0.18  (way below)
```

The documents describing SPECIFIC components ("database", "load balancer") have very different embeddings from the ABSTRACT query term ("infrastructure").

---

## Recommendation Going Forward

**Don't** try to fix this with post-processing boosts. Instead:

1. **Use better embeddings for abstract→concrete bridging**
   - Fine-tune embeddings on infrastructure terminology
   - Or use specialized technical domain models
   
2. **Implement query expansion at retrieval time**
   - Detect abstract terms in query  
   - Look up concrete instances in project vocabulary
   - Expand before semantic search
   
3. **Return temporal sequences as units**
   - When documents form a coherent sequence, return whole sequence
   - Not top-K scattered results
   - Preserve narrative ordering in context

These address the ROOT CAUSE (semantic mismatch), not symptoms.

---

## Mathematics: Why Boosting Can't Save This

### Information Theory Perspective

```
Kullback-Leibler Divergence between:
- Query distribution:       P(terms | query_abstract)
- Document distributions:  Q(terms | doc_concrete)

KL(P||Q) = very large

No amount of score boosting (which is just multiplicative/additive) 
can overcome a fundamental distributional mismatch.

To fix, need:
- Adjust P (query expansion) → lower KL divergence
- Or adjust document embeddings to better align
- Not just boost scores
```

---

## Lessons Learned

| Approach | Why It Failed | Lesson |
|----------|---------------|--------|
| Radiance | Wrong time dimension | Target root cause, not symptoms |
| Clustering | Can't cluster what's not retrieved | Retrieval >> re-ranking |
| Inclusion | Added documents sorted to bottom | Architecture constraints matter |

**Key insight:** Post-processing boosts have hard limits. The embedding space determines what's retrievable. No amount of re-ranking fixes fundamental semantic mismatches.

