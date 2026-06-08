# Changelog — v0.3

v0.3 fixes the four things flagged after v0.2: the correction-matching **gap**,
**self-heal**, **querying**, and **extraction**. Still zero third-party dependencies.

## 1. The gap — TF-IDF correction matching

v0.2 matched corrections to existing memories with raw token overlap, which punted to
"open" far too often. v0.3 adds a pure-stdlib **TF-IDF cosine** similarity engine
(`tokenize` / `best_match`) used when a correction has no explicit `[ref:]`. It now
matches paraphrases that share distinctive terms (e.g. a correction about the
"recommendation ranking backend" finds the decision that adopted pgvector for it), while
still leaving genuinely unrelated corrections open. Every match records a `match_score`
in the new memory's frontmatter and in the ledger, so the decision is auditable; the
acceptance threshold (default 0.18) is one constant to tune.

## 2. Self-heal — real, non-destructive repairs

`heal` was cosmetic (rebuild index + memory map). It now repairs structure and reconciles
the supersession graph, all logged and reversible (it only edits frontmatter; it never
deletes a file):

- assigns a missing `id`; infers a missing `type` from the folder
- regenerates duplicate `id`s
- repairs supersession **reciprocity** both ways (if A supersedes B, B is marked
  `superseded_by: A` and retired; if B points to A, A's `supersedes` is back-filled)
- clears **dangling** `superseded_by` links and reactivates the orphaned memory
- `--fix-visibility` (opt-in) downgrades shareable docs that contain secrets to private

Use `heal --dry-run` to preview every repair before applying it.

## 3. Querying — recall pool + TF-IDF re-rank + filters

`query` now pulls a wider FTS candidate pool for recall, then **re-ranks** by TF-IDF
cosine (title weighted above body) for precision, so multi-term queries surface the most
relevant memory first. Results carry a `score`. New filters: `--kind a,b`, `--project`,
`--status`. Snippets now center on the densest window of query-term hits instead of the
first single hit.

## 4. Extraction — structured ingestion

`ingest` was "read a few text extensions, dump one blob, truncate at 20k chars." It now:

- splits markdown into one memory per `#`/`##` section (titled `file.md: Heading`);
  `--no-split` keeps a file whole
- chunks large headingless files on line boundaries instead of truncating
- **dedupes** by content hash (`source_hash`) — re-ingesting the same file adds nothing
- captures metadata (`source_path`, `source_hash`, `bytes`, `ingested_at`)
- skips binaries/unknown types cleanly and reports counts (added / duplicates / non-text)
- recognises many more text/code extensions

## New / changed CLI flags

- `query ... --kind a,b --project NAME --status active`
- `heal --dry-run --fix-visibility`
- `ingest ... --no-split`

## Tests

`python3 -m unittest test_cartridge test_v0_3` — 25 tests, standard library only.
v0.3 adds 14 covering TF-IDF matching (paraphrase + negative + scoring), query re-rank and
filters, the four heal repairs (with dry-run), and extraction (split, dedupe, binary skip,
metadata, chunking).

## Compatibility

Unchanged on-disk format; v0 and v0.2 cartridges work as-is. Running `heal` once will
back-fill ids/types and reconcile any supersession links created by hand.
