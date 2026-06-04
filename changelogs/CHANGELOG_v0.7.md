# Changelog — v0.7

v0.7 makes it safe to extract only part of the memory. It adds a local export policy,
visibility partitions, quarantine, and a strict `safe-pack`, with leakage prevention as the
explicit design goal. Scope touched pack (to add the visibility/policy gate) but left
importers, absorb, resolve, embeddings, audit and heal alone. All 60 prior tests still pass
(total now 75).

## Partitions

`quarantine` is now a recognised visibility alongside the existing
`private / personal / work-safe / shareable / public / blocked`. Quarantined and blocked
items are excluded from every query that powers an export, so they cannot reach a pack by
the normal path.

## New commands

- `policy [--init]` — show the effective export policy, or write a default
  `LLM_KOSH_POLICY.json`. Policy keys: `default_visibility`, `blocked_terms`,
  `allowed_export_visibility`, `require_redaction`. Missing file ⇒ safe defaults.
- `classify [--apply]` — scans every memory; if a doc contains a secret or a policy
  blocked-term but is marked exportable, it **suggests** downgrading to `private`. Suggest
  only by default; `--apply` enacts and logs each change. Never auto-upgrades anything to
  shareable.
- `partition` — reports how memories split across the visibility buckets, flagging which
  are exportable and which are never exported.
- `quarantine [--id ID] [--restore] [--list]` — moves a risky item out of the export flow
  by setting visibility `quarantine` (recording `prev_visibility`); fully non-destructive
  and reversible with `--restore`. No arg / `--list` lists quarantined items.
- `safe-pack <query> --out …` — `pack` with strict defaults: private excluded, blocked
  excluded, secret scan mandatory, policy enforced, and redaction ON unless `--no-redact`.
  `--allow-blocked` is the only override and is logged.

## Pack changes (for integration)

`pack` gained `--allow-blocked` and `--enforce-policy`. Before assembly it now runs a
visibility gate: blocked items are withheld unless `--allow-blocked`; with
`--enforce-policy`, anything whose visibility isn't in `allowed_export_visibility` is
withheld too. Withheld items are counted in the manifest (`withheld_by_policy`,
`policy_enforced`, `allow_blocked`), surfaced in `09_DO_NOT_ASSUME.md`, and logged as
`policy.export_filtered`. The v0.6 whole-pack secret scan still runs as the final gate, so
safe-pack has two independent defences: visibility/policy filtering *and* secret
scan/redaction.

## Leakage guarantees (all test-enforced)

- private memories never leave through `safe-pack`.
- blocked memories never leave through any pack unless `--allow-blocked` is explicit.
- quarantined memories never appear in an export.
- a shareable doc that still contains a secret is redacted by `safe-pack`.
- every policy/visibility decision is logged to the ledger.
- `classify` only suggests unless `--apply` is passed.

## Files changed / added

- `llm_kosh_cli.py` — added the policy/classify/partition/quarantine/safe-pack module and the
  pack visibility gate; added `quarantine` visibility; excluded blocked/quarantine from
  non-private query results (version → 0.7.0).
- `test_v0_7.py` — 15 new tests.

## Tests

`python3 -m unittest test_cartridge test_v0_3 test_v0_4 test_v0_5 test_v0_6 test_v0_7` → 75
passing (60 prior + 15 new). New tests cover policy defaults/override/init, classify
suggest-vs-apply, partition buckets, quarantine round-trip + non-export, and the six leakage
guarantees above plus policy logging.

## Known limitations

- `classify` term/secret matching is lexical (the same conservative detectors as the secret
  gate); it flags shareable risk but won't infer sensitivity from meaning. Review before
  `--apply` on a large corpus.
- `blocked_terms` is a substring match; very generic terms could over-flag. Tune the list in
  `LLM_KOSH_POLICY.json`.
- Policy applies at export time. It does not retroactively reclassify stored memories — use
  `classify --apply` for that.

## Compatibility

Source format unchanged and backward compatible (`quarantine`/`prev_visibility` are new
optional fields). Cartridges with no `LLM_KOSH_POLICY.json` use safe built-in defaults, so
nothing breaks; `pack` without the new flags behaves as before except that blocked items —
which were always meant to be unexportable — are now actually withheld.
