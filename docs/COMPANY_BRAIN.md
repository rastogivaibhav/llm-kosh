# Company brain foundation

Company Brain is an explicit cartridge profile, not the default behaviour of a
personal install. New cartridges start in `personal` mode. Select the governed
profile with `llm-kosh install --mode company-brain`, or initialise an existing
cartridge with `llm-kosh --root ./cartridge brain init` before configuring
external source folders and Company Brain MCP tools.

The company-brain layer turns a cartridge from a collection of searchable files
into governed organizational memory. It is additive: legacy source files remain
readable and can be migrated idempotently without deleting or rewriting them.

## Data flow

```text
source systems / legacy cartridge
              |
              v
reference-first artifacts or explicit immutable snapshots
              |
              v
normalized events --> sessions --> goal-oriented episodes
              |
              v
candidate atomic memories --review--> verified/active memory
              |
              v
permission-first hybrid retrieval
              |
              v
structured, cited, token-budgeted context packs
```

Full documents, transcripts, and receipts are evidence. A memory is a bounded
claim such as a decision, fact, constraint, task, outcome, risk, question, or
procedure. Every memory must cite at least one evidence record and carries a
lifecycle, confidence, validity window, classification, and access policy.

## Storage contract

- `brain/company_brain.sqlite` is canonical metadata for evidence, episodes,
  memories, entities, relations, lifecycle events, and evidence links.
- Existing local artifacts remain at their original paths. Canonical metadata
  stores their exact path, SHA-256 fingerprint, size, modification time and
  file identity; reference mode copies zero source bytes.
- `evidence/blobs/<sha256>` exists only for explicit `snapshot` evidence or
  `managed` content originally created inside LLM-Kosh.
- FTS, vector, and graph indexes are derived projections and may be rebuilt.
- Evidence and memories are tenant-scoped. Classification and attached ABAC
  grants are checked before any candidate is ranked or returned.
- Candidate memories are excluded from normal retrieval until reviewed.

The local hybrid retriever combines FTS5 BM25 with deterministic token-space
similarity, project fit, confidence, importance, lifecycle authority, and
freshness. The contract allows a local dense-vector projection to replace the
token-space signal later without changing canonical data.

## First migration

Always inspect a dry run first:

```bash
llm-kosh --root ./cartridge brain migrate --dry-run
llm-kosh --root ./cartridge brain migrate
llm-kosh --root ./cartridge brain health
```

Migration preserves every legacy Markdown record as evidence. Deterministically
recognizable decisions, preferences, facts, corrections, questions, tasks, and
outcomes become `candidate` memories. Raw transcripts and unrecognized files
remain evidence-only. Superseded legacy items remain evidence-only unless
`--include-superseded-memories` is explicitly set.

Migration identities derive from legacy source IDs and content hashes, making
repeat runs idempotent.

Legacy files are registered in `reference` mode. Migration does not copy their
bytes into the company-brain evidence store.

## Multimodal artifacts

Artifact type and semantic memory type are deliberately independent. Supported
artifact families include screenshots/images, PDF and DOCX documents, XLSX
worksheets, CSV/TSV, HTML, text/source code, structured data, presentations,
email/chat/transcripts, audio and video. A screenshot is evidence; a decision,
fact, metric or constraint extracted from it is memory.

Register and inspect existing data without copying it:

```bash
llm-kosh --root ./cartridge brain register ./dashboard.png --artifact-type screenshot
llm-kosh --root ./cartridge brain inspect <evidence-id> \
  --locator '{"region":[0.1,0.2,0.8,0.6]}'
llm-kosh --root ./cartridge brain segment <evidence-id> \
  --locator '{"region":[0.1,0.2,0.8,0.6]}'
```

Native locators support text lines, CSV rows, DOCX paragraphs, PDF pages, XLSX
sheet/A1 ranges, HTML heading/text blocks and normalized image regions.

Create an immutable copy only when preservation policy requires it:

```bash
llm-kosh --root ./cartridge brain snapshot <evidence-id>
```

Run the executable storage and citation acceptance checks:

```bash
llm-kosh --root ./cartridge brain evaluate
```

## Review and retrieval

Create a candidate with evidence:

```bash
llm-kosh --root ./cartridge brain remember \
  --type decision \
  --title "Use PostgreSQL for audit events" \
  --statement "Audit events are stored in PostgreSQL for durable JSONB queries." \
  --project audit \
  --classification internal \
  --evidence-file ./architecture-decision.md
```

