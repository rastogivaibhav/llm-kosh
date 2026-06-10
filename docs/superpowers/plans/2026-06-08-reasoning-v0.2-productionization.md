# Temporal Causal Reasoning Engine v0.2 - Productionization & Scale

> **For agentic workers:** Use superpowers:subagent-driven-development (recommended) to execute this plan task-by-task.

**Goal:** Push ReasoningEngine from 70% → 98%+ temporal reasoning accuracy AND make it production-ready for petabyte-scale data with self-healing capabilities.

**Architecture:** Three-phase approach: (1) Accuracy improvements, (2) Self-healing & resilience, (3) Distributed petabyte-scale architecture.

**Tech Stack:** Python, JSONL (append-only), RocksDB (snapshots), optional Redis (hot cache), gRPC (distributed).

---

## Phase 1: Accuracy Improvements (70% → 95%)

### Task 1: Bidirectional Path Scoring

**Files:**
- Modify: `llm_kosh/engine/reasoning/fiber_bundle.py:_enumerate_paths`
- Modify: `llm_kosh/engine/reasoning/__init__.py:query`
- Test: `tests/test_reasoning_fiber_bundle.py`

**Goal:** Currently only finds forward paths (A→B→C). Need to also find backward paths (C→B→A) to capture complete temporal chains.

- [ ] **Step 1:** Add `_enumerate_paths_backward()` that traverses incoming edges (reverse direction)
- [ ] **Step 2:** In `query()`, call both forward and backward enumeration
- [ ] **Step 3:** Merge results, prefer forward paths 2x weight over backward (temporal semantics)
- [ ] **Step 4:** Test on tmp_004, tmp_005 (currently failing)
- [ ] **Step 5:** Verify F1 scores improve to ≥0.50
- [ ] **Step 6:** Commit with message "feat(reasoning): bidirectional path enumeration for complete chains"

**Expected gain:** +10% accuracy (70% → 80%)

---

### Task 2: Anchor Set Expansion

**Files:**
- Modify: `llm_kosh/engine/reasoning/__init__.py:query` (line 94-95)
- Test: `tests/test_reasoning_engine.py`

**Goal:** Currently uses top-5 anchors. Process ALL candidates from retrieval.

- [ ] **Step 1:** Remove `[:5]` limit on anchor selection
- [ ] **Step 2:** Instead, filter anchors by score threshold (≥0.30)
- [ ] **Step 3:** Add anchor deduplication (by semantic similarity)
- [ ] **Step 4:** Test: tmp_004 should now find both "Team A" and "Board review" anchors
- [ ] **Step 5:** Verify no performance regression (should still be <5ms per query)
- [ ] **Step 6:** Commit "feat(reasoning): expand anchor set beyond top-5"

**Expected gain:** +5% accuracy (80% → 85%)

---

### Task 3: Causal Discourse Marker Extraction

**Files:**
- Create: `llm_kosh/engine/reasoning/discourse.py`
- Modify: `llm_kosh/engine/reasoning/causal_dag.py:add_fact` (call discourse extractor)
- Test: `tests/test_reasoning_discourse.py`

**Goal:** Auto-detect temporal relationships from text ("then", "after", "subsequently", "finally").

- [ ] **Step 1:** Write `extract_discourse_markers(text) -> List[Dict]`
  - Regex patterns for temporal connectives
  - Return: `[{"marker": "then", "position": 25}, ...]`

- [ ] **Step 2:** Write `infer_temporal_edges(doc_pair) -> List[EdgeSpec]`
  - Check if doc1 mentions doc2 subject + temporal marker
  - Example: doc1="DB provisioned" + doc2="Servers deployed" + marker="then" → INFERS edge

- [ ] **Step 3:** Integrate into `add_fact()` - auto-create edges between documents in same project
- [ ] **Step 4:** Test on tmp_003, tmp_005, tmp_007 (should auto-link sessions)
- [ ] **Step 5:** Verify F1 scores on failing tests improve to ≥0.45
- [ ] **Step 6:** Commit "feat(reasoning): auto-extract causal discourse markers"

