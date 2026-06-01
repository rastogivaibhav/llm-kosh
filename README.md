# AI Memory Cartridge

A **local-first, human-readable AI memory cartridge**. Not a SaaS, not an agent memory DB,
not an Obsidian clone — a personal artifact you own that captures your decisions, prompts,
projects and AI conversations as plain Markdown files, and that can produce focused,
**bootable context packs** to upload into ChatGPT, Claude, Gemini, DeepSeek, Codex, or hand
to another person.

The loop it gives you:

```
capture / import  ->  query  ->  pack  ->  upload to an LLM  ->  get a MEMORY_RECEIPT
        ^                                                              |
        +---------------  absorb  <-  resolve  <-  audit / heal  ------+
```

## Why

LLM memory today is either vendor-locked and opaque, or absent. This keeps the source of
truth as files **you** can read, diff, back up and grep, and treats every index as a
rebuildable derivative. Nothing leaves your machine unless you pack it, and the pack passes
a secret gate first.

## Principles

1. Local-first; no cloud, no vendor dependency.
2. The Python standard-library path always works. Optional deps (sentence-transformers) are
   truly optional.
3. Human-readable Markdown source is the source of truth; SQLite/vector indexes are derived
   and rebuildable.
4. No silent destructive edits. Every superseding/destructive action is logged. Corrections
   supersede; they never delete; history is preserved.
5. Every export remains understandable as a plain zip uploaded to any LLM.

## Install

No install. One file, Python 3.9+ standard library:

```bash
python3 cartridge.py --help
```

Optional local vector indexer (semantic search & auto-resolution):

```bash
pip install sentence-transformers sqlite-vec   # 100% offline, high-performance local vector DB
```

## Quick start

```bash
python3 cartridge.py --root ~/AI-Cartridge init --owner "Your Name"
python3 cartridge.py --root ~/AI-Cartridge add --kind decision \
    --project "SelectiveOS" --title "AI lessons require teacher approval" \
    --body "Generated lessons go to a teacher queue before student visibility."
python3 cartridge.py --root ~/AI-Cartridge query "teacher approval"
python3 cartridge.py --root ~/AI-Cartridge pack "SelectiveOS teacher lessons" \
    --for chatgpt --out selectiveos.zip --include-private
```

See `QUICKSTART.md` for the full daily workflow and `EXAMPLES.md` for copy-paste recipes.

## Using packs with each LLM

Create a pack, then upload the zip and tell the model to boot from it:

> Boot from this cartridge. Read `01_BOOT.md` first, then files `02`-`12` in order. Use this
> as your source context. At the end, return a `MEMORY_RECEIPT`.

- **ChatGPT / Claude / Gemini** - `--for chatgpt|claude|gemini`. Upload the zip (or paste
  the numbered files). Each gets a tailored `provider/<NAME>_CONTEXT.md`.
- **DeepSeek** - `--for deepseek` produces a compact `DEEPSEEK_CONTEXT.txt` for tighter
  context windows.
- **Codex / coding** - `--for codex` emphasises projects and engineering decisions as
  binding constraints.
- **Human handover** - `--for human` writes a narrative someone can read to pick up your
  work.

When the model returns a `MEMORY_RECEIPT`, save it and absorb it:

```bash
python3 cartridge.py --root ~/AI-Cartridge absorb MEMORY_RECEIPT.md
python3 cartridge.py --root ~/AI-Cartridge resolve        # close out open corrections
python3 cartridge.py --root ~/AI-Cartridge audit
python3 cartridge.py --root ~/AI-Cartridge heal --safe
```

### Automated Real-Time Monitoring (Daemon)

To automate this loop completely without manual execution, run the watchdog daemon:

```bash
python3 cartridge.py --root ~/AI-Cartridge watch
```

This monitors your `receipts/` directory in real-time. Whenever an LLM writes a `MEMORY_RECEIPT*.md` file there, the daemon immediately:
1. Validates and auto-absorbs the receipt's memories and provenance.
2. Auto-resolves any corrections using the local similarity model.
3. Automatically archives the processed receipt into a `receipts/processed/` subdirectory to avoid duplicate triggers and keep the workspace perfectly clean!


## Importing your history

```bash
python3 cartridge.py --root ~/AI-Cartridge import-chatgpt ~/Downloads/chatgpt_export.zip --project "AI Portfolio"
python3 cartridge.py --root ~/AI-Cartridge import-claude  ~/Downloads/claude_export.json
python3 cartridge.py --root ~/AI-Cartridge import-gemini  ~/Downloads/MyActivity.json
python3 cartridge.py --root ~/AI-Cartridge import-generic ~/notes/chat.md
```

Add `--dry-run` to preview. Raw exports are preserved verbatim under `attachments/imports/`.

## Command surface

| Area | Commands |
|------|----------|
| Core | `init`, `add`, `ingest`, `index`, `query`, `status` |
| Packs | `pack`, `validate-pack`, `explain-pack`, `daily-pack` |
| Receipts | `absorb`, `watch`, `resolve`, `receipt-template` |
| Semantic | `embed`, `query --semantic` |
| Import | `import-chatgpt`, `import-claude`, `import-gemini`, `import-generic`, `import-report` |
| Safety | `policy`, `classify`, `partition`, `quarantine`, `safe-pack` |
| Health | `audit`, `heal`, `verify-ledger`, `memory-map`, `repair-plan` |
| Daily | `today`, `inbox`, `promote`, `static-site` |
| Backup | `export-backup`, `import-backup`, `migrate` |

Every command has `--help`.

## Safety in one line

`safe-pack` never emits private or blocked memories, scans for secrets, and redacts by
default. `pack` blocks on detected secrets unless you `--redact` or `--allow-secrets`. See
`SECURITY.md`.

## Backup

```bash
python3 cartridge.py --root ~/AI-Cartridge export-backup --out cartridge-backup.zip
python3 cartridge.py --root ~/NewLocation import-backup cartridge-backup.zip
```

Backups contain the source of truth (Markdown + ledger + config), not derived indexes;
those rebuild on restore.

## Layout

```
CARTRIDGE.json        config + cartridge_id
CARTRIDGE_POLICY.json export policy (optional)
BOOT.md               boot instructions
MEMORY_MAP.md         generated map
source/               the source of truth (Markdown + frontmatter)
ledger/events.jsonl   append-only event log
indexes/              derived FTS + vector indexes (rebuildable)
attachments/imports/  preserved raw imports
exports/              packs + static site
reports/              audit / import / repair reports
```

See `DESIGN.md` for the architecture and `CHANGELOG_v*.md` for the version history.

## Status

v1.0.0 - stable personal release. Standard library only, no internet required.
