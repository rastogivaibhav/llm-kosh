# Graph Report - .  (2026-08-03)

## Corpus Check
- cluster-only mode — file stats not available

## Summary
- 3155 nodes · 8070 edges · 170 communities (136 shown, 34 thin omitted)
- Extraction: 92% EXTRACTED · 8% INFERRED · 0% AMBIGUOUS · INFERRED: 660 edges (avg confidence: 0.53)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `41ed7ae5`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- Community 0
- Community 1
- Community 2
- Community 3
- Community 4
- Community 5
- Community 6
- Community 7
- Community 8
- Community 9
- Community 10
- Community 11
- Community 12
- Community 13
- Community 14
- Community 15
- Community 16
- Community 17
- Community 18
- Community 19
- Community 20
- Community 21
- Community 22
- Community 23
- Community 24
- Community 25
- Community 26
- Community 27
- Community 28
- Community 29
- Community 30
- Community 31
- Community 32
- Community 33
- Community 34
- Community 35
- Community 36
- Community 37
- Community 38
- Community 39
- Community 40
- Community 41
- Community 42
- Community 43
- Community 44
- Community 45
- Community 46
- Community 47
- Community 48
- Community 49
- Community 50
- Community 51
- Community 52
- Community 53
- Community 54
- Community 55
- Community 56
- Community 57
- Community 58
- Community 59
- Community 60
- Community 61
- Community 62
- Community 63
- Community 64
- Community 65
- Community 66
- Community 67
- Community 68
- Community 69
- Community 70
- Community 71
- Community 72
- Community 73
- Community 74
- Community 75
- Community 76
- Community 77
- Community 78
- Community 79
- Community 80
- Community 81
- Community 82
- Community 83
- Community 84
- Community 85
- Community 86
- Community 87
- Community 88
- Community 89
- Community 90
- Community 91
- Community 92
- Community 93
- Community 94
- Community 95
- Community 96
- Community 97
- Community 98
- Community 99
- Community 100
- Community 101
- Community 102
- Community 103
- Community 104
- Community 105
- Community 106
- Community 107
- Community 108
- Community 109
- Community 110
- Community 111
- Community 112
- Community 113
- Community 114
- Community 115
- Community 116
- Community 117
- Community 118
- Community 119
- Community 120
- Community 121
- Community 122
- Community 123
- Community 124
- Community 125
- Community 126
- Community 127
- Community 128
- Community 129
- Community 130
- Community 131
- Community 132
- Community 133
- Community 134
- Community 135
- Community 137
- Community 138
- Community 139
- Community 140
- Community 141
- Community 142
- Community 143
- Community 144
- Community 145
- Community 146
- Community 147
- Community 148
- Community 149
- Community 150
- Community 151
- Community 152
- Community 153
- Community 154
- Community 155
- Community 156
- Community 157
- Community 158
- Community 168

## God Nodes (most connected - your core abstractions)
1. `ReasoningEngine` - 151 edges
2. `QueryTrace` - 138 edges
3. `init_cartridge()` - 116 edges
4. `CompanyBrainStore` - 109 edges
5. `main()` - 102 edges
6. `CausalDAG` - 94 edges
7. `FiberBundle` - 84 edges
8. `TraceCritic` - 79 edges
9. `WeaknessReport` - 66 edges
10. `rebuild_index()` - 66 edges

## Surprising Connections (you probably didn't know these)
- `main()` --indirect_call--> `clean()`  [INFERRED]
  llm_kosh/cli.py → scripts/run_temporal_causal_provenance_dataset_eval.py
- `test_v2_episode_table_is_upgraded_before_native_index_creation()` --calls--> `CompanyBrainStore`  [EXTRACTED]
  tests/test_understanding.py → llm_kosh/company_brain/store.py
- `test_status_does_not_initialize_missing_cartridge()` --calls--> `status()`  [EXTRACTED]
  tests/test_atomic_index_safety.py → llm_kosh/engine/commands.py
- `test_reasoning_rejects_document_sized_facts()` --calls--> `ReasoningEngine`  [EXTRACTED]
  tests/test_reasoning_storage_bounds.py → llm_kosh/engine/reasoning/__init__.py
- `FactRec` --uses--> `EdgeType`  [INFERRED]
  research_eval/scripts/run_multidomain_evaluation.py → llm_kosh/engine/reasoning/causal_dag.py

## Import Cycles
- None detected.

## Communities (170 total, 34 thin omitted)

### Community 0 - "Community 0"
Cohesion: 0.04
Nodes (29): Analyze *trace* for per-trace weaknesses. Returns a list of TraceWeakness…, Analyze *trace* for cross-iteration weaknesses in the recursive loop context.…, Path, QueryTrace, Reconstruct a QueryTrace from a previously serialised dict., Immutable record of a single reasoning pass. Captures every decision point from…, Persist QueryTrace objects to disk as JSON files. Each trace is stored as…, Save *trace* to disk. Idempotent — overwrites if trace_id exists. (+21 more)

### Community 1 - "Community 1"
Cohesion: 0.04
Nodes (40): DiscoveryGenerator, Maps a WeaknessReport to a deduplicated, severity-sorted list of…, datetime, Full pipeline: retrieve -> bundle -> critique -> escape if needed -> return.…, Like query(), but also builds and auto-saves a QueryTrace. Candidates are…, Like dialectic_query(), but also builds and auto-saves a QueryTrace., Increase salience without promoting an inferred edge into discovered truth., Promote an edge only when an explicit evidence reference is supplied. (+32 more)