**Expected gain:** +10% accuracy (85% → 95%)

---

### Task 4: Temporal Alignment & Contradiction Resolution

**Files:**
- Create: `llm_kosh/engine/reasoning/temporal_alignment.py`
- Modify: `llm_kosh/engine/reasoning/causal_dag.py:add_fact`
- Test: `tests/test_reasoning_alignment.py`

**Goal:** When facts have overlapping timelines, auto-align them or flag contradictions.

- [ ] **Step 1:** Write `align_timelines(facts) -> Dict[str, datetime]`
  - Extract dates: "Day 1", "Monday", "15th April" from text
  - Normalize to absolute timestamps

- [ ] **Step 2:** Write `detect_timeline_contradictions(facts) -> List[Contradiction]`
  - Flag if same-project docs imply time-traveling (A after B before A)
  - Weight by confidence

- [ ] **Step 3:** Auto-adjust fact validity windows based on inferred timeline
- [ ] **Step 4:** Test on edge cases (relative dates, ambiguous timelines)
- [ ] **Step 5:** Commit "feat(reasoning): temporal alignment and contradiction detection"

**Expected gain:** +3% accuracy (95% → 98%)

---

## Phase 2: Self-Healing & Resilience (Production Hardening)

### Task 5: Query Feedback Loop

**Files:**
- Create: `llm_kosh/engine/reasoning/feedback.py`
- Modify: `llm_kosh/engine/reasoning/__init__.py:query`
- Test: `tests/test_reasoning_feedback.py`

**Goal:** Learn from query success/failure to improve future queries.

- [ ] **Step 1:** Add `record_feedback(query_id, expected_facts, actual_facts, success: bool)`
- [ ] **Step 2:** Track failed query patterns (e.g., "discourse marker not detected")
- [ ] **Step 3:** Auto-adjust edge confidence: if edge A→B always helps queries, boost confidence
- [ ] **Step 4:** Implement exponential moving average: `new_conf = 0.8 * old_conf + 0.2 * observed_success_rate`
- [ ] **Step 5:** Write to `reasoning/feedback.jsonl` (append-only like events)
- [ ] **Step 6:** Test: Run 100 queries, observe confidence drift
- [ ] **Step 7:** Commit "feat(reasoning): adaptive feedback loop for self-healing"

**Expected improvement:** Adaptation to domain-specific patterns over time.

---

### Task 6: Snapshot Integrity Checking

**Files:**
- Modify: `llm_kosh/engine/reasoning/causal_dag.py:_try_load_snapshot`
- Create: `llm_kosh/engine/reasoning/integrity.py`
- Test: `tests/test_reasoning_integrity.py`

**Goal:** Detect and recover from corrupted snapshots/logs.

- [ ] **Step 1:** Add checksum validation to snapshot JSON
  - Compute SHA-256 of content, store in snapshot header

- [ ] **Step 2:** Implement `verify_snapshot() -> bool`
  - Check: fact count consistency, edge topology soundness, no orphaned facts

- [ ] **Step 3:** On corruption, auto-rebuild from JSONL log (already implemented, just formalize)
- [ ] **Step 4:** Log integrity issues to `reasoning/integrity_log.jsonl`
- [ ] **Step 5:** Test: Corrupt a snapshot, verify recovery
- [ ] **Step 6:** Commit "feat(reasoning): snapshot integrity checking and auto-recovery"

---

### Task 7: Distributed Path Enumeration

**Files:**
- Create: `llm_kosh/engine/reasoning/distributed.py`
- Modify: `llm_kosh/engine/reasoning/fiber_bundle.py:_enumerate_paths`
- Test: `tests/test_reasoning_distributed.py`

**Goal:** For large fact graphs, distribute path enumeration across processes.

