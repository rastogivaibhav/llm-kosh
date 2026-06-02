# SECURITY

This tool's whole point is that **nothing leaves your machine unless you pack it**, and a
pack passes safety gates first. This document is the threat model and the guarantees.

## What stays local

Everything. Source, indexes, ledger, packs and the static site are all files under your
cartridge root. There is no network call on any code path. The only optional dependency
(`sentence-transformers`) runs a model locally; it does not phone home.

## The one boundary that matters

The only operation that produces something intended to leave your machine is `pack` /
`safe-pack` / `daily-pack` (you then upload the zip). Both safety gates run there.

### Gate 1 — visibility & policy (before the pack is assembled)

- Memories marked `blocked` are withheld unless you pass `--allow-blocked` (logged).
- Memories marked `quarantine` are never exported.
- `private` is excluded by default; `pack --include-private` opts in. `safe-pack` never
  includes private.
- With `--enforce-policy` (always on for `safe-pack`), only visibilities in
  `allowed_export_visibility` from `KOUSH_POLICY.json` may leave.

### Gate 2 — secret scan (before the zip is written)

The entire assembled pack — every `.md`/`.json`/`.txt`, including the source map and
provider files, not just the copied source — is scanned for secrets:

- private key blocks, AWS keys, Stripe live keys, GitHub tokens/PATs, Slack tokens, Google
  API keys, JWTs, and `keyword: value` assignments (password, api_key, token, secret,
  client_secret, ...).

Default behaviour is **block**: the pack is not written and the offenders are listed.
Options: `--redact` (mask across the whole pack; your source files are never modified) or
`--allow-secrets` (explicit override). Blocked attempts are logged as `context_pack.blocked`.

## safe-pack defaults

`safe-pack` = `pack` with: private excluded, blocked excluded, policy enforced, secret scan
mandatory, redaction ON unless `--no-redact`. Use it when in doubt.

## Helpers

- `classify` flags exportable docs that contain secrets/blocked-terms and suggests
  downgrading them to private (suggest-only unless `--apply`).
- `partition` shows exactly which memories sit in each visibility bucket.
- `quarantine` pulls a risky item out of the export flow non-destructively; `--restore`
  reverses it.
- `audit` reports secrets in source (high severity if the doc is shareable) and
  superseded-but-still-exportable items; `heal --fix-visibility` downgrades them.

## What this does NOT protect against

- **Detector coverage.** The secret scanner is pattern-based and conservative. It catches
  common token shapes and `keyword: value` forms; it will miss bespoke or unlabelled
  secrets. Treat it as a strong safety net, not a guarantee. Review packs of sensitive
  material, and prefer `safe-pack --redact`.
- **What you mark.** Visibility is your classification. If a secret sits in a doc you marked
  `shareable` and it isn't a recognised pattern, gate 1 won't catch it (gate 2 might). Run
  `classify` periodically.
- **After it leaves.** Once you upload a pack to a third-party LLM, that provider's terms
  apply. The tool can't control retention on their side. Pack the minimum you need.
- **Local disk security.** Files are plaintext on your disk by design (so you can read and
  diff them). Use full-disk encryption / file permissions for at-rest protection. Back up
  with `export-backup` and store the backup somewhere you trust.

## Logging

Every superseding, quarantine, classify-apply, policy filter, migration, and blocked-pack
event is appended to `ledger/events.jsonl`. `verify-ledger` checks it for corruption.

## Reporting

This is a personal-use tool with no network surface. If you find a way for data to leave the
machine without an explicit pack/upload, that's a bug worth fixing — it would violate the
core principle.