### Community 2 - "Community 2"
Cohesion: 0.05
Nodes (29): build_case_index(), clean_body(), compute_confidence(), extract_facts_and_edges(), find_or_create_stub(), parse_frontmatter(), parse_judgment_date(), process_document() (+21 more)

### Community 3 - "Community 3"
Cohesion: 0.06
Nodes (36): CrossQueryCritic, Analyzes a session (list of QueryTrace objects) for long-term, cross-query…, Analyze a session of traces for 5 session-level weaknesses. Returns a list of…, _make_trace(), Return a QueryTrace suitable for session-level analysis., Tests for CrossQueryCritic.analyze_session()., analyze_session([]) returns []., analyze_session with 4 traces returns [] (minimum is 5 for any check). (+28 more)

### Community 4 - "Community 4"
Cohesion: 0.10
Nodes (37): FactRec, EdgeOrigin, EdgeProvenance, EdgeRole, EdgeType, EvidenceRef, Enum, str (+29 more)

### Community 5 - "Community 5"
Cohesion: 0.09
Nodes (51): CausalEdge, Convert datetime to Unix timestamp, or None., TrajectoryState, _ts(), EscapeMechanism, Traverse low-confidence edges (< threshold) from existing bundle anchors., Search for alternative causal paths to high-confidence targets., Targeted escape from coherence traps. Acts only when LyapunovCritic returns… (+43 more)

### Community 6 - "Community 6"
Cohesion: 0.05
Nodes (39): Enum, str, Enum of weakness categories detected during trace analysis. Per-trace…, Return per_trace_weaknesses + session_weaknesses sorted by severity descending., Highest severity weakness, or None if no weaknesses exist., Represents a single weakness detected in a reasoning trace. This is the primary…, Return a JSON-serialisable dict representation., Reconstruct a TraceWeakness from a previously serialised dict. (+31 more)

### Community 7 - "Community 7"
Cohesion: 0.06
Nodes (33): Analyzes QueryTrace objects for weaknesses. Provides two analysis methods: -…, TraceCritic, _clean_trace(), Return a QueryTrace whose default field values do NOT trigger any weakness.…, Tests for TraceCritic.analyze()., If lyapunov_dimensions is empty, return []., If a required key is absent from lyapunov_dimensions, return []., Trigger when temporal_consistency < 0.6. (+25 more)

### Community 8 - "Community 8"
Cohesion: 0.06
Nodes (62): apply_intake_proposal(), _brain_principal(), company_artifact_inspect(), company_artifact_register(), company_artifact_segment(), company_artifact_snapshot(), company_brain_evaluate(), company_brain_health() (+54 more)

### Community 9 - "Community 9"
Cohesion: 0.09
Nodes (54): add_brain_parser(), _principal(), _principal_arguments(), Any, Path, CLI parser and dispatch for company-brain capabilities., run_brain_command(), compile_context() (+46 more)

### Community 10 - "Community 10"
Cohesion: 0.12
Nodes (52): main(), ensure_root(), read_json(), job_process_safe_receipts(), daily_pack(), Small pack of active projects and open decisions/gaps for an LLM check-in., validate_pack(), validate_cartridge_conformance() (+44 more)

### Community 11 - "Community 11"
Cohesion: 0.12
Nodes (17): EvidenceSegmentInput, Principal, CompanyBrainStore, _json(), _json_load(), Any, Connection, Path (+9 more)