- [ ] **Step 1:** Implement `_enumerate_paths_distributed(dag, start_id, targets, depth, num_workers=4)`
  - Partition targets by hash
  - Spawn worker processes for each partition
  - Merge results

- [ ] **Step 2:** Use `multiprocessing.Pool` for worker management
- [ ] **Step 3:** Test on fact graph with 10k nodes
- [ ] **Step 4:** Verify speedup (should be ~3-4x with 4 workers)
- [ ] **Step 5:** Fall back to single-threaded for small graphs (<1k nodes)
- [ ] **Step 6:** Commit "feat(reasoning): distributed path enumeration for large graphs"

---

## Phase 3: Petabyte-Scale Architecture

### Task 8: Time-Partitioned Event Log

**Files:**
- Modify: `llm_kosh/engine/reasoning/causal_dag.py`
- Create: `llm_kosh/engine/reasoning/partitioning.py`
- Test: `tests/test_reasoning_partitioning.py`

**Goal:** Instead of single `reasoning/events.jsonl`, shard by time (daily/monthly).

- [ ] **Step 1:** Implement `_get_log_path(timestamp) -> Path`
  - Returns `reasoning/2026/06/08_events.jsonl` for June 8, 2026
  - Auto-creates directories

- [ ] **Step 2:** Modify `add_fact()` to write to date-partitioned log
- [ ] **Step 3:** Implement `_load_from_log()` to iterate all date partitions
- [ ] **Step 4:** Add log rotation: archive old logs to `reasoning/archive/`
- [ ] **Step 5:** Test: Ingest 1M facts spanning multiple days, verify loading
- [ ] **Step 6:** Commit "feat(reasoning): time-partitioned event log for petabyte scale"

**Expected:** Enables efficient historical queries and log management at scale.

---

### Task 9: Hot/Warm/Cold Storage Tiers

**Files:**
- Create: `llm_kosh/engine/reasoning/tiering.py`
- Modify: `llm_kosh/engine/reasoning/causal_dag.py`
- Test: `tests/test_reasoning_tiering.py`

**Goal:** Keep recent facts in memory, older ones in compressed snapshots, ancient ones archived.

- [ ] **Step 1:** Define tiers:
  - Hot: Last 7 days in memory (Dict/List)
  - Warm: Last 90 days in SQLite index
  - Cold: >90 days in gzipped JSONL archives

- [ ] **Step 2:** Implement `_age_fact(fact_id) -> int` (days since creation)
- [ ] **Step 3:** Implement `promote_to_warm()` and `demote_to_cold()` jobs
- [ ] **Step 4:** Modify `get_fact()` to query appropriate tier
- [ ] **Step 5:** Test: 1M facts, query both hot and cold, measure latency
- [ ] **Step 6:** Commit "feat(reasoning): hot/warm/cold storage tiering"

**Expected:** 1M facts searchable in <100ms, storage reduced 10-50x.

---

### Task 10: RocksDB Index for Billion-Scale Facts

**Files:**
- Create: `llm_kosh/engine/reasoning/index.py`
- Modify: `llm_kosh/engine/reasoning/causal_dag.py`
- Test: `tests/test_reasoning_index_billion.py`

**Goal:** Replace in-memory Dict with RocksDB for billion-fact support.

- [ ] **Step 1:** Create `reasoning/rocksdb/` directory
- [ ] **Step 2:** Implement `FactIndex` using rocksdb-python
  - Write: `index.put(fact_id, fact_json)`
  - Read: `index.get(fact_id)`
  - Range query: `index.range_query(start_ts, end_ts)`

- [ ] **Step 3:** Dual-write: Update both in-memory cache AND RocksDB
- [ ] **Step 4:** On startup, load top-N facts to cache, rest on-demand
- [ ] **Step 5:** Test: 1B fact graph, measure P50/P99 latency
- [ ] **Step 6:** Commit "feat(reasoning): RocksDB index for petabyte-scale"

**Expected:** Billion facts, <50ms median query latency.

---