Review its source, then promote it through the governed lifecycle:

```bash
llm-kosh --root ./cartridge brain review <memory-id> \
  --to verified --principal reviewer --clearance internal --reason "ADR checked"
llm-kosh --root ./cartridge brain review <memory-id> \
  --to active --principal reviewer --clearance internal --reason "Approved"
```

Search and compile context as an explicit principal:

```bash
llm-kosh --root ./cartridge brain search "audit storage" \
  --principal alice --group platform --principal-project audit \
  --project audit --clearance internal --json

llm-kosh --root ./cartridge brain context "Plan the audit service rollout" \
  --principal alice --group platform --principal-project audit \
  --project audit --clearance internal --tokens 6000
```

Context packs contain an executive brief; typed sections for current state,
decisions, constraints, open work, open questions, risks, outcomes, and
procedures; conflict and lifecycle warnings; source citations; retrieval
explanations; bounded observed-activity episode narratives; and token-budget
accounting.

## Session and episode understanding

Schema v3 can turn a registered JSONL session export into bounded normalized
events, source-native sessions, coherent work episodes, and conservative
candidate memories. It reads the registered source in place. It does not copy
the transcript; normalized events contain a redacted summary of at most 2,000
characters plus the exact JSONL line locator.

Preview the graph with no pipeline writes, then persist it explicitly:

```bash
llm-kosh --root ./cartridge brain register ./session.jsonl \
  --artifact-type structured_data
llm-kosh --root ./cartridge brain understand <evidence-id> --dry-run
llm-kosh --root ./cartridge brain understand <evidence-id>
llm-kosh --root ./cartridge brain sessions --project audit
llm-kosh --root ./cartridge brain episodes --query "audit parser"
llm-kosh --root ./cartridge brain episode <episode-id>
```

The deterministic v1 engine recognizes common generic/Codex/Claude-style
message fields, time gaps, project switches, explicit goal changes, handoffs,
and completion transitions. It classifies work phases and extracts only
explicit decisions, constraints, tasks, outcomes, and questions. Extraction is
idempotent, all generated memories remain `candidate`, failures do not advance
the connector checkpoint, and secrets in common key/value forms are redacted
from derived summaries.

The executable graph contract, development prompts, validation prompts, and
exit gates are in `docs/SESSION_EPISODE_ENGINE_SPEC.md`.

## MCP surface and trust boundary

Read operations:

- `company_memory_search`
- `company_context_compile`
- `company_memory_get`
- `company_brain_health`
- `company_brain_evaluate`
- `company_artifact_inspect`
- `company_sessions_list`
- `company_episodes_search`
- `company_episode_get`

Write operations require `--allow-write`:

- `company_memory_propose`
- `company_memory_propose_from_evidence`
- `company_artifact_register`
- `company_artifact_segment`
- `company_artifact_snapshot`
- `company_session_understand`
- `reasoning_ingest`

Lifecycle mutation requires `--allow-mutate`:

- `company_memory_review`

The MCP server remains read-only by default. Client-supplied principal context
is enforced against tenant, classification, principal, group, and project
grants before retrieval.

## Operational safeguards

- Legacy search indexes are built as validated replacement databases and only
  activated after integrity, FTS, cardinality, and source-fingerprint checks.
- `status` inspects index health without rebuilding or starting a daemon.
- Ordinary CLI commands no longer start background services implicitly.
- Watchers ignore SQLite WAL/SHM and partial-download artifacts.
- The causal graph accepts atomic facts of at most 8,000 characters; complete
  documents remain evidence and are not duplicated into graph logs/snapshots.
- Reasoning event logs replay as streams and snapshots are replaced atomically.
- Windows uninstall stops and removes both shipped scheduled-task names before
  uninstalling the Python package.

## Next production increments

This foundation deliberately does not pretend that deterministic segmentation
and local token similarity are a complete company brain. The next increments
are connector adapters and identity sync, model-assisted extraction with
versioned eval gates, entity resolution, cross-episode synthesis, explicit
contradiction and supersession workflows, local embedding projections,
policy-administration UX, retrieval evaluation sets, and authorization/citation
observability. Behavioural or employee scoring remains out of scope unless a
separate governance design explicitly authorizes it.