### Community 12 - "Community 12"
Cohesion: 0.09
Nodes (51): CausalRetrieval, _dct(), harmonic_match(), Resonance-based retrieval over the CausalDAG. Returns (TemporalFact,…, Build resonance profiles for all facts currently in the DAG., Full retrieval pipeline. 1. Build query resonance profile. 2. Harmonic-match…, DCT-II: standard type-II Discrete Cosine Transform (stdlib math only)., Build a DCT-based resonance profile for text. 1. Tokenize text. 2. Compute TF… (+43 more)

### Community 13 - "Community 13"
Cohesion: 0.09
Nodes (51): parse_frontmatter(), _all_docs_meta(), audit(), build_repair_plan(), _chunk_text(), classify(), _existing_source_hashes(), export_backup() (+43 more)

### Community 14 - "Community 14"
Cohesion: 0.08
Nodes (21): BiasProfile, get_adapted_weights(), Path, Persistent reasoning bias tracker. Stored as JSON at…, Update patterns and bias profile from a new trace., A detected pattern in reasoning behaviour across multiple traces., Insert or update a pattern in self.patterns., Adapt LyapunovCritic weights based on self-model observations. If any Lyapunov… (+13 more)

### Community 15 - "Community 15"
Cohesion: 0.04
Nodes (28): NOT detected when repair_strength == 0.1 (boundary)., NOT detected when repair_strength >= 0.1., NOT detected when discovery_result_summary is None., When repair_strength key missing, defaults to 1.0 (no weakness)., Detects oscillation when stability goes UP then DOWN., Severity = |curr - prev| (absolute drop)., Description includes all three stability scores., NOT detected when iteration < 2. (+20 more)

### Community 16 - "Community 16"
Cohesion: 0.08
Nodes (19): App(), BottomBar(), Sidebar(), PROMPTS, api, searchPrompts(), ErrorBoundary, Airlock() (+11 more)

### Community 17 - "Community 17"
Cohesion: 0.10
Nodes (43): EpisodeInput, NormalizedEventInput, Any, SessionInput, _actor_type(), _candidate_type(), _clean_text(), _episode_from_events() (+35 more)

### Community 18 - "Community 18"
Cohesion: 0.11
Nodes (37): _any_cosine(), best_match(), _build_idf(), build_vector_index(), corpus_fingerprint(), _cosine(), _doc_text(), extract_procedural_features() (+29 more)

### Community 19 - "Community 19"
Cohesion: 0.11
Nodes (36): boot_text(), find_doc_by_id(), Path, Rewrite a source doc's frontmatter in place (body preserved). Non-destructive., read_doc(), supersede(), update_doc_meta(), atomic_write_text() (+28 more)

### Community 20 - "Community 20"
Cohesion: 0.07
Nodes (44): CompletedProcess, check_path_variable(), _claude_desktop_config_path(), clean_local_state(), create_home_dir(), install_python_package(), _pip_cmd(), _print_pip_result() (+36 more)

### Community 21 - "Community 21"
Cohesion: 0.09
Nodes (32): add_memory(), init_cartridge(), job_sync_reasoning_graph(), explain_pack(), _count(), test_failed_index_activation_preserves_previous_database(), test_index_inspection_is_read_only_and_reports_staleness(), test_status_does_not_initialize_missing_cartridge() (+24 more)

### Community 22 - "Community 22"
Cohesion: 0.09
Nodes (27): Any, datetime, Enum, str, Infer temporal evidence quality from content, metadata, versions, and edges., A partial-order temporal relation usable when exact timestamps are absent., Timestamp-generalised temporal evidence. TheHypoKosh should not require a…, TemporalConstraint (+19 more)

### Community 23 - "Community 23"
Cohesion: 0.10
Nodes (39): active(), agent_memory(), build_engine(), dt(), graph_rag(), hypo(), keyword_rag(), main() (+31 more)

### Community 24 - "Community 24"
Cohesion: 0.07
Nodes (33): fixture, Provides a temporary workspace path initialized for LlmKosh., Provides a helper to run llm-kosh main with args and capture output., runner(), temp_workspace(), test_cli_add_and_query(), test_cli_ingest(), test_cli_init_and_status() (+25 more)

### Community 25 - "Community 25"
Cohesion: 0.08
Nodes (21): Recompute total_severity from all weaknesses., True if any weakness (per-trace or session) exists., Reconstruct a WeaknessReport from a previously serialised dict., Aggregated weakness report for a single trace, combining per-trace and session-…, WeaknessReport, Tests for WeaknessReport dataclass., WeaknessReport with no weaknesses has total_severity=0.0., total_severity is mean of all severities. (+13 more)

### Community 26 - "Community 26"
Cohesion: 0.10
Nodes (17): _make_report(), _make_weakness(), Create a minimal TraceWeakness for test purposes., Wrap weaknesses in a WeaknessReport (all treated as per-trace)., Tests for HealingExecutor.heal() strategy mapping and accumulation., Two SINGLE_PATH_DOMINANCE → depth += 4 (2+2)., Two temporal weaknesses → 2 × 86400., temporal + contradiction + depth should each apply independently. (+9 more)

### Community 27 - "Community 27"
Cohesion: 0.14
Nodes (32): HTMLParser, _bounded_text(), _column_number(), fingerprint_file(), _HTMLText, _image_dimensions(), infer_artifact_type(), inspect_artifact() (+24 more)

### Community 28 - "Community 28"
Cohesion: 0.08
Nodes (20): QueryParams, Reconstruct a QueryParams from a dictionary., Represents modified query parameters for the next recursive iteration. This is…, Test that QueryParams has correct default values., Test custom QueryParams construction., Create QueryParams with default values., Create QueryParams with custom values., Create QueryParams with some custom values and some defaults. (+12 more)

### Community 29 - "Community 29"
Cohesion: 0.08
Nodes (23): HealingAction, HealingActionType, HealingExecutor, Enum, str, Enum of healing actions that can be applied when the recursive loop detects…, Translates a WeaknessReport into a QueryParams for the next recursive…, Apply healing actions derived from *weakness_report* and return new… (+15 more)

### Community 30 - "Community 30"
Cohesion: 0.11
Nodes (33): clear_pid(), is_running(), Path, PID file utilities shared by service.py and cli.py., Return the integer PID stored in path, or 0 if missing or invalid., Return True if a process with the given PID is running. Uses os.kill(pid, 0)…, Write '0' to path, effectively marking the PID slot as unused., Write the current process ID to path. (+25 more)

### Community 31 - "Community 31"
Cohesion: 0.09
Nodes (32): get_mcp_tools_schema(), Starts the MCP server with the specified configuration., Returns the JSON schema of available tools., start_server(), mcp_cartridge(), asyncio, fixture, test_mcp_tools_schema() (+24 more)

### Community 32 - "Community 32"
Cohesion: 0.06
Nodes (35): @babel/core, babel-jest, @babel/preset-env, @babel/preset-react, concurrently, cross-env, devDependencies, @babel/core (+27 more)

### Community 33 - "Community 33"
Cohesion: 0.14
Nodes (13): _add_fact(), dag(), _now(), populated_dag(), datetime, fixture, Tests for llm_kosh.engine.reasoning.discovery (Task 9: T5.1 + T5.2 + T5.3), DAG with 5 facts and some edges: f1 -> f2 (CAUSES) f1 -> f3 (SUPERSEDES) f4 ->… (+5 more)

### Community 34 - "Community 34"
Cohesion: 0.16
Nodes (10): DiscoveryQuestion, DiscoveryResult, DiscoveryType, Enum, str, Discovery Engine — T5.1 + T5.2 + T5.3 Generates and executes discovery…, Executes a DiscoveryQuestion against a CausalDAG + FiberBundle. SAFETY CONTRACT…, SafeDiscovery (+2 more)

### Community 35 - "Community 35"
Cohesion: 0.16
Nodes (31): read_doc(), build_index(), category_abstention(), category_agent_state(), category_multihop(), category_scalability(), category_staleness(), category_temporal() (+23 more)

### Community 36 - "Community 36"
Cohesion: 0.17
Nodes (20): FilenameProcessor, get_all_processors(), get_builtin_processors(), get_processor_by_name(), get_user_processors(), _load_processors_from_dir(), ProcessorBase, ProposalBatch (+12 more)

### Community 37 - "Community 37"
Cohesion: 0.13
Nodes (19): append_ledger(), frontmatter(), Canonical SHA-256 of a ledger row, excluding its own row_hash field., Last row hash in the chain: from CHAIN_HEAD cache, else tail scan, else genesis., Append a hash-chained event row. Locked, fsynced, tamper-evident. Each row…, _read_chain_head(), row_hash(), sha256_bytes() (+11 more)

### Community 38 - "Community 38"
Cohesion: 0.13
Nodes (23): assign_timestamps(), build_causes_edges(), build_contradicts_edges(), build_infers_edges(), build_similar_edges(), ingest_facts(), load_source(), main() (+15 more)

### Community 39 - "Community 39"
Cohesion: 0.13
Nodes (13): engine(), _now(), fixture, _select_anchors includes all candidates above threshold, not just top-5., test_anchor_selection_uses_threshold_not_hard_limit(), test_engine_critique(), test_engine_explore(), test_engine_ingest_returns_id() (+5 more)

### Community 40 - "Community 40"
Cohesion: 0.15
Nodes (9): _FSEventHandler, _ExternalFolderHandler, _IntakeFolderHandler, Path, Manages the full daemon lifecycle., Main entry point: sets up everything and enters the run loop., _ReceiptHandler, ServiceRunner (+1 more)

### Community 41 - "Community 41"
Cohesion: 0.20
Nodes (23): daemon_once(), daemon_run_job(), daemon_start(), daemon_status(), _get_enabled_jobs(), job_audit(), job_backup_snapshot(), job_heal_safe() (+15 more)

### Community 42 - "Community 42"
Cohesion: 0.17
Nodes (16): ModelWorld, ModelWorldLink, ModelWorldNode, ModelWorldNodeKind, ModelWorldStats, Enum, str, Finite, inspectable model-world registry. This is not a graph database… (+8 more)

### Community 43 - "Community 43"
Cohesion: 0.15
Nodes (23): benchmark_ablations(), benchmark_learning_curve(), benchmark_main_table(), build_synthetic_cartridge(), main(), _pct(), print_ablation_table(), print_learning_curve() (+15 more)

### Community 44 - "Community 44"
Cohesion: 0.16
Nodes (9): KoshVerify, Any, Path, Verify a question using the project-native temporal-causal engine., Return a short human-readable provenance explanation., Serializable product-level answer from Kosh Verify., Product/API layer over TheHypoKosh. Use this API when positioning the project…, VerifyReport (+1 more)

### Community 45 - "Community 45"
Cohesion: 0.14
Nodes (21): cartridge(), _now(), datetime, fixture, Write a minimal memory markdown file and rebuild the index., Discourse markers in new fact auto-create edges from preceding facts., test_auto_edge_creation_from_discourse(), test_causal_dag_add_edge() (+13 more)

### Community 46 - "Community 46"
Cohesion: 0.11
Nodes (17): resolveLlmKoshExecutable(), addLog(), { app, BrowserWindow, ipcMain, dialog, shell, Tray, Menu, globalShortcut }, commandLogs, configPath, { daemonManager }, fs, mcpLogs (+9 more)

### Community 47 - "Community 47"
Cohesion: 0.13
Nodes (8): _classification(), mahalanobis_distance(), MemoryTensor, project_subspace(), temporal_vector_decay(), weighted_cosine_similarity(), Any, ValueError

### Community 48 - "Community 48"
Cohesion: 0.12
Nodes (9): CausalDAG, Path, Temporal Causal Hypergraph manager. Owns the reasoning event log. All other…, Serialize hot layer to snapshot.json for faster startup., Attempt to load hot layer from snapshot. Returns True on success., Return binary edges active at query_time from fact_id., Get active binary edges pointing TO fact_id., Return synthetic expansion edges for active hyperedges. A hyperedge A ∧ B -> C… (+1 more)

### Community 49 - "Community 49"
Cohesion: 0.16
Nodes (18): _extract_body(), _extract_title(), _find_connecting_edge(), format_narrative(), Convert datetime to UTC timestamp, handling both aware and naive., First non-empty line, stripped of leading '#', max 60 chars., First sentence after the title line, max 120 chars., Find highest-confidence edge in fiber.paths where target_id == next_fact_id. (+10 more)

### Community 50 - "Community 50"
Cohesion: 0.16
Nodes (14): extract_judis_num(), extract_petitioner(), extract_respondent(), JudisDoc, load_documents(), main(), _parse_date_string(), print_stats() (+6 more)

### Community 51 - "Community 51"
Cohesion: 0.10
Nodes (21): type, type, properties, type, type, type, id, included (+13 more)

### Community 52 - "Community 52"
Cohesion: 0.11
Nodes (12): QueryTracer, Query execution tracing for recursive self-healing loop., Execute query with tracing, capturing retrieval candidates. This variant uses…, Snapshot of execution state at a specific point during query processing., Return the n most recently executed traces., Return all captured traces., Clear in-memory trace history., Record execution state at a pipeline stage (internal use). (+4 more)

### Community 53 - "Community 53"
Cohesion: 0.11
Nodes (19): type, type, type, properties, intake_id, ledger_event, project, raw_hash (+11 more)

### Community 54 - "Community 54"
Cohesion: 0.11
Nodes (19): pending, rejected, reviewed, trusted, status, trust_level, enum, type (+11 more)

### Community 55 - "Community 55"
Cohesion: 0.20
Nodes (5): datetime, Add a temporal fact to the causal DAG. Accepts either: 1. A TemporalFact…, Examine the last 10 facts added before new_fact_id and auto-create causal edges…, Increase salience/reinforcement without silently increasing truth confidence., Promote an edge only when external/new evidence references exist.

### Community 56 - "Community 56"
Cohesion: 0.18
Nodes (17): DiscourseMark, extract_discourse_markers(), infer_temporal_edge(), Causal discourse marker extraction. Detects temporal/causal language patterns…, A detected temporal or causal discourse marker., Return all discourse markers found in text, sorted by position., Look for discourse markers at the start of target_text that signal a…, Decide whether to auto-create a causal edge from source to target. Returns… (+9 more)

### Community 57 - "Community 57"
Cohesion: 0.12
Nodes (17): build, appId, directories, extraResources, mac, nsis, productName, win (+9 more)

### Community 58 - "Community 58"
Cohesion: 0.29
Nodes (12): main(), build_synthetic_servicenow_dataset(), KoshAgent, MultiAgentMemoryBus, Tiny in-process memory bus for testing multi-agent transfer., Synthetic ServiceNow incident/change/problem dataset for deterministic tests.…, Independent Kosh Verify agent with its own local cartridge. The agent has no…, split_servicenow_dataset_by_agent() (+4 more)

### Community 59 - "Community 59"
Cohesion: 0.36
Nodes (16): now_iso(), _compute_hash(), import_apply(), import_detect(), import_list(), import_preview(), import_report(), import_rollback() (+8 more)

### Community 60 - "Community 60"
Cohesion: 0.16
Nodes (14): PYBIND11_MODULE(), mahalanobis_distance(), MemoryTensor, embedding, id, M_sal, t, project_subspace() (+6 more)

### Community 61 - "Community 61"
Cohesion: 0.13
Nodes (7): IntervalTree, _parse_dt(), Pure-Python bisect-based interval index for fast valid-at-T queries., Return all fact IDs whose validity window contains t., Return all facts valid at Unix timestamp t., One-time import of existing llm-kosh SQLite memories as TemporalFacts. Skips…, ReinforcementState

### Community 62 - "Community 62"
Cohesion: 0.22
Nodes (11): HyperEdge, TemporalFact, AgentRunResult, _edge_to_transfer(), _fact_to_transfer(), _first_present(), _hyperedge_to_transfer(), MemoryTransferPacket (+3 more)

### Community 63 - "Community 63"
Cohesion: 0.32
Nodes (16): assert_contains(), assert_not_contains(), index(), main(), Path, LLM-Kosh STATE-Bench Analog: Agent Loop Simulator…, Scenario B: Knowledge Update — State Overwrite Test The agent records a server…, Scenario C: Multi-Session State Continuity Day 1 context is correctly recalled… (+8 more)

### Community 64 - "Community 64"
Cohesion: 0.12
Nodes (10): fixture, Run a temporal query on real cartridge data, Measure memory usage with real documents, Read and display cartridge metadata, Integration tests using real cartridge data, Load real documents from cartridge, Verify real cartridge is accessible, Verify we can load documents from cartridge (+2 more)

### Community 65 - "Community 65"
Cohesion: 0.12
Nodes (15): appId, author, email, name, copyright, description, homepage, jest (+7 more)

### Community 66 - "Community 66"
Cohesion: 0.15
Nodes (16): properties, items, type, type, type, items, type, items (+8 more)

### Community 67 - "Community 67"
Cohesion: 0.28
Nodes (3): _report(), TestDiscoveryGenerator, _weakness()

### Community 68 - "Community 68"
Cohesion: 0.19
Nodes (11): buildCommandArgs(), { buildCommandArgs }, cleanupAndReturn(), fs, os, path, runCommand(), runSmokeTestSequence() (+3 more)

### Community 69 - "Community 69"
Cohesion: 0.22
Nodes (8): Path, ReceiptDAG, _apply_temporal_sequence_clustering(), _extract_numeric_time(), Detect and boost temporally coherent document sequences. If any document from a…, Extract numeric time references from text (Day N, Month N, etc)., retrieve_memory_tensor(), sigmoid()

### Community 70 - "Community 70"
Cohesion: 0.25
Nodes (13): _html_escape(), _page(), Path, Serve the static workbench locally., Open the local workbench in the default browser., Export the workbench as a zip file., Delete the generated workbench., Generate a local static HTML dashboard under exports/workbench/. No server, no… (+5 more)

### Community 71 - "Community 71"
Cohesion: 0.21
Nodes (13): get_default_cartridge_root(), get_global_config(), get_llmkosh_home(), _load_toml(), Any, Path, Read ~/.llmkosh/config.toml. Use tomllib (3.11+) with tomli fallback., Return the llmkosh home directory (~/.llmkosh). (+5 more)

### Community 72 - "Community 72"
Cohesion: 0.15
Nodes (13): match_count, matches, redacted, target, query, required, $schema, title (+5 more)

### Community 73 - "Community 73"
Cohesion: 0.22
Nodes (13): extract_tags_from_content(), main(), primary_answer_precision(), benchmark_support.py (v2 -- KoshVerify API)…, Fraction of query_tags present in the primary_answer fact's tags., Run a single verify call. Returns a flat metrics dict., Run one query and compute tag F1 (top-K) + primary answer precision., Parse the 'Tags: X, Y, Z' line embedded in a fact's content. (+5 more)

### Community 74 - "Community 74"
Cohesion: 0.17
Nodes (10): dependencies, lucide-react, react, react-dom, AgentSim(), ROLE_STYLE, SCENARIOS, lucide-react (+2 more)

### Community 75 - "Community 75"
Cohesion: 0.15
Nodes (12): required, $schema, title, type, intake_id, processor, raw_hash, received_at (+4 more)

### Community 76 - "Community 76"
Cohesion: 0.23
Nodes (4): Path, LyapunovCritic, High when one path dominates and alternatives are absent., Computes stability score V for a FiberBundle. V = w1·temporal_consistency +…

### Community 77 - "Community 77"
Cohesion: 0.31
Nodes (4): Counteracts known biases by adjusting QueryParams., Return a new QueryParams adjusted to counteract observed biases., SelfModelController, TestSelfModelController

### Community 78 - "Community 78"
Cohesion: 0.27
Nodes (5): build_bench_edges(), For each judge that appears in 2+ cases: - Cases sharing ≥2 judges,…, CAUSES edges should only appear when ≥2 judges shared., CAUSES source should have an earlier or equal date than target., TestBuildBenchEdges

### Community 79 - "Community 79"
Cohesion: 0.26
Nodes (9): ingest_facts(), _build_corpus(), _make_doc(), _make_new_format_body(), _make_old_format_body(), tests/test_judis_ingestion.py Tests for scripts/ingest_judis_cartridge.py…, Build a synthetic JUDIS old-format judgment body., Build a synthetic newer-format judgment body (post-2010). (+1 more)

### Community 80 - "Community 80"
Cohesion: 0.17
Nodes (12): description, type, properties, required_sections, rules, items, type, items (+4 more)

### Community 81 - "Community 81"
Cohesion: 0.15
Nodes (13): type, type, type, type, type, type, properties, app_version (+5 more)

### Community 82 - "Community 82"
Cohesion: 0.15
Nodes (4): Test that HealingActionType enum has all required values., Ensure we have exactly 7 healing action types., Verify HealingActionType is a string enum., TestHealingActionType

### Community 83 - "Community 83"
Cohesion: 0.17
Nodes (12): scripts, build, dev, dist, lint, package, package:linux, package:mac (+4 more)

### Community 84 - "Community 84"
Cohesion: 0.27
Nodes (7): CATEGORY_META, CategoryDetailPanel(), LatencyChart(), latencyColor(), ScoreCard(), scoreColor(), SummaryHeader()

### Community 85 - "Community 85"
Cohesion: 0.27
Nodes (8): main(), Create a small Kosh Verify demo cartridge grounded in Vaibhav's project thesis.…, Add a fact without LLM extraction., seed_incident_cartridge(), Path, test_kosh_verify_export_report(), test_kosh_verify_incident_demo_surfaces_project_native_signals(), test_kosh_verify_no_evidence_abstains()

### Community 86 - "Community 86"
Cohesion: 0.17
Nodes (12): source_path, id, included, kind, pack_file, reason, title, required (+4 more)

### Community 87 - "Community 87"
Cohesion: 0.24
Nodes (8): _parse_dt(), _parse_optional_dt(), datetime, Ingest ServiceNow-shaped records as temporal facts and causal/provenance edges.…, Small ServiceNow-shaped record used by Kosh Verify demos/tests. This is…, Import packet into this agent's cartridge, preserving transfer provenance.…, Best available temporal anchor for the record. ServiceNow data often has…, ServiceNowRecord

### Community 88 - "Community 88"
Cohesion: 0.21
Nodes (7): extract_body_air_citations(), extract_own_air_citation(), Extract (year, page) from the CITATION section's AIR entry., Find AIR YYYY SC NNN cross-references in the judgment body text., Cross-refs should be sought in JUDGMENT section only., The synthetic citing doc (judis-40000) should have 5 cross-refs., TestAirCitations

### Community 89 - "Community 89"
Cohesion: 0.27
Nodes (3): extract_date(), Try all date patterns in order on body + title. Returns (datetime_or_None,…, TestExtractDate

### Community 90 - "Community 90"
Cohesion: 0.17
Nodes (12): type, format, type, properties, analysis, created_at, receipt_path, review_id (+4 more)

### Community 91 - "Community 91"
Cohesion: 0.18
Nodes (10): analysis, receipt_path, review_id, stats, trust_state, created_at, required, $schema (+2 more)

### Community 92 - "Community 92"
Cohesion: 0.27
Nodes (5): build_contradicts_edges(), CONTRADICTS: if case A has petitioner P and respondent R, and case B has…, The 5 UNION/KERALA + 5 KERALA/UNION pairs should yield contradicts edges., Docs decades apart should not get CONTRADICTS edges., TestBuildContradictsEdges

### Community 93 - "Community 93"
Cohesion: 0.25
Nodes (5): build_infers_edges(), Build INFERS edges when case A's body cites 'AIR YYYY SC NNN' and that…, Return (engine_mock, docs_with_fact_ids)., No edge should point to itself., TestBuildInfersEdges

### Community 94 - "Community 94"
Cohesion: 0.24
Nodes (5): extract_all_judges(), Extract all judge names from BENCH section(s)., First 10 docs have 5 judges each., Docs 10-19 (contradiction pairs) have 2 judges each., TestExtractAllJudges

### Community 95 - "Community 95"
Cohesion: 0.18
Nodes (11): type, type, type, type, corrections_found, decisions_found, generated_files, open_gaps (+3 more)

### Community 96 - "Community 96"
Cohesion: 0.18
Nodes (10): type, type, properties, llm_kosh_id, llm_kosh_version, query, type, $schema (+2 more)

### Community 98 - "Community 98"
Cohesion: 0.22
Nodes (9): _cartridge_root_str(), _mcp_command(), patch_claude_desktop_config(), Return the cartridge root as a forward-slash string suitable for JSON., Inject the llm-kosh mcpServers entry into claude_desktop_config.json. If an…, Reliable Claude Desktop command for source and frozen installs., test_claude_config_uses_absolute_python_module_command(), test_frozen_commands_reenter_the_cli() (+1 more)

### Community 99 - "Community 99"
Cohesion: 0.22
Nodes (9): source_type, enum, type, cli, daemon, folder, import, mcp (+1 more)

### Community 100 - "Community 100"
Cohesion: 0.22
Nodes (9): chatgpt, claude, codex, deepseek, gemini, human, target, enum (+1 more)

### Community 101 - "Community 101"
Cohesion: 0.22
Nodes (8): description, name, packages, repository, source, url, $schema, version

### Community 102 - "Community 102"
Cohesion: 0.50
Nodes (8): _dag(), _now(), test_discovery_promotion_requires_evidence(), test_empty_bundle_is_no_evidence_abstention(), test_hyperedge_requires_all_sources_in_path_context(), test_inferred_shortcut_can_be_reinforced_without_discovery_promotion(), test_invalid_edge_rejects_missing_facts(), test_reasoning_mode_empirical_filters_unproven_analogy()

### Community 103 - "Community 103"
Cohesion: 0.32
Nodes (6): fs, readConfig(), writeConfig(), fs, path, { readConfig, writeConfig }

### Community 104 - "Community 104"
Cohesion: 0.25
Nodes (6): { app, Notification }, { buildCommandArgs }, http, { resolveLlmKoshExecutable }, { spawn }, { daemonManager }

### Community 105 - "Community 105"
Cohesion: 0.25
Nodes (6): { contextBridge, ipcRenderer }, liveBridge, files, electron, electron, dist/**/*

### Community 106 - "Community 106"
Cohesion: 0.25
Nodes (6): buildDir, fs, Jimp, path, png2icons, resourcesDir

### Community 107 - "Community 107"
Cohesion: 0.25
Nodes (8): visibility, enum, type, blocked, private, public, shareable, work-safe

### Community 108 - "Community 108"
Cohesion: 0.32
Nodes (7): compute_f1(), Test Temporal Causal Reasoning Engine v0.1…, Run temporal reasoning tests using ReasoningEngine. Report F1 scores and…, Simple whitespace + punctuation tokenizer for F1 scoring., Keyword F1 between retrieved context and ground-truth expected string. Returns…, run_temporal_tests(), tokenize()

### Community 109 - "Community 109"
Cohesion: 0.25
Nodes (5): Tests for WeaknessType enum., Verify all 14 weakness types are defined., Verify exactly 14 enum members., Verify all enum members inherit from str., TestWeaknessType

### Community 110 - "Community 110"
Cohesion: 0.25
Nodes (7): Smoke tests for the demo script., Demo script exists at expected path., Demo script runs to completion without error., Demo output contains both KEYWORD SEARCH and TEMPORAL CAUSAL REASONING sections., test_demo_script_exists(), test_demo_script_output_contains_sections(), test_demo_script_runs()

### Community 111 - "Community 111"
Cohesion: 0.29
Nodes (5): fs, path, fs, path, { resolveLlmKoshExecutable }

### Community 112 - "Community 112"
Cohesion: 0.29
Nodes (5): fs, { Jimp }, path, png2icons, pngToIcoObj

### Community 113 - "Community 113"
Cohesion: 0.29
Nodes (7): enum, type, processor, generic_file, importer, manual, receipt

### Community 114 - "Community 114"
Cohesion: 0.57
Nodes (6): _load_migrations(), migrate_apply(), migrate_check(), migrate_rollback(), Path, _save_migrations()

### Community 115 - "Community 115"
Cohesion: 0.43
Nodes (6): generate_mock_locomo(), generate_mock_longmemeval(), main(), Generates a list of multi-session scenarios with updates and temporal reasoning., Generates dialogue graphs for long context event summarization benchmarks., run_benchmark()

### Community 116 - "Community 116"
Cohesion: 0.43
Nodes (3): normalize_party(), Lowercase + strip punctuation, take first 30 chars for matching., TestNormalizeParty

### Community 120 - "Community 120"
Cohesion: 0.40
Nodes (5): linux, icon, target, AppImage, deb

### Community 121 - "Community 121"
Cohesion: 0.40
Nodes (3): _HealthHandler, BaseHTTPRequestHandler, Minimal HTTP handler that serves GET /health.

### Community 123 - "Community 123"
Cohesion: 0.50
Nodes (3): globals, reactHooks, reactRefresh

### Community 124 - "Community 124"
Cohesion: 0.50
Nodes (3): buildDir, fs, path

### Community 125 - "Community 125"
Cohesion: 0.67
Nodes (3): convert_to_memory(), Memory, Path

### Community 126 - "Community 126"
Cohesion: 0.50
Nodes (4): ai-memory-context-pack.v1, schema, enum, type

### Community 127 - "Community 127"
Cohesion: 0.50
Nodes (4): type, read_order, items, type

### Community 128 - "Community 128"
Cohesion: 0.50
Nodes (4): _now(), fixture, DAG with low-confidence edges not normally traversed., sparse_dag()

### Community 134 - "Community 134"
Cohesion: 0.67
Nodes (3): format, type, created_at

## Knowledge Gaps
- **283 isolated node(s):** `python`, `path`, `fs`, `fs`, `{ spawn }` (+278 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **34 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `ReasoningEngine` connect `Community 1` to `Community 0`, `Community 2`, `Community 3`, `Community 4`, `Community 5`, `Community 7`, `Community 8`, `Community 10`, `Community 12`, `Community 14`, `Community 21`, `Community 22`, `Community 23`, `Community 24`, `Community 29`, `Community 34`, `Community 39`, `Community 41`, `Community 42`, `Community 43`, `Community 44`, `Community 48`, `Community 49`, `Community 50`, `Community 64`, `Community 76`, `Community 77`, `Community 102`, `Community 108`?**
  _High betweenness centrality (0.247) - this node is a cross-community bridge._
- **Why does `init_cartridge()` connect `Community 21` to `Community 128`, `Community 1`, `Community 4`, `Community 5`, `Community 9`, `Community 10`, `Community 12`, `Community 13`, `Community 17`, `Community 18`, `Community 19`, `Community 20`, `Community 23`, `Community 24`, `Community 31`, `Community 33`, `Community 35`, `Community 36`, `Community 37`, `Community 39`, `Community 42`, `Community 43`, `Community 45`, `Community 49`, `Community 59`, `Community 63`, `Community 64`, `Community 71`, `Community 102`, `Community 108`, `Community 115`?**
  _High betweenness centrality (0.079) - this node is a cross-community bridge._
- **Why does `QueryTrace` connect `Community 0` to `Community 1`, `Community 3`, `Community 4`, `Community 6`, `Community 7`, `Community 39`, `Community 77`, `Community 14`, `Community 15`, `Community 109`, `Community 52`, `Community 25`?**
  _High betweenness centrality (0.068) - this node is a cross-community bridge._
- **Are the 42 inferred relationships involving `ReasoningEngine` (e.g. with `CausalDAG` and `EdgeOrigin`) actually correct?**
  _`ReasoningEngine` has 42 INFERRED edges - model-reasoned connections that need verification._
- **Are the 38 inferred relationships involving `QueryTrace` (e.g. with `CrossQueryCritic` and `TraceCritic`) actually correct?**
  _`QueryTrace` has 38 INFERRED edges - model-reasoned connections that need verification._
- **Are the 10 inferred relationships involving `CompanyBrainStore` (e.g. with `ReferenceChangedError` and `ReferenceError`) actually correct?**
  _`CompanyBrainStore` has 10 INFERRED edges - model-reasoned connections that need verification._
- **Are the 4 inferred relationships involving `main()` (e.g. with `append_ledger()` and `ensure_root()`) actually correct?**
  _`main()` has 4 INFERRED edges - model-reasoned connections that need verification._