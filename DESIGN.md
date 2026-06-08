# DESIGN

## One idea

A personal AI memory you own, as files. The cartridge is a folder of human-readable Markdown
with YAML-ish frontmatter (the **source of truth**) plus rebuildable indexes and an
append-only event ledger. Everything else — search, packs, the static site — is derived from
the source and can be regenerated at any time.

## Source of truth vs derived state

| Layer | Where | Truth? | Rebuild |
|-------|-------|--------|---------|
| Memories | `source/**/*.md` | yes | n/a |
| Event ledger | `ledger/events.jsonl` | yes (append-only history) | n/a |
| Config / policy | `LLM_KOSH.json`, `LLM_KOSH_POLICY.json` | yes | n/a |
| FTS index | `indexes/memory.sqlite` | no | `index` / any query |
| Vector index | `indexes/vectors.sqlite` | no | `embed` |
| Memory map | `MEMORY_MAP.md` | no | `memory-map` / `heal` |
| Packs / site | `exports/` | no | `pack` / `static-site` |

The index is rebuilt only when the corpus fingerprint (a hash over relpath + content hash of
every source file) changes, so repeated commands are cheap.

## A memory

```markdown
---
type: decision
id: decision.selectiveos.teacher-approval-queue.1a2b3c4d
title: Teacher approval queue
project: SelectiveOS
visibility: private
status: active
created: "2026-05-29T10:00:00Z"
---

# Teacher approval queue

AI lessons must be teacher-approved before they go student-facing.
```

`type` in {project, decision, prompt, note, file, conversation, receipt, correction, gap,
suggestion}. `status` in {active, superseded, open, inbox, promoted, quarantined, ...}.

## The loop

`pack` selects relevant memories, writes a numbered, ordered set of files (`01_BOOT` ...
`12_MEMORY_RECEIPT_TEMPLATE`) plus a provider-specific context file and the raw source, and
zips it. An LLM boots from it and returns a `MEMORY_RECEIPT`. `absorb` parses that receipt
into typed memories and records provenance (`source_receipt`). A **Correction** supersedes
the memory it corrects: the old one becomes `status=superseded` with a `superseded_by`
backlink and the new one records `supersedes` — non-destructive and reversible. When absorb
can't confidently match a correction it leaves it `open`; `resolve` closes it (manually, by
dismiss, or `--auto`).

### Automated Loop (Watchdog Daemon)
To facilitate zero-overhead local operations, `cartridge watch` boots a filesystem watcher (via `watchdog`). It monitors the `receipts/` directory for any `MEMORY_RECEIPT*.md` files. To ensure absolute data safety and prevent infinite loop triggers, the daemon:
1. Implements a temporary lock/discard set to ignore concurrent `on_created` and `on_modified` write-flushes of the same file.
2. Gracefully waits for file flushes before parsing.
3. Automatically moves successfully processed receipt files into a `receipts/processed/` archive folder. Since the watcher is non-recursive, archiving completely breaks the trigger loop and leaves the workspace pristine.

## Matching

Correction matching and the optional semantic query both use a pluggable similarity layer:
a pure-stdlib **TF-IDF cosine** (default, offline) or **sentence-transformers** dense
embeddings (opt-in, local). 

### High Performance Local Vector DB
If `sqlite-vec` is installed in the python environment, `cartridge` automatically sets up and queries a SQLite-based virtual table (`vec_docs` using the `vec0` virtual table type) and runs native vector cosine distances (`vec_distance_cosine`).
To fulfill our principle of "Python standard-library path always works", `cartridge` implements a robust load-time gate. If the system `sqlite3` does not support compiled extension loading (common on standard system pythons), the system gracefully and transparently falls back to storing vectors as unified serialized JSON `{dim: weight}` dicts and computes cosine similarity directly in Python, maintaining a 100% stable offline-first execution path.


## Packs (compiler v2)

Fixed read order, declared in `01_BOOT.md` and the manifest. `09_DO_NOT_ASSUME.md` lists
open gaps, unresolved corrections, and anything dropped for budget — the explicit
"unproven/missing" surface so the model doesn't invent. `10_SOURCE_MAP.json` links every
included item back to its cartridge id and source path. Profiles tailor the provider file
(compact text for DeepSeek, code emphasis for Codex, narrative for Human). Budgets cap docs
and characters (a token proxy, deliberately conservative).

## Safety model (two independent gates)

1. **Visibility/policy gate** (pre-assembly): blocked never leaves without `--allow-blocked`;
   quarantine never leaves; with `--enforce-policy`, only `allowed_export_visibility` leaves.
   `safe-pack` turns all of this on and excludes private by default.
2. **Secret gate** (pre-zip): scans the whole assembled pack (md/json/txt, including the
   source map and provider files). Blocks by default; `--redact` masks across the entire pack
   while leaving source files untouched; `--allow-secrets` overrides.

Source files are never mutated by packing. All superseding, quarantine, policy and migration
actions are logged to the ledger.

## Self-healing

`audit` reports 14 finding classes (structural, supersession, secret, index-staleness,
ledger integrity, pack manifests). `heal` applies only safe, non-destructive fixes (rebuild
indexes, regenerate BOOT/MEMORY_MAP, assign/repair ids and supersession links) and supports
`--dry-run`, `--write-plan`, `--apply-plan`, and opt-in `--fix-visibility`. It never deletes.

## Backups & migration

`export-backup` zips the source of truth (source + ledger + config + policy + reports +
preserved imports), explicitly **not** the derived indexes. `import-backup` restores and
rebuilds indexes, refusing to overwrite a non-empty cartridge without `--force`. `migrate`
is explicit and reversible: it stamps the app version and ensures a `llm_kosh_id`, recording
the prior version in `migrated_from`, and never rewrites memory content.

## Dependencies

Standard library only on the default path. `sentence-transformers` is the single optional
dependency and is never required; if absent, the `st` backend prints an install hint instead
of failing.
