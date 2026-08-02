# Session and episode understanding engine

Status: executable implementation contract for company-brain schema v3.

## Goal

Convert registered AI session artifacts into bounded normalized events,
source-native sessions, coherent goal-oriented episodes and evidence-backed
candidate memories. Original transcripts remain reference-only artifacts.

## Non-goals

- No behavioural or employee scoring.
- No automatic promotion of extracted candidates to verified truth.
- No storage of complete messages, system prompts or tool output in events.
- No model requirement; this milestone is deterministic and locally testable.
- No claims of causation based only on event order.

## Canonical contracts

### Normalized event

Required fields: deterministic event ID, tenant, source type/native ID, session
ID, actor type/ID, event type, role, occurred time, evidence/segment reference,
native locator, bounded semantic summary, project candidates, entities,
classification, access policy and ingestion run.

Event types: `message`, `tool_call`, `tool_result`, `file_change`, `commit`,
`ticket_change`, `document_change`, `handoff`, `checkpoint`, `system`, `other`.

System instructions and large tool results remain evidence but are excluded
from semantic candidate extraction.

### Session

A source-native interaction window with project, participants, start/end,
status, evidence IDs, event count and connector metadata. Session identity is
deterministic from tenant, source type and source-native session ID.

### Episode

A coherent unit of intent with a semantic title, goal, project, participants,
start/end, status, outcome narrative, session/evidence IDs, event membership,
phase summary, boundary signals, confidence and access policy.

Boundary signals: time gap, project change, explicit new user goal, completion,
blocking, rollback and agent handoff. Topic similarity is deterministic token
overlap in v1; model-assisted segmentation may be added as a versioned
projection later.

### Extraction

Deterministic candidates cover explicit decisions, constraints, tasks, outcomes
and unresolved questions. Every candidate must cite a normalized event segment,
remain `candidate`, identify extractor/run version and pass existing atomic
memory validation. Reprocessing the same evidence and pipeline version is
idempotent.

## Engineering graph prompts

### Graph 1 — schema v3

Development prompt: add normalized events, sessions, episode membership,
checkpoints, extraction runs and episode-memory provenance using additive,
transactional migrations.

Validation prompt: upgrade v2 stores, enforce foreign keys, deterministic
identity and idempotent replay without changing evidence bytes.

Exit gate: v2 data remains readable; replay produces no duplicate canonical
rows.

### Graph 2 — normalizers

Development prompt: stream JSONL session artifacts, accept common Codex/Claude
and generic event shapes, preserve exact line/message locators, cap summaries,
and classify event/actor/project fields without persisting raw payloads.

Validation prompt: malformed JSON, overlong lines, Unicode, missing IDs/times,
system prompts, tool output and mutation during processing.

Exit gate: every stored event is bounded and evidence-addressable.

### Graph 3 — segmentation

Development prompt: group source sessions and segment episodes using time,
project, explicit-goal, lifecycle and topic signals; classify work phases and
produce concise evidence-linked narratives.

Validation prompt: one goal, multiple goals, long gaps, project switches,
handoffs, blocked work, rollback and deterministic replay.

Exit gate: gold fixtures meet boundary and status expectations.

### Graph 4 — extraction

Development prompt: extract only explicit atomic decisions, constraints, tasks,
outcomes and questions; create segments and candidate memories with run
provenance; create project/system entities only from deterministic signals.

Validation prompt: reject system prompts, raw tool dumps, UUID titles,
multi-claim text, unsupported causation and candidates without evidence.

Exit gate: precision-oriented fixtures pass and no candidate is authoritative.

### Graph 5 — retrieval/context

Development prompt: add authorized episode search and token-budgeted episode
narratives to context packs alongside existing memories and attachments.

Validation prompt: ACL isolation, unavailable evidence, historical status,
budget enforcement and citation completeness.

Exit gate: episode context is useful, bounded and fully cited.

### Graph 6 — orchestration

Development prompt: expose dry-run normalize/understand plus session/episode
read APIs through CLI and capability-gated MCP. Persist checkpoints only after
durable completion.

Validation prompt: dry runs cause no canonical writes; failures do not advance
checkpoints; repeated successful runs are idempotent.

Exit gate: a registered JSONL session becomes queryable episodes and candidates
through one explicit command.

### Graph 7 — evaluation

Development prompt: publish boundary, extraction, provenance, idempotency,
storage-amplification and permission metrics with representative fixtures.

Validation prompt: adversarial and complete regression suites plus an
end-to-end reference-only session smoke test.

Exit gate: zero transcript-copy amplification, all candidates cited, all tests
green and documentation matches the executable interface.

## Graph execution model

```text
G1 schema -----------+------------------------------+
                    |                              |
G2 normalize -------+--> G3 segment --> G4 extract+--> G5 retrieve/context
                    |                              |              |
                    +----------> G6 orchestrate <--+--------------+
                                           |
                                           v
                                      G7 evaluate
```

Nodes are replayable build units, not background autonomous loops. A node may
start only when all incoming contracts are green. Any failed validation routes
back to the node that owns the violated contract. Checkpoints are outputs of a
successful G6 transaction and are never inputs that can override canonical
evidence identity.

Every engineering prompt uses this envelope:

1. Role: name the component boundary, not a persona.
2. Objective: one measurable state transition.
3. Inputs: exact schema/API versions and upstream node outputs.
4. Invariants: reference-only source, ACL inheritance, bounded derived text,
   deterministic IDs, idempotency, and candidate-only extraction.