### Task 11: Distributed ReasoningEngine (Multi-Node)

**Files:**
- Create: `llm_kosh/engine/reasoning/grpc_service.py`
- Create: `llm_kosh/engine/reasoning/coordinator.py`
- Test: `tests/test_reasoning_distributed_nodes.py`

**Goal:** Shard fact graph across multiple nodes, coordinate queries.

- [ ] **Step 1:** Define gRPC service:
  - `query(query_str, shard_id) -> QueryResult`
  - `ingest(content, ...) -> fact_id` (routes to appropriate shard)
  - `health_check() -> Status`

- [ ] **Step 2:** Implement `ShardCoordinator` that:
  - Routes fact by ID hash to appropriate node
  - Gathers results from all shards
  - Merges FiberBundles

- [ ] **Step 3:** Test with 3-node cluster:
  - 1M facts total, split into 3 shards
  - Run 100 queries, verify correctness
  - Measure throughput (queries/sec)

- [ ] **Step 4:** Commit "feat(reasoning): distributed multi-node coordinator"

**Expected:** 100k queries/sec across 10 nodes.

---

## Phase 4: Integration Testing on Real Cartridge

### Task 12: Real Cartridge Integration Test

**Files:**
- Create: `tests/test_reasoning_real_cartridge.py`
- Create: `scripts/benchmark_real_cartridge.py`
- Test: Run on user's `C:\Users\vrast\OneDrive\Apps\Documents\llm-kosh-cart`

**Goal:** Ingest existing cartridge memories, run temporal queries on real data.

- [ ] **Step 1:** Load all documents from cartridge source/
- [ ] **Step 2:** Ingest into ReasoningEngine with metadata from existing DB
- [ ] **Step 3:** Run benchmark suite:
  - Temporal query accuracy on real data
  - Latency under load (concurrent queries)
  - Memory footprint
  - Snapshot size

- [ ] **Step 4:** Create dashboard showing:
  - Accuracy by document type
  - Latency percentiles (P50, P95, P99)
  - Index size vs fact count
  - Cache hit rate

- [ ] **Step 5:** Document results in `REAL_CARTRIDGE_BENCHMARK.md`
- [ ] **Step 6:** Commit "test(reasoning): real cartridge integration benchmark"

---

## Success Criteria

### Accuracy
- [ ] 98%+ on temporal reasoning tests (vs current 70%)
- [ ] 100% on real cartridge queries (user-validated)

### Performance
- [ ] <5ms query latency (P99) on 1M facts
- [ ] <50ms on 1B facts (petabyte-scale)
- [ ] 100k+ queries/second on distributed cluster

### Resilience
- [ ] Auto-recovery from corrupted snapshots
- [ ] Automatic contradiction detection
- [ ] Feedback-driven edge confidence adaptation
- [ ] Zero data loss on node failure (distributed)

### Scale
- [ ] Time-partitioned logs support unlimited fact ingestion
- [ ] Hot/warm/cold tiering reduces storage 10-50x
- [ ] RocksDB + distributed nodes support petabyte data
- [ ] Multi-node clustering for 100k QPS

---

## Execution Timeline

**Phase 1 (Accuracy):** 2-3 days
- Tasks 1-4: Bidirectional paths, anchor expansion, discourse markers, temporal alignment

**Phase 2 (Resilience):** 2-3 days
- Tasks 5-7: Feedback loop, integrity checking, distributed path enumeration

**Phase 3 (Scale):** 3-4 days
- Tasks 8-11: Partitioning, tiering, RocksDB, multi-node coordinator

**Phase 4 (Integration):** 1-2 days
- Task 12: Real cartridge testing and benchmarking

**Total:** ~10 days to production-ready at petabyte scale

---

## Notes

- All changes maintain backward compatibility with v0.1
- Snapshot format versioning allows easy schema evolution
- Feedback loop enables continuous improvement after deployment
- Distributed architecture is optional—single-node still scales to billions
- Real cartridge testing will guide final tuning

