# Koush: Changelog

All notable changes to Koush are documented here. The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [1.9.0] - 2026-06-03

### Added
- Import Hardening: Hardened conversational imports into a reversible transaction system.
- New `import` CLI: `detect`, `preview`, `apply`, `rollback`, `list`, `show`, `report`.
- New `migrate` CLI: `check`, `apply`, `rollback`.
- `import apply` saves original payloads to `attachments/imports/<import_id>/` and deduplicates by SHA256.
- Added Koush standardized conversational normalization.

## [1.8.0] - 2026-06-03

### Added
- Self-Healing Daemon OS: Transformed `watch` into a local maintenance runtime.
- New `daemon` commands: `start`, `once`, `status`, `jobs`, `run-job`, `log`, `stop`.
- `watch` command is now deprecated and aliased to `daemon start --mode watchdog`.
- Supports jobs: `scan_intake`, `process_safe_receipts`, `heal_safe`, `audit`, etc.
- Safe auto-apply: Receipts with high-impact or security issues are left for manual review.

## [1.7.0] - 2026-06-03

### Added
- Pack Standard + Conformance Kit: Formalized Koush pack levels 0 through 3.
- `conformance` command group to validate `.koushpack.zip`, `MEMORY_RECEIPT.md`, and cartridge layouts.
- Pack schemas and documentation provided in `spec/conformance/` and `docs/PACK_CONFORMANCE.md`.

## [1.6.0] - 2026-06-03

### Added
- Local Workbench UI: Added `workbench` command to generate a rich, static HTML dashboard (`koush workbench build/serve/open/export/clean`).
- The new dashboard provides visual access to Projects, Decisions, and an active Search interface, entirely locally and without external dependencies.
- Replaced the basic `static-site` command with the new workbench module.

## [1.5.0] - 2026-06-03

### Added
- MCP Production Adapter: Safe extraction of read, write, and mutate capabilities as MCP tools (`mcp-server`, `mcp-tools`, `mcp-test`).

## [1.4.0] - 2026-06-03

### Added
- Declarative Intake Processors: Added `processor` commands for automated, deterministic rule packs that inspect intake items and propose structured memory changes without an LLM.

## [1.3.0] - 2026-06-03

### Added
- Receipt Review + Trust Gate: New commands `validate-receipt`, `review-receipt`, `receipt-diff`, and `trust-receipt` to safeguard memory absorption.
- Added `--review` and `--apply-review` flags to `absorb` to route LLM receipts through a trust gate before executing.
- Persistent markdown review reports generated in `reports/receipt_reviews/` to surface impact and security warnings.

## [1.2.0] - 2026-06-03

### Added
- Intake Control Plane: Centralized management of incoming memories via `intake` commands (`scan`, `list`, `show`, `validate`, `review`, `apply`, `reject`, `quarantine`).
- `intake.schema.json` and `INTAKE_SPEC.md` defining the flow and data structures for intake items.
- Policy flag `intake.auto_apply_receipts` for watchdog daemon behavior.

## [1.0.0] - 2026-06-02

### Added
- **Global Rebranding**: "AI Memory Cartridge" has been officially renamed to **Koush**.
- `koush.spec` replaces `cartridge.spec` for PyInstaller binary generation.
- Desktop UI now officially branded as Koush.
- Added GitHub remote integration (`koush.git`).

### Changed
- The primary configuration file has been migrated from `CARTRIDGE.json` to `KOUSH.json`.
- Policy configurations now use `KOUSH_POLICY.json`.
- The CLI entrypoint has been renamed from `cartridge.py` to `koush_cli.py`.

---

## Historical Versions (AI Memory Cartridge)

Older versions of the product before the Koush rebrand are preserved in the `changelogs/` directory:

- [v1.0.0-rc (Pre-Rebrand)](changelogs/CHANGELOG_v1.md)
- [v0.9.0](changelogs/CHANGELOG_v0.9.md)
- [v0.8.0](changelogs/CHANGELOG_v0.8.md)
- [v0.7.0](changelogs/CHANGELOG_v0.7.md)
- [v0.6.0](changelogs/CHANGELOG_v0.6.md)
- [v0.5.0](changelogs/CHANGELOG_v0.5.md)
- [v0.4.0](changelogs/CHANGELOG_v0.4.md)
- [v0.3.0](changelogs/CHANGELOG_v0.3.md)
- [v0.2.0](changelogs/CHANGELOG_v0.2.md)
