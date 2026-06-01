# Changelog — v0.5

v0.5 adds real conversation importers so the cartridge can be seeded from actual
ChatGPT, Claude, Gemini and generic exports. Scope was deliberately limited to import:
pack, resolve, embeddings, audit and heal are untouched. All 34 prior tests still pass.

## New commands

- `import-chatgpt <zip|folder|file>` — ChatGPT export (`conversations.json`; tree `mapping`
  is linearised by walking parent→children, with a time-ordered fallback).
- `import-claude <zip|folder|file>` — Claude export (`chat_messages` with `text` or
  `content[].text`; `human`/`assistant` senders).
- `import-gemini <zip|folder|file>` — Google Takeout "My Activity" JSON for Gemini/Bard
  (each Gemini-headed activity record becomes a single-prompt conversation; non-Gemini
  records are filtered out).
- `import-generic <file|folder>` — `.md`/`.txt` transcripts (split on `User:` / `Assistant:`
  style speaker labels; whole-file note if none) and generic `.json` (auto-detects a
  ChatGPT/Claude shape, otherwise a list of `{role|sender, text|content}`).
- `import-report [--import-id ID]` — print import report(s); default lists all imports on
  record and shows the most recent report.

All importers support `--project`, `--visibility` (default `private`), `--limit`, and
`--dry-run`.

## Behaviour

- **Raw preservation.** The original zip/file/folder is copied verbatim into
  `attachments/imports/<import_id>/` and never mutated or deleted.
- **Typed records only.** One human-readable `conversation` record per conversation is
  written under `source/conversations/`. No decisions, prompts or projects are invented
  from imports (explicit non-goal: no hallucinated decisions).
- **Provenance frontmatter** on every record: `provider`, `import_id`, `source_file`,
  `conversation_title`, `conversation_date` (when available), `message_count`, `source_hash`.
- **Import report** written to `reports/imports/<import_id>.{md,json}` summarising provider,
  source, status, conversations, message counts, preserved-raw path, and any skipped files.
- **Ledger events**: `import.started`, then `import.completed` (or `import.failed` when
  nothing parsed).
- **Graceful failure.** Malformed JSON, HTML-only exports, or unrecognised structures
  produce a clear status (`empty` / `no_conversations`) and a report — never a stack trace.
- **`--dry-run`** previews counts and titles and writes nothing (no records, no raw copy,
  no ledger, no report).

## Integration notes

Imported `conversation` records are ordinary source files, so the existing FTS index and
`query` pick them up automatically (e.g. `query "teacher approval"` returns an imported
chat). No changes were needed to pack/resolve/embeddings/audit/heal.

## Files changed / added

- `cartridge.py` — added the importer module and five subcommands (version → 0.5.0).
- `test_v0_5.py` — 11 new tests.
- `fixtures/` — synthetic sample exports for each provider (no real user data).

## Tests

`python3 -m unittest test_cartridge test_v0_3 test_v0_4 test_v0_5` → 45 tests, all passing
(34 prior + 11 new). New tests cover: ChatGPT dry-run writes nothing; real ChatGPT import
with provenance + raw preservation + searchability; report and ledger events; Claude;
Gemini (with non-Gemini record filtered); generic markdown and generic JSON; `--limit` and
`--visibility`; malformed and unknown-structure graceful handling; the `import-report`
command.

## Known limitations

- **Gemini**: Takeout activity JSON rarely separates the model's reply, so a Gemini import
  captures prompts as single-message conversations. HTML "My Activity" exports are not
  parsed (the report tells the user to export JSON). Recommend exporting JSON from Takeout.
- **No candidate extraction yet**: imports do not auto-suggest decisions/prompts/projects.
  This is intentional for v0.5 (avoids hallucinated decisions); a conservative, opt-in
  heuristic could come later.
- **Generic HTML** files are reported as skipped rather than scraped.
- Large exports are imported in full into memory; chunking very large single conversations
  is not yet done (the `ingest` path already chunks files, but importers store one record
  per conversation).

## Compatibility

On-disk source format unchanged and backward compatible; `conversation` was already a
supported kind. The vector index, if built, should be rebuilt (`embed`) after a large
import to include the new records in semantic search.
