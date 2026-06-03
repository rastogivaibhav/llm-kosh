# Changelog — v0.6

v0.6 rewrites the context-pack compiler so exports feel intentionally **bootable** rather
than a zip of search hits. Scope was limited to packs plus the cartridge-id needed to stamp
them; importers, absorb, resolve, embeddings, audit and heal are untouched. All 45 prior
tests still pass (total now 60).

## Pack structure v2

`pack` now emits a fixed, ordered layout the LLM is told to read top to bottom:

```
01_BOOT.md                02_CONTEXT_BRIEF.md     03_TASK_CONTEXT.md
04_MATCHED_MEMORY.md      05_DECISIONS.md         06_OPEN_GAPS.md
07_PROMPTS.md             08_GENERATED_FILES.md   09_DO_NOT_ASSUME.md
10_SOURCE_MAP.json        11_MANIFEST.json        12_MEMORY_RECEIPT_TEMPLATE.md
provider/<PROFILE>_CONTEXT.(md|txt)
source-files/
```

- **01_BOOT.md** instructs the model to read 01→12 in order and states the rules
  (decisions are settled; don't assume anything in 09; trace claims to 10).
- **09_DO_NOT_ASSUME.md** lists open gaps, unresolved corrections, and any items dropped for
  budget — the explicit "unproven / missing" surface.
- **10_SOURCE_MAP.json** links every item back to its cartridge `id` and `source_path`, and
  records whether it was included and why not.
- **11_MANIFEST.json** (schema `ai-memory-context-pack.v1`) includes target, query,
  timestamp, redaction status, match count, cartridge id + version, budget, and char usage.

## Profiles

`--for chatgpt|claude|gemini|deepseek|codex|human` each generate a tailored
`provider/` file:
- **deepseek** → compact plain-text `.txt`.
- **codex** → emphasises projects + engineering decisions as binding constraints.
- **human** → a handover narrative for a person picking up the work.
- **chatgpt / claude / gemini** → standard markdown context view.

## Budgets

- `--budget small|medium|large` presets (docs + char caps; default medium).
- `--max-docs N` and `--max-chars N` override the preset.
- Over-budget documents are truncated with a marker or omitted; omissions are surfaced in
  09_DO_NOT_ASSUME.md and counted in the manifest. Pack output reports chars used / budget
  and final zip size.

## New commands

- `validate-pack <zip>` — checks all 12 required files exist, the manifest has the required
  keys and is valid JSON, and every source-map entry links back to an id + source_path.
  Exits non-zero on failure.
- `explain-pack <zip>` — prints target, query, cartridge id/version, redaction status,
  matched/included counts, char budget, read order, and the included items.

## Cartridge identity

New cartridges get a `koush_id` in `KOUSH.json`. Pre-v0.6 cartridges (no id) get a
**deterministic, stable** id derived from owner + created_at at pack time — no file is
mutated, so it stays backward compatible and reversible.

## Security

The secret gate is unchanged in strictness but now scans the **entire assembled pack
directory** (all `.md`/`.json`/`.txt`, including provider files and the source map) before
zipping. Default is still block; `--redact` masks across the whole pack (source untouched);
`--allow-secrets` overrides. Blocked packs write nothing and log `context_pack.blocked`.

## Files changed / added

- `koush_cli.py` — rewrote `pack_context`; added `validate_pack`, `explain_pack`,
  `cartridge_meta`, profile/budget helpers; `koush_id` in init (version → 0.6.0).
- `test_v0_6.py` — 15 new tests.

## Tests

`python3 -m unittest test_cartridge test_v0_3 test_v0_4 test_v0_5 test_v0_6` → 60 passing
(45 prior + 15 new). New tests cover: all 12 required files present; manifest + source-map
contracts; boot read-order; DO_NOT_ASSUME lists open gaps; all six profile files generated
(human=handover, codex=projects); small budget caps docs; max-chars enforced;
validate-pack pass/fail; explain-pass; secret block and redact.

## Known limitations

- Char budget is a proxy for tokens (no tokenizer dependency); it's deliberately
  conservative, not exact per-model token accounting.
- Open gaps / corrections in 06 and 09 are matched by query relevance plus a kind filter;
  a gap unrelated to the query may not appear. Tune with broader queries if needed.
- `validate-pack` checks structure and manifest/source-map integrity, not semantic quality
  of the selected memories.

## Compatibility

Source format unchanged; older cartridges pack without migration (id derived
deterministically). Pack schema bumped to `…pack.v1`; consumers keying on the old flat
`MANIFEST.json`/`05_SOURCE_MAP.json` names should read the new numbered files.
