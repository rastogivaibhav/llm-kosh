# Changelog — v0.9

v0.9 adds personal-workflow polish so the cartridge is usable daily without a full app. Six
new commands, all additive — pack, absorb, resolve, embeddings, audit/heal, importers and
the safety layer are untouched. All 95 prior tests still pass (total now 106).

## New commands

- `today [--days N]` — glanceable status: recent memories, inbox count, open gaps, open
  corrections (with ids), and latest export packs.
- `inbox [text] [--project P]` — quick capture. With text, saves a note flagged
  `status=inbox` for later review; without, lists pending inbox items and how to promote
  them.
- `promote --id ID --to decision|prompt|project|gap|note [--title T] [--project P]` — turns
  a captured note/suggestion into a typed memory. Non-destructive: the original is marked
  `status=promoted` with a `promoted_to` link, and the new item records `promoted_from`.
- `receipt-template` — prints the canonical MEMORY_RECEIPT format (handy to paste into an
  LLM chat).
- `daily-pack --out FILE [--budget small|medium|large] [--include-private]` — a small,
  uploadable pack of active projects and open decisions/gaps, built on the v0.6 pack
  compiler with the `human` handover profile.
- `static-site [--include-private]` — generates a local static HTML dashboard under
  `exports/site/`: `index.html` with client-side search, per-project pages, per-decision
  pages, plus `search.json` / `search.js` / `style.css`.

## static-site details

- **stdlib only, no framework, no server.** Search is ~10 lines of vanilla JS over a static
  `search.json`; everything opens from `file://`. No React/Vue/Angular, no CDN, no external
  `https://` references (test-enforced).
- **Private-safe by default.** Private/blocked/quarantine memories are excluded unless
  `--include-private` is passed; the index page reports how many were withheld.

## Files changed / added

- `cartridge.py` — added the v0.9 workflow module (`today`, `inbox`, `promote`,
  `receipt_template`, `daily_pack`, `static_site`, plus helpers) and six subcommands
  (version → 0.9.0).
- `test_v0_9.py` — 11 new tests.

## Tests

`python3 -m unittest test_cartridge test_v0_3 test_v0_4 test_v0_5 test_v0_6 test_v0_7 test_v0_8 test_v0_9`
→ 106 passing (95 prior + 11 new). New tests cover: inbox capture/list and status flag;
promote note→decision (non-destructive, with back/forward links) and missing-id error;
today reporting gaps/corrections/inbox; receipt-template text; daily-pack produces an
uploadable zip (BOOT + manifest); static-site generates local files and valid search.json;
private excluded by default and included with the flag; and the no-framework/offline
guarantee.

## Known limitations

- `static-site` is read-only and regenerates from scratch each run (it deletes and rebuilds
  `exports/site/`). Re-run after changes; it is not incremental.
- Client-side search is a simple substring match over title/project/kind, not the FTS/vector
  index — adequate for a personal dashboard, not a full search UI.
- `today` "recent" uses the `created` timestamp; hand-edited or imported items without a
  `created` field are treated as recent.
- `promote` copies the body forward; it does not transform phrasing (a captured note becomes
  a decision verbatim — edit afterward if needed).

## Compatibility

Source format unchanged; `inbox`/`promoted` statuses and `promoted_from`/`promoted_to` are
new optional fields. The site is written under `exports/`, which is already gitignored in
the shipped `.gitignore`.
