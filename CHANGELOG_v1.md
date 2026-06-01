# Changelog — v1.0

The stable personal release. v1.0 adds backup/restore/migration and a full documentation
set, and bundles a smoke-demo that runs the entire master-plan workflow end to end. No new
engine behaviour beyond the three backup/migration commands — the command surface was
complete after v0.9. All 106 prior tests still pass (total now 114).

## New commands

- `export-backup --out FILE` — writes a portable backup zip of the **source of truth**
  (`source/`, `ledger/`, `attachments/`, `reports/`, `CARTRIDGE.json`,
  `CARTRIDGE_POLICY.json`, `BOOT.md`, `MEMORY_MAP.md`) with a `BACKUP_MANIFEST.json`.
  Derived indexes are deliberately excluded — they rebuild on restore.
- `import-backup BACKUP [--force]` — restores a backup into a cartridge root and rebuilds
  the FTS index. Refuses to overwrite a cartridge that already has memories unless `--force`.
  Rejects zips that aren't cartridge backups.
- `migrate [--dry-run]` — explicit, reversible migration: stamps the current app version and
  ensures a `cartridge_id`, recording the prior version under `migrated_from`. Never rewrites
  memory content. No-op (and says so) when already current.

## Documentation

- **README.md** — rewritten for real usage: the loop, principles, per-LLM pack instructions
  (ChatGPT/Claude/Gemini/DeepSeek/Codex/human), the full command surface table, layout.
- **QUICKSTART.md** — 10-minute path from `init` to a working absorb loop and backup.
- **DESIGN.md** — architecture: source-of-truth vs derived state, the memory schema, the
  loop, the matching layer, pack compiler v2, the two-gate safety model, self-healing,
  backups/migration.
- **SECURITY.md** — threat model and guarantees: what stays local, the two export gates,
  `safe-pack` defaults, detector coverage limits, and what the tool does *not* protect
  against.
- **EXAMPLES.md** — copy-paste recipes for every workflow.

## Smoke demo

`smoke_demo.sh [root]` runs the master-plan workflow against a throwaway cartridge:
init → import-chatgpt (bundled fixture) → add decision → embed → pack → validate-pack →
explain-pack → absorb a simulated MEMORY_RECEIPT → resolve → audit → heal --safe → today →
daily-pack → static-site → export-backup. Exits non-zero on any failure. Verified passing.

## Files changed / added

- `cartridge.py` — added `export_backup`, `import_backup`, `migrate` and their subcommands
  (version → 1.0.0).
- `README.md` (rewritten), `QUICKSTART.md`, `DESIGN.md`, `SECURITY.md`, `EXAMPLES.md` (new).
- `smoke_demo.sh` (new), `test_v1_0.py` (8 new tests).

## Tests

`python3 -m unittest test_cartridge test_v0_3 test_v0_4 test_v0_5 test_v0_6 test_v0_7 test_v0_8 test_v0_9 test_v1_0`
→ 114 passing (106 prior + 8 new). New tests cover: backup contains source but not derived
indexes; backup→restore round-trip with working query and preserved cartridge_id;
import refuses a non-empty target without `--force` and overwrites with it; non-backup zip
rejected; migrate stamps version + cartridge_id and records history; migrate `--dry-run`
changes nothing; migrate no-op when current.

## v1.0 quality bar (from the master plan)

- All old tests pass — yes (114 total).
- No internet required; no optional dependency required — yes. The `st` path remains
  available but optional.
- Secret gate remains strict; source format backward compatible — yes.
- Migration is explicit and reversible — yes (`migrate`, `migrated_from`).
- Every command has `--help`; errors are human-readable (SystemExit messages, not
  stack traces, on the expected failure paths).
- README explains uploading packs to ChatGPT/Claude/Gemini/DeepSeek/Codex — yes.

## Known limitations

- `import-backup --force` replaces files present in the backup; it does not delete files
  that exist only in the target. For a clean restore, point it at a fresh root.
- `migrate` covers the v0.x→1.0 line (version stamp + cartridge_id). There's no schema
  rewrite because the on-disk format has stayed backward compatible throughout; future
  breaking changes would extend `migrate` with explicit, reversible steps.
- The smoke demo shells out with `bash`; on Windows run the equivalent commands from
  `EXAMPLES.md` or use WSL.
- Secret detection remains pattern-based (see SECURITY.md) — a strong net, not a proof.

## Compatibility

Source format unchanged and backward compatible across all versions. Older cartridges work
as-is; run `migrate` once to stamp v1.0.0 and (if needed) add a `cartridge_id`. Backups are
forward-compatible: a backup carries its `app_version` so a restore knows what made it.
