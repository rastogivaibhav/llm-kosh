# Parallel Workplan: Phase 0 + Phase 1 (Weeks 1-8)

## Overview

**Running two workstreams in parallel:**
- **Workstream A:** Phase 0 (Foundation: install, ingestion, MCP)
- **Workstream B:** Phase 1 (Validation: causal test on 200 records)

**Why parallel?**
- Phase 0 and 1 are mostly independent
- Learning from causal test (1) informs Phase 0 design (A)
- Faster overall timeline (8 weeks instead of sequential 12 weeks)
- Parallel work discovers issues earlier

**Integration point:** Week 5-6 (learnings merge)

---

## Timeline at a Glance

```
WEEK 1     WEEK 2     WEEK 3     WEEK 4     WEEK 5     WEEK 6     WEEK 7     WEEK 8
│          │          │          │          │          │          │          │
Phase 0 ──────────────────────────────────────────────────────────────────────────
(Foundation)  Design    Build      Build      Test/Fix   Polish    Ship v0.1

Phase 1 ──────────────────────────────────────────────────
(Causal)      Design    Extract    Validate   Analyze    DECISION

         Parallel work                        ↓ Merge learnings
                                             ↓ Phase 1 informs Phase 0
```

---

## Workstream A: Phase 0 (Foundation)

### **Goal:** One-click install + robust ingestion + auto MCP

---

### **Week 1: Phase 0 Design (Parallel with Phase 1 Design)**

**Deliverable:** Architecture blueprint for Phase 0

**Tasks:**

1. **Installation Pipeline Design**
   - Spec: What does `pip install llm-kosh` do?
   - Step 1: Download package
   - Step 2: Install dependencies
   - Step 3: Create ~/.llmkosh/ directory structure
   - Step 4: Register daemon with systemd/launchd/Windows Services
   - Step 5: Create default cartridge
   - Step 6: Test daemon startup
   - Step 7: Return success/failure message
   
   **Question:** What config needed? (Zero = best, minimal acceptable)
   **Decision:** No initial config. Auto-detect or ask once per machine.

2. **Directory Structure Design**
   ```
   ~/.llmkosh/
     ├─ config.toml             (Settings)
     ├─ daemon.pid              (Running daemon PID)
     ├─ daemon.log              (Log file)
     ├─ cartridges/
     │   └─ default/            (Default cartridge)
     │       ├─ memory.db
     │       ├─ reasoning/
     │       │   └─ events.jsonl
     │       └─ source/
     └─ shell-integration.sh    (CLI integration)
   ```

3. **Auto-Daemon Logic**
   - When user runs `llm-kosh` command
   - Check: Is daemon running?
   - If NO: Auto-start daemon
   - If YES: Use existing daemon
   - User sees: No difference (either way works)

4. **MCP Auto-Start Design**
   - Daemon includes MCP server
   - Starts automatically when daemon starts
   - Listens on stdio (for Claude)
   - No user configuration
   - Claude Desktop finds it automatically

5. **Ingestion Pipeline Skeleton**
   - What happens when file drops in cartridge folder?
   - Watch folder for new files
   - Detect format (PDF, DOCX, MD, JSON, etc.)
   - Route to appropriate converter
   - Ingest to SQLite
   - Log result
   - Error handling: Log and continue

**Deliverable:** Architecture document (2-3 pages)
- Installation flow diagram
- Directory structure
- Daemon lifecycle
- MCP integration
- Ingestion flow

**Owner:** 1 person
**Time:** 3-4 days
**Blocking:** Building Phase 0 code

---

### **Week 2: Phase 0 Build - Part A (Daemon Service)**

**Deliverable:** Working daemon that auto-starts and stays running

**Tasks:**

1. **Daemon Core**
   - Process management (spawn, manage, restart)
   - PID file handling
   - Log file management
   - Signal handling (graceful shutdown)
   - Error recovery

2. **Auto-Start Mechanism**
   - Systemd integration (Linux)
   - launchd integration (macOS)
   - Windows Service integration
   - Shell wrapper script for detection
   - Auto-spawn on first command

3. **HTTP API Skeleton**
   - Endpoints: /status, /reason, /query, /ingest
   - Request/response format
   - Error handling
   - Logging

4. **MCP Server Integration**
   - Start MCP on daemon start
   - Stdio handling
   - Tool mapping
   - Shutdown cleanup

