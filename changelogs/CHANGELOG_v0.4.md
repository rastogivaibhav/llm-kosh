# Changelog — v0.4

v0.4 adds the `resolve` workflow for open corrections, plus an optional
**embeddings + vector index** layer for semantic matching and search. The default
path stays pure-stdlib and fully offline; the semantic model is opt-in.

## 1. `resolve` — close out open corrections

When `absorb` can't confidently match a correction it leaves it `open` instead of
guessing. `resolve` is the manual + assisted way to finish the job:

- `resolve` — lists every open correction with its top candidate targets (id + score) and
  the exact commands to act.
- `resolve --correction <id> --target <id>` — applies it: the target is retired
  (`superseded_by`) and the correction becomes the active belief.
- `resolve --correction <id> --dismiss` — keeps the correction as a standalone memory that
  supersedes nothing.
- `resolve --auto [--threshold X] [--semantic]` — re-runs matching across all open
  corrections and applies everything above the threshold, using the vector index if
  `--semantic` is set.

Every resolution is logged and writes a `resolved:` marker into the correction's
frontmatter; nothing is deleted.

## 2. Embeddings + vector index (a persistent SQLite vector DB)

`embed` builds a vector for every memory and stores it in `indexes/vectors.sqlite`
(a `vectors` table keyed by id, plus a `vmeta` row recording backend/model/dim/idf). Like
the FTS index it's derived and rebuildable from source. Two pluggable backends share one
cosine implementation (vectors are stored as `{dim: weight}` dicts, sparse or dense):

- **`tfidf`** (default) — pure stdlib, zero-dependency, works offline. Persists the IDF in
  the index so queries vectorise in the same space.
- **`st`** — sentence-transformers (`pip install sentence-transformers`), a local model
  on your machine (default `all-MiniLM-L6-v2`). Nothing leaves the machine. Not bundled, so
  the cartridge stays dependency-free unless you opt in; if the library is missing you get
  a clear install message rather than a stack trace.

`embed --backend st --model <name>` selects it. `status` now reports the index backend,
dimension, vector count, and build time.

## 3. Semantic search and matching

- `query <q> --semantic` searches the vector index instead of FTS (build it with `embed`
  first); supports `--kind`, `--project`, `--active-only`, returns scores.
- `resolve --auto --semantic` and correction matching can use the vector backend.

### Honest limitation (and why `st` exists)

The `tfidf` backend — including its vector form — is **lexical**: it keys on shared words.
It will not bridge a pure synonym gap. A correction worded "drop the incumbent processor
and onboard Adyen" scores ~0 against a decision titled "Use Stripe", because they share no
tokens, so it correctly stays open. That is exactly the case the `st` backend is for: a
real sentence embedding places "incumbent processor" near "Stripe" and lets `resolve
--auto --semantic` catch it. The dense path is tested here with a stub embedder (the model
isn't downloaded in this build environment), but it is standard sentence-transformers usage.

## New CLI

- `embed [--backend tfidf|st] [--model NAME]`
- `query ... --semantic`
- `resolve [--correction ID --target ID | --dismiss | --auto] [--threshold X] [--semantic]`

## Tests

`python3 -m unittest test_cartridge test_v0_3 test_v0_4` — 34 tests, stdlib only. v0.4 adds
9: vector index build, semantic search (tfidf and a stubbed dense backend), the `st` import
guard, the no-index error, and the four resolve flows (list, apply, dismiss, auto).

## Compatibility

On-disk source format unchanged; earlier cartridges work as-is. The vector index is a new,
optional artifact — delete `indexes/vectors.sqlite` and re-run `embed` any time. Re-run
`embed` after adding memories to keep semantic search current.