5. Work: implementation files and permitted migrations.
6. Adversarial tests: malformed data, authorization, mutation, replay and
   resource bounds.
7. Output: changed contracts, migration notes, metrics, known limitations and
   exact validation commands.
8. Exit decision: `pass`, `revise:<owner-node>` or `blocked:<external-input>`.

## Built graph status

| Node | Implementation | Validation gate |
|---|---|---|
| G1 | schema v3 sessions, events, membership, runs, provenance, checkpoints | additive v2 upgrade and replay fixtures |
| G2 | streaming JSONL normalizer with native line locators and secret redaction | malformed/overlong/reference fixtures |
| G3 | time/project/goal/handoff/completion boundaries and phase classification | multi-goal and status fixtures |
| G4 | explicit decision/constraint/task/outcome/question candidates | segment citation and candidate-only lifecycle checks |
| G5 | authorized episode search and token-budgeted context narratives | ACL, evidence availability and budget fixtures |
| G6 | CLI and capability-gated MCP orchestration | dry-run, checkpoint and interface fixtures |
| G7 | health/evaluate metrics for graph and provenance integrity | focused plus complete regression suite |

## Acceptance metrics

- Source-copy amplification for reference evidence: exactly `0` bytes.
- Stored event summary: at most 2,000 characters; input line: at most 1 MiB.
- Candidate citation completeness: 100 percent.
- Episode membership integrity: zero orphan events.
- Replay duplication: zero additional canonical sessions, events, episodes,
  memories or extraction runs for an unchanged source/pipeline pair.
- Dry-run canonical writes and checkpoint movement: zero.
- Authorization leakage in session, episode, memory and context reads: zero in
  the policy fixtures.
- Checkpoint advancement after failed extraction: zero.

## Next graph: cross-session company understanding

This is the prompt structure for the next implementation cycle after the
deterministic session engine. It must remain a versioned projection over the v3
canonical records.

### N1 - connector adapter contract

Development prompt: define a connector SDK that streams source-native events
from Codex, Claude, email and ticket exports into the existing normalized-event
contract. Store cursor/checkpoint state only after canonical commit. Do not add
connector-specific columns to canonical tables; preserve opaque native locators
and connector version metadata.

Validation prompt: run contract fixtures for pagination, retry, duplicate
delivery, deleted/moved source, partial page, clock skew, identity collision and
least-privilege scope. Prove identical native input produces identical event
IDs across restart.

Exit gate: two adapters pass the same fixture suite without canonical schema
changes or source-byte copying.

### N2 - identity and entity resolution

Development prompt: create versioned candidate links for people, agents,
projects, repositories, systems and customers using exact identifiers first,
then bounded alias evidence. Never merge entities destructively. A merge is a
reviewable relation with supporting event/evidence IDs and reversible status.

Validation prompt: homonyms, renamed repositories, shared email aliases,
cross-tenant identifiers, bot/person ambiguity and merge rollback.

Exit gate: precision target at least 0.98 on exact-identity fixtures; every
probabilistic link is reviewable and reversible.

### N3 - model-assisted semantic extraction in shadow mode

Development prompt: add a provider-neutral extractor interface that consumes
only authorized bounded episode packets and returns schema-validated candidate
memories, entities and relations. Record prompt version, model, parameters,
input event IDs and output hash. Run in shadow mode beside deterministic v1;
never auto-promote memory.

Validation prompt: prompt injection in transcripts, unsupported causal claims,
secret reproduction, multi-claim output, citation mismatch, nondeterministic
replay and provider failure. Compare precision/recall with deterministic v1 on
a human-labelled set.

Exit gate: citation precision 1.0, atomicity at least 0.95 and no candidate
promotion or checkpoint advancement on invalid output.

### N4 - contradiction, supersession and temporal truth

Development prompt: derive candidate `CONTRADICTS`, `SUPERSEDES` and `CONFIRMS`
relations from atomic memories only. Separate observation time from validity
time. Require direct evidence for automatic candidate relations and review for
any lifecycle mutation.

Validation prompt: changed decisions, temporary exceptions, scope differences,
duplicate wording, stale facts and contradictory sources with different ACLs.

Exit gate: no cross-policy relation leaks; current-state queries preserve the
full historical chain and explain why one item is current.

### N5 - cross-episode synthesis

Development prompt: construct bounded project narratives from authorized
episodes and reviewed atomic memories: goals, milestones, decisions, blockers,
outcomes and unresolved work. Synthesis is a disposable projection carrying all
input IDs, build version and an authority label; it is not canonical truth.

Validation prompt: project collision, mixed classifications, missing evidence,
conflicting episodes, budget pressure and historical `as_of` queries.

Exit gate: every narrative sentence maps to at least one visible canonical ID;
removing access to an input removes its contribution on rebuild.

### N6 - retrieval projection and evaluation harness

Development prompt: add local embedding and graph projections behind the
existing permission-first candidate set. Publish golden task/evidence pairs and
measure retrieval, context utility, citation correctness, latency and storage
amplification per build version.

Validation prompt: compare lexical baseline, embedding, graph and fusion
ablation runs; include negative ACL queries and changed-reference failures.

Exit gate: improve labelled recall without reducing citation precision or ACL
isolation, and keep all projections rebuildable from canonical v3 records.