**Testing:**
- Local: Does daemon start/stop correctly?
- Local: Does auto-spawn work?
- Local: Does `llm-kosh status` show running?

**Deliverable:** Runnable daemon (with debug output)

**Owner:** 1-2 people
**Time:** Full week
**Blocking:** Phase 0 Part B

---

### **Week 3: Phase 0 Build - Part B (Ingestion + Installation)**

**Deliverable:** One-click install works + ingestion auto-starts

**Tasks:**

1. **Installation Package**
   - setup.py / pyproject.toml configuration
   - Dependency specification
   - Entry points (llm-kosh command)
   - Daemon registration script
   - Post-install hook (create ~/.llmkosh/)

2. **Ingestion Pipeline**
   - File watcher (monitors cartridge folder)
   - Format detection (PDF, DOCX, Markdown, JSON)
   - Converter routing
   - SQLite ingestion
   - Error handling + retry logic
   - Progress logging

3. **Shell Integration**
   - CLI command registration
   - Shell completions (bash, zsh)
   - Alias support
   - Portable across platforms

4. **Default Cartridge**
   - Create default on first install
   - Initialize SQLite schema
   - Create events.jsonl
   - Set permissions

**Testing:**
- Fresh install: Does everything work?
- File drop: Does auto-ingestion happen?
- Command line: Does `llm-kosh query` work?

**Deliverable:** `pip install llm-kosh` works end-to-end

**Owner:** 1-2 people
**Time:** Full week
**Blocking:** Phase 0 Part C

---

### **Week 4: Phase 0 Build - Part C (Polish + MCP)**

**Deliverable:** Polished Phase 0, MCP fully integrated

**Tasks:**

1. **MCP Integration**
   - Claude Desktop discovers MCP automatically
   - All tools mapped and tested
   - Error handling in MCP layer
   - Logging for debugging

2. **Error Handling**
   - Installation failures → clear messages
   - Ingestion failures → logged, not fatal
   - Daemon crashes → auto-restart
   - Network errors → graceful degradation

