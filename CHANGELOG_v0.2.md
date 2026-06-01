# Changelog — v0.2

v0 was a one-way exporter: it could emit context packs but couldn't fold an LLM's
output back into structured memory, and the only operation that sent data off the
machine (`pack`) had no secret screening. v0.2 closes the loop and the trust hole.

## 1. `absorb` is real now

In v0, `absorb` stored the whole receipt as one opaque blob, so the
Boot → Work → Receipt → Absorb loop never actually updated memory. v0.2 parses a
`MEMORY_RECEIPT` into **typed** memories and records **provenance** — every item
created from a receipt carries a `source_receipt` field linking back to it.

- New decisions → `decision` memories
- Corrections → applied as supersessions (see below)
- Generated files → `file` memories
- Open gaps → `gap` memories (status `open`)
- Suggested memory updates → `suggestion` memories (status `suggested`, advisory only)

Use `absorb <file> --dry-run` to preview what would be written without touching anything.

## 2. Supersession + provenance

A Correction retires the belief it corrects instead of piling a contradiction on top:

- the old memory's frontmatter becomes `status: superseded` with a `superseded_by` backlink
- the new memory records `supersedes: <old-id>`
- **nothing is deleted** — the old file stays on disk, so it is fully reversible
- superseded memories are **excluded from packs by default** (`--include-superseded` to override)

Matching: if the correction bullet names the target with `[ref: <id>]`, supersession is
deterministic. If not, it falls back to a conservative fuzzy match (token-overlap guarded);
if it can't find a confident target, the correction is saved as an **open** item for you to
resolve rather than guessing.

## 3. Redaction gate at the pack boundary

`pack` now scans every document that would leave the machine — including the snippet
summaries and source map, not just the copied files. Default behaviour is to **block**:

```
pack ...                 # BLOCKS if any secret is detected, lists offenders
pack ... --redact        # masks secrets in the export; your source files are untouched
pack ... --allow-secrets # exports anyway (use only when you're sure)
```

Detectors: private-key blocks, AWS keys, Stripe live keys, GitHub tokens/PATs, Slack
tokens, Google API keys, JWTs, and `keyword: value` assignments (password, api_key,
token, secret, client_secret, …). `audit` runs the same scan across **all** source docs
now, not only shareable ones.

## 4. Incremental index

The FTS index is rebuilt only when the source corpus fingerprint changes, instead of on
every command. Plain `query`/`status` on an unchanged corpus no longer re-hash and
re-index every file. `index` forces a rebuild.

## 5. Hardened query

FTS terms are quoted so operator words (`NEAR`, `AND`, `OR`, `NOT`) and punctuation no
longer break or hijack a search; snippets are computed in Python (the old contentless
`snippet()` returned `None`).

---

## Receipt grammar the absorber understands

```markdown
# MEMORY_RECEIPT

## New decisions
- Short title :: Optional longer body [project: Name]

## Corrections
- What changed and what is now true [ref: <existing-memory-id>]

## Generated files
- filename.ext :: what it is

## Open gaps
- Something still unresolved

## Suggested memory updates
- A non-binding suggestion
```

- `::` separates a short title from a longer body. Omit it and the whole line is used.
- `[project: Name]` attaches the item to a project.
- `[ref: <id>]` names the exact memory a correction retires (deterministic supersession).

The grammar is forgiving: `-` or `*` bullets both work, tags are optional, and empty
placeholder bullets (`- ...`) are ignored.

## New / changed CLI flags

- `absorb <file> --dry-run`
- `pack ... --redact | --allow-secrets | --include-superseded`
- `query ... --active-only`

## Compatibility

Cartridges created by v0 work unchanged — the new frontmatter fields are all optional and
the on-disk format is identical. Run `heal` once to regenerate the memory map with status
flags.

## Tests

`python3 -m unittest test_cartridge -v` — 11 tests, standard library only (no pytest), in
keeping with the project's zero-dependency principle. They cover the absorb-to-typed-memory
path, supersession via `[ref:]`, provenance, the unmatched-correction fallback, the pack
secret-block and redact paths (including the snippet side-channel), superseded-exclusion
from packs, and incremental indexing.
