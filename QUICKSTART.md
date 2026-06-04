# QUICKSTART

A 10-minute path from empty cartridge to a working boot/work/absorb loop.

## 0. Prerequisites

Python 3.9+. No install, no internet. (Optional: `pip install sentence-transformers` for
semantic search.) In examples below `R` is your cartridge folder.

```bash
R=~/AI-Cartridge
```

## 1. Initialise

```bash
python3 llm_kosh_cli.py --root $R init --owner "Your Name"
```

This creates the folder tree, `LLM_KOSH.json` (with a `llm_kosh_id`), `BOOT.md`, and an
empty index.

## 2. Capture

Add typed memories directly:

```bash
python3 llm_kosh_cli.py --root $R add --kind project --title "SelectiveOS" \
    --body "UK 11+ prep platform."
python3 llm_kosh_cli.py --root $R add --kind decision --project "SelectiveOS" \
    --title "Teacher approval queue" \
    --body "AI lessons must be teacher-approved before they go student-facing."
```

Or capture quick thoughts to the inbox and promote later:

```bash
python3 llm_kosh_cli.py --root $R inbox "Maybe use pgvector for ranking" --project SelectiveOS
python3 llm_kosh_cli.py --root $R inbox                      # list pending
python3 llm_kosh_cli.py --root $R promote --id <note-id> --to decision
```

## 3. Bring in your history (optional)

```bash
python3 llm_kosh_cli.py --root $R import-chatgpt ~/Downloads/chatgpt_export.zip --dry-run
python3 llm_kosh_cli.py --root $R import-chatgpt ~/Downloads/chatgpt_export.zip --project "AI Portfolio"
```

## 4. Find things

```bash
python3 llm_kosh_cli.py --root $R query "teacher approval"
python3 llm_kosh_cli.py --root $R query "ranking" --kind decision --project SelectiveOS
```

For semantic search:

```bash
python3 llm_kosh_cli.py --root $R embed                      # tfidf, offline, default
python3 llm_kosh_cli.py --root $R query "lesson sign-off" --semantic
```

## 5. Pack for an LLM

```bash
python3 llm_kosh_cli.py --root $R pack "SelectiveOS teacher lessons and registration" \
    --for chatgpt --out selectiveos.zip --include-private
python3 llm_kosh_cli.py --root $R explain-pack selectiveos.zip
python3 llm_kosh_cli.py --root $R validate-pack selectiveos.zip
```

Upload `selectiveos.zip` to ChatGPT/Claude/Gemini and say: *"Boot from this cartridge. Read
01_BOOT.md first, then 02-12 in order. Return a MEMORY_RECEIPT at the end."*

## 6. Absorb what comes back

Save the model's `MEMORY_RECEIPT` to `MEMORY_RECEIPT.md`, then manually absorb:

```bash
python3 llm_kosh_cli.py --root $R absorb MEMORY_RECEIPT.md
python3 llm_kosh_cli.py --root $R resolve         # finish any corrections it couldn't auto-match
```

### Alternatively: Real-Time Auto-Absorption (Daemon)

Run the background watchdog daemon to monitor `receipts/` and absorb automatically:

```bash
python3 llm_kosh_cli.py --root $R watch
```

Save your `MEMORY_RECEIPT*.md` files directly in `receipts/` directory. The daemon instantly processes the receipt, triggers correction auto-resolution, and archives the completed file into `receipts/processed/` automatically!


## 7. Keep it healthy

```bash
python3 llm_kosh_cli.py --root $R today           # glance at gaps / corrections / packs
python3 llm_kosh_cli.py --root $R audit
python3 llm_kosh_cli.py --root $R heal --safe
python3 llm_kosh_cli.py --root $R static-site && open $R/exports/site/index.html
```

## 8. Back up

```bash
python3 llm_kosh_cli.py --root $R export-backup --out cartridge-backup.zip
```

That's the whole loop. Everything is plain files under `$R` you can read, grep, and commit
to git.