3. **Logging + Monitoring**
   - Daemon logs to ~/.llmkosh/daemon.log
   - Rotation (don't fill disk)
   - User can see: `llm-kosh daemon logs`
   - Silent operation (no spam)

4. **Testing**
   - Installation on fresh machine (or VM)
   - File ingestion with various formats
   - CLI commands work
   - MCP connects from Claude
   - Daemon auto-restart after crash
   - Multi-user scenarios

**Deliverable:** Phase 0 production-ready (pre-release)

**Owner:** 1-2 people
**Time:** Full week
**Blocking:** Phase 0 validation

---

### **Week 5: Phase 0 Validation + Merge Learnings**

**Deliverable:** Phase 0 ready to ship + merged with Phase 1 learnings

**Tasks:**

1. **Testing on Your Cartridge**
   - Install on fresh machine (or VM)
   - Point at your 20,531-document cartridge
   - Auto-ingestion on new documents
   - CLI queries work
   - MCP connects from Claude
   - Performance acceptable (query latency < 100ms)

2. **Merge Phase 1 Learnings**
   - Phase 1 (causal test) completes this week
   - See: What causal extraction found
   - Adjust Phase 0 if needed
   - No major changes (foundation stays solid)
   - Minor tweaks OK

3. **Fix Issues**
   - Any bugs found in testing
   - Performance optimizations
   - UX improvements

4. **Prepare Ship**
   - Release notes
   - Documentation
   - Installation guide

**Deliverable:** Phase 0 ready for v0.1.0 release

**Owner:** 1-2 people
**Time:** Full week
**Blocking:** Phase 0 ship (week 6)

---

### **Week 6: Phase 0 Ship**

**Deliverable:** v0.1.0 released (internal or public)

**Tasks:**

1. **Final Testing**
   - Comprehensive smoke test
   - Edge case handling
   - Performance validation

2. **Release**
   - Tag version 0.1.0 in git
   - Build wheel/sdist
   - Test `pip install llm-kosh` works

3. **Documentation**
   - Installation guide
   - Quick start guide
   - Troubleshooting guide

**Deliverable:** v0.1.0 shipped

**Owner:** 1 person
**Time:** 2-3 days
**Blocking:** Post-Phase 0 activities

---

## Workstream B: Phase 1 (Causal Validation)

### **Goal:** Extract causal facts from 200 records, validate approach

---

### **Week 1: Phase 1 Design (Parallel with Phase 0 Design)**

**Deliverable:** Causal extraction blueprint

**Tasks:**

1. **Select 200 Test Records**
   - From your 20,531 documents
   - Domain: Constitutional law (homogeneous, fewer edge cases)
   - Date range: 1970-2010 (mature doctrine)
   - Criteria: Must have clear causal relationships

2. **Causal Pattern Analysis**
   - Read 20 sample judgments
   - Identify common causal patterns:
     - "Following the principle established in X" → APPLIES
     - "This Court held in X" → ESTABLISHES
     - "Distinguished from X" → CONTRADICTS
     - "As in the earlier case X" → CITES
     - "Overruling X" → OVERRULES
     - "Interpreting Article X" → INTERPRETS

3. **Extraction Heuristics Design**
   - Rule-based patterns (regex/NLP)
   - Confidence scoring
   - Edge case handling
   - Error recovery

4. **Fact Schema Design**
   ```
   Fact:
     - id: unique identifier
     - content: legal principle (text)
     - source_judgment: which case
     - year: when established
     - confidence: how sure (0-1)
   
   Edge:
     - source_fact: from
     - target_fact: to
     - type: CITES, OVERRULES, INTERPRETS, APPLIES, ESTABLISHES
     - confidence: how sure (0-1)
     - evidence: quote from judgment
   ```

5. **Validation Plan**
   - Spot-check 20 extracted facts (manual)
   - Are causal chains logical?
   - Are confidence scores reasonable?
   - Do edges make legal sense?

**Deliverable:** Extraction spec document

**Owner:** 1 person (with domain knowledge helpful)
**Time:** 3-4 days
**Blocking:** Phase 1 extraction

---

### **Week 2: Phase 1 Extraction - Build**

**Deliverable:** Extraction pipeline runs on 200 records

**Tasks:**

1. **Implement Extraction Heuristics**
   - NLP: Parse judgment text
   - Pattern matching: Find causal relationships
   - Confidence scoring: Rate each extraction
   - Logging: Track what was extracted, what failed

2. **Test Extraction**
   - Run on 200 documents
   - Check output: Are facts extracted?
   - Check edges: Are relationships correct?
   - Count: How many facts? How many edges?

3. **Handle Edge Cases**
   - Judgments with no clear causality
   - Complex multi-party reasoning
   - Ambiguous references
   - Missing citations

4. **Logging**
   - What was extracted from each document
   - Confidence for each fact/edge
   - Failures and reasons
   - Summary statistics

**Deliverable:** 200 documents processed, facts extracted

**Owner:** 1 person
**Time:** Full week
**Blocking:** Phase 1 validation

---

### **Week 3: Phase 1 Validation - Extract + Analyze**

**Deliverable:** Analysis of what causal looks like

**Tasks:**

1. **Manual Validation**
   - Read extracted facts (sample 20)
   - Check: Are they legal/correct?
   - Score accuracy (% correct)
   - Identify patterns of errors
   - Adjust heuristics if needed

2. **Ingest into Reasoning DAG**
   - Take extracted facts
   - Load into causal DAG (events.jsonl)
   - Build reasoning graph
   - Create indexes

3. **Test Reasoning Queries**
   - Example: "What's the causal chain for basic structure doctrine?"
   - Run multi-hop reasoning
   - Check: Do chains make sense?
   - Measure: Query latency
   - Analyze: Stability scores

4. **Statistics**
   - Facts extracted: Count
   - Edges created: Count
   - Average confidence: Score
   - Graph density: Edges per fact
   - Query performance: ms/query

5. **Quality Assessment**
   - Is extraction accurate? (80%+ correct?)
   - Are chains coherent? (Do they make legal sense?)
   - Is performance acceptable? (< 100ms query?)
   - Is this scalable to 20k? (Estimate based on 200)

**Deliverable:** Analysis report + causal graph (200 records)

**Owner:** 1-2 people
**Time:** Full week
**Blocking:** Phase 1 decision

---

### **Week 4: Phase 1 Analysis + Decision**

**Deliverable:** Go/No-go decision for full causal build

**Tasks:**

1. **Synthesize Learnings**
   - Combine validation results
   - Document what works
   - Document what doesn't
   - Identify improvements needed

2. **Create Report**
   - Extraction accuracy: Y% correct
   - Reasoning chain quality: Good/OK/Poor
   - Performance: X ms/query
   - Scalability estimate: Cost to scale 20k?
   - Recommendations: What to change?

3. **DECISION GATE**
   - Is causal extraction working? (Accuracy > 75%)
   - Are chains coherent? (Manual review: yes/no)
   - Is performance acceptable? (Latency < 200ms)
   - Can we scale? (Complexity manageable)

   **GO:** Proceed to Phase 2 (recursive loop)
   
   **NO-GO:** Adjust approach, iterate
   
   **PARTIAL:** Scale with improvements

4. **Plan Next Steps**
   - If GO: Phase 2 roadmap
   - If NO-GO: What to change?
   - If PARTIAL: Which improvements first?

**Deliverable:** Phase 1 decision report + next roadmap

**Owner:** 1 person (lead)
**Time:** Full week
**Blocking:** Phase 2 approval

---

## Integration Points (Weeks 5-6)

### **Week 5: Learnings Merge**

**When Phase 0 (week 5) meets Phase 1 (week 4):**

1. **Phase 1 Outputs → Phase 0 Inputs**
   - Causal facts structure → Adjust ingestion pipeline?
   - Reasoning graph size → Performance implications?
   - Query latency → MCP responsiveness?
   - Data format → SQLite schema impacts?

2. **Adjustments to Phase 0**
   - Minor tweaks OK
   - Major changes? → Phase 0 scope stays fixed
   - Use learnings to optimize ingestion pipeline

3. **No Blocking**
   - Phase 0 continues regardless of Phase 1 results
   - Phase 1 is validation, not requirement
   - Phase 0 ships even if Phase 1 says "iterate"

---

### **Week 6: Phase 0 Polish (Phase 1 Results Available)**

**Phase 1 decision made, Phase 0 ships:**

1. **If Phase 1 says GO:**
   - Phase 0 polishes foundation
   - Phase 2 (recursive loop) can start immediately
   - Everyone happy

2. **If Phase 1 says NO-GO:**
   - Phase 0 still ships (foundation is solid)
   - Phase 2 doesn't start yet
   - Iterate causal approach (weeks 7-8)
   - Then Phase 2

3. **Either way:**
   - Phase 0 is production-ready
   - Foundation is bulletproof
   - Features come later

---

## Resource Allocation

### **Workstream A (Phase 0: Foundation)**
- **Team size:** 2 people (can be 1, but slower)
- **Roles:**
  - Engineer 1: Daemon + installation (weeks 1-3)
  - Engineer 2: Ingestion + MCP (weeks 2-4)
  - Overlap weeks 3-4: Both work on integration
- **Total effort:** 8 person-weeks

### **Workstream B (Phase 1: Causal)**
- **Team size:** 1-2 people
- **Roles:**
  - Engineer 1: Extraction + testing (weeks 1-3)
  - Domain expert (optional): Review accuracy (weeks 3-4)
- **Total effort:** 4-5 person-weeks

### **Shared:**
- Architecture review (week 1: 1 day)
- Integration/merge (week 5: 2-3 days)
- Release (week 6: 2-3 days)

### **Total Project Effort: 12-14 person-weeks across 8 weeks**

**If 1 person:** 12-14 weeks (sequential)
**If 2 people:** 7-8 weeks (parallel)
**If 3+ people:** Can overlap more, faster

---

## Parallel Risks & Mitigation

### **Risk 1: Phase 1 discovers causal won't work**
- **Impact:** May need to redesign ingestion
- **Mitigation:** Quick iteration (weeks 7-8)
- **Backup:** Phase 0 still ships, Phase 2 delayed
- **Likelihood:** Low (200 records should validate)

### **Risk 2: Phase 0 takes longer than estimated**
- **Impact:** Delay Phase 0 ship
- **Mitigation:** Phase 1 independent, not blocked
- **Backup:** Extend weeks 5-6 as needed
- **Likelihood:** Medium (integration complexity)

### **Risk 3: Resource constraints**
- **Impact:** Can't run both in parallel
- **Mitigation:** Sequential (Phase 0 first) still works
- **Backup:** Prioritize Phase 0 (foundation first)
- **Likelihood:** Depends on your team

### **Risk 4: Phase 1 learnings require Phase 0 redesign**
- **Impact:** Rework done
- **Mitigation:** Keep Phase 0 modular, easy to adjust
- **Backup:** Redesign is OK if major (foundation more important)
- **Likelihood:** Low (design should handle it)

---

## Success Criteria

### **Phase 0 Success (Week 6):**
- ✅ `pip install llm-kosh` works on fresh machine
- ✅ Auto-daemon startup works
- ✅ File ingestion auto-starts
- ✅ `llm-kosh query "something"` returns results
- ✅ Claude Desktop connects via MCP
- ✅ Query latency < 100ms (on your 20k docs)
- ✅ No user configuration needed

### **Phase 1 Success (Week 4):**
- ✅ 200 documents extracted → facts created
- ✅ Extraction accuracy > 75% (manual spot-check)
- ✅ Causal chains coherent (legal sense)
- ✅ Query performance < 200ms
- ✅ Clear roadmap for scaling to 20k

### **Integration Success (Week 6):**
- ✅ Phase 0 ships on schedule
- ✅ Phase 1 results inform Phase 2 (if GO)
- ✅ No rework required for Phase 0
- ✅ Ready for Phase 2 (or iteration)

---

## Decision Gates

### **Gate 1: End of Week 1 (Design Review)**
- **Check:** Are Phase 0 and Phase 1 designs solid?
- **Approval required:** Yes
- **If NO:** Iterate design (1 week)
- **If YES:** Proceed to build

### **Gate 2: End of Week 3 (Mid-Build)**
- **Check:** Is Phase 0 build on track? Is Phase 1 extraction working?
- **Approval required:** Yes
- **If NO:** Adjust effort/timeline
- **If YES:** Continue

### **Gate 3: End of Week 4 (Phase 1 Decision)**
- **Check:** Does causal extraction work?
- **Approval required:** Yes (Go/No-go)
- **If GO:** Proceed to Phase 2 design
- **If NO-GO:** Plan iteration

### **Gate 4: End of Week 6 (Phase 0 Ship)**
- **Check:** Is Phase 0 production-ready?
- **Approval required:** Yes
- **If YES:** Release v0.1.0
- **If NO:** Extend week 5-6

---

## Outputs by Week

```
WEEK 1:
  ├─ Phase 0 Design Doc
  ├─ Phase 1 Design Doc
  └─ Team approval

WEEK 2:
  ├─ Daemon prototype
  └─ Extraction code (25% complete)

WEEK 3:
  ├─ Installation package working
  ├─ Ingestion pipeline running
  └─ 200 documents extracted

WEEK 4:
  ├─ CLI commands work
  ├─ Causal validation report
  └─ Phase 1 decision (GO/NO-GO)

WEEK 5:
  ├─ Phase 0 validated on your 20k docs
  ├─ Learnings merged into Phase 0
  ├─ MCP fully integrated
  └─ v0.1.0 ready

WEEK 6:
  ├─ v0.1.0 released
  ├─ Installation guide published
  └─ Phase 2 roadmap (if Phase 1 = GO)

WEEK 7-8:
  ├─ Phase 1 iteration (if NO-GO)
  └─ Or Phase 2 prep (if GO)
```

---

## Next: Your Approval

**Questions for you:**

1. **Team size:** How many engineers available?
   - 1 person → Sequential (Phase 0 weeks 1-6, Phase 1 weeks 7-8)
   - 2+ people → Parallel (weeks 1-8 as designed)

2. **Domain expertise:** Do you have causal domain knowledge?
   - Yes → Phase 1 can self-validate
   - No → Might need domain expert (week 3-4)

3. **Timeline:** Is 8 weeks realistic?
   - Yes → Proceed with parallel plan
   - No → Adjust (can extend to 10-12)

4. **Risk tolerance:** OK with causal validation uncertainty?
   - High risk OK → Parallel is fine
   - Low risk → Sequential safer (Phase 0 first)

5. **Priorities:** What's more important?
   - Foundation rock-solid → Phase 0 first
   - Validate causal works → Phase 1 first
   - Both → Parallel (this plan)

**Once you confirm, I can detail Week 1 specifically.**

---

## One More Thing

**This parallel approach is optimal because:**

1. ✅ **Fast learning:** Phase 1 insights in week 4, not week 14
2. ✅ **Independent work:** Teams don't block each other
3. ✅ **Merge friendly:** Learnings inform Phase 0, not rework it
4. ✅ **Risk early:** Know if causal works by week 4
5. ✅ **Ship on time:** Phase 0 ships week 6 regardless

**This is the professional way to do parallel development.**

Ready to start?
