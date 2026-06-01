# Changelog — v0.8

v0.8 turns audit/heal into a real self-healing layer: a broad set of audit findings, a
human-readable repair plan you can review and apply, and `verify-ledger` / `memory-map`.
Nothing is ever auto-deleted. All 75 prior tests still pass (total now 95).

## Audit v2

`audit` now detects: missing frontmatter / id, duplicate ids, duplicate titles (within a
kind+project), secrets in source (high if shareable), dangling `superseded_by`, superseded
items still marked exportable, generated-file records with no `attached_file`/source,
open corrections, unresolved suggestions, missing `BOOT.md`, a stale FTS index, an
out-of-date vector index, corrupt ledger rows, and export packs missing a manifest. The
report is grouped by severity and written to `reports/AUDIT_REPORT.{json,md}` with a
`by_type` summary.

**Hardening fix:** rebuilding the index used to crash on a duplicate id (the `documents.id`
primary-key collision) — which meant audit could never actually report that corruption.
Indexing now survives duplicate ids (first wins; later collisions are suffixed internally)
so audit reports `duplicate_id` instead of throwing. This makes the whole tool more robust,
not just audit.

## Heal v2

`heal` modes:
- `--dry-run` — show every repair, change nothing.
- `--safe` (default) — safe automatic fixes only.
- `--write-plan` — write `reports/REPAIR_PLAN.{json,md}` and exit without changes.
- `--apply-plan <file>` — apply a previously written plan, restricted to its listed paths.
- `--fix-visibility` — opt-in: downgrade shareable secret-containing docs to private, and
  mark superseded-but-exportable docs private.

Safe automatic fixes: rebuild FTS index; rebuild the vector index if one exists; regenerate
`MEMORY_MAP.md`; regenerate `BOOT.md` if missing; infer missing type from folder; assign
missing ids; regenerate duplicate ids; repair supersession reciprocity; clear dangling
supersede links. **No auto-delete** — every fix edits frontmatter or rebuilds a derived
artifact, all logged and reversible.

## New commands

- `verify-ledger` — checks every ledger row is valid JSON with required fields; reports bad
  line numbers.
- `memory-map` — regenerates `MEMORY_MAP.md` showing projects, active decisions, open
  corrections, open gaps, recent receipts, export packs, and index health (FTS + vector).
- `repair-plan` — writes the human-readable repair plan (same as `heal --write-plan`).

## Files changed / added

- `cartridge.py` — rewrote `audit`/`heal_safe`; added `verify_ledger`, `memory_map`,
  `build_repair_plan`/`write_repair_plan`, `index_is_stale`, `vector_index_stale`,
  `boot_text`; hardened `rebuild_index` against duplicate ids (version → 0.8.0).
- `test_v0_8.py` — 20 new tests.

## Tests

`python3 -m unittest test_cartridge test_v0_3 test_v0_4 test_v0_5 test_v0_6 test_v0_7 test_v0_8`
→ 95 passing (75 prior + 20 new). New tests cover each audit finding (missing frontmatter,
duplicate id, duplicate title, secret-in-shareable, dangling/exportable supersession, open
correction, missing BOOT, stale FTS, stale vector, generated-file-without-source, corrupt
ledger), `verify-ledger`, heal dry-run/safe, no-delete guarantee, write-plan→apply-plan
round-trip, repair-plan readability, and memory-map sections.

## Known limitations

- Open corrections, unresolved suggestions, and generated-file-without-source are surfaced
  as advisories, not auto-fixed — they need human judgement (use `resolve`/`promote`).
- `--apply-plan` matches plan actions by path; if you edit the source tree between
  write-plan and apply-plan, regenerate the plan.
- Duplicate-title detection is exact (case-insensitive) within kind+project; near-duplicate
  titles aren't flagged.
- The vector-index freshness check compares document counts, not per-document hashes; an
  edit that doesn't change the count won't be flagged until you re-`embed` (heal rebuilds it
  anyway when a vector index exists).

## Compatibility

Source format unchanged. `MEMORY_MAP.md` is the new canonical map filename; the legacy
`MEMORY.map.md` is still written for older references. Older cartridges audit/heal without
migration.
