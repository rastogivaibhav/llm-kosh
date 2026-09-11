# llm-kosh v2.1.1 — Hardening Release

## Fixed
- **Daemon root mismatch (critical):** the auto-spawned daemon ignored the CLI's
  `--root` and always targeted `~/.llmkosh/cartridge`, so it either died on a
  missing root or silently watched the wrong cartridge. `maybe_spawn(root)` now
  forwards the active root via `LLMKOSH_ROOT`, and `ServiceRunner.run()` honors it.
- **3-second CLI stall:** every CLI command polled a daemon that could never start.
  A failed spawn now writes a 10-minute cooldown marker (`~/.llmkosh/spawn_failed`)
  so subsequent commands skip the wait. Test suite runtime: 191s → 12s.
- **Daemon exit code:** invalid cartridge root now logs a clear error and exits 1
  (was: warning + useless run loop).
- **Frontmatter list round-trip:** `frontmatter({"tags": [...]})` serialized lists
  as JSON but `parse_frontmatter` returned them as strings. Lists now round-trip.
- **Test infra:** added `asyncio_mode = "auto"` + marker registration to
  pyproject.toml (11 MCP tests were failing for lack of it); the real-cartridge
  integration test now respects `LLM_KOSH_REAL_CARTRIDGE` env var and skips
  gracefully instead of failing on machines without the hardcoded Windows path.

## Added
- **Tamper-evident hash-chained ledger:** every `append_ledger` row now carries
  `prev` (hash of the previous row, genesis-anchored) and `row_hash` (canonical
  SHA-256 of the row). Appends are advisory-locked (fcntl/msvcrt), flushed, and
  fsynced; the chain head is cached in `ledger/CHAIN_HEAD`.
- **Chain verification in `verify-ledger`:** recomputes every row hash and checks
  link integrity. Detects silent payload edits (`row_hash_mismatch`) and silent
  row deletion/reordering (`broken_link`). Pre-2.1.1 rows are counted as `legacy`
  and remain valid — no migration required.
- **Regression suite:** `tests/test_ledger_hardening.py` (8 tests) covering chain
  fields, tamper detection, deletion detection, legacy compatibility, 4-process
  concurrent append safety, and frontmatter round-trip.

## Test status
579 passed, 8 skipped, 0 failed (was 561/11/7).
