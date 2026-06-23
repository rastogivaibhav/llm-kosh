# QUICKSTART

A 10-minute path from empty cartridge to a working boot/work/absorb loop.

## 0. Prerequisites

Install Python 3.9+ and llm-kosh. MCP support is included in the normal package.

```bash
python -m pip install --upgrade llm-kosh
```

In examples below `R` is your cartridge folder.

```bash
R=~/AI-Cartridge
```

## 1. Initialise

```bash
llm-kosh init --owner "Your Name"
```

This creates the folder tree, `LLM_KOSH.json` (with a `llm_kosh_id`), `BOOT.md`, and an
empty index.

## 2. Capture

Add typed memories directly:

```bash
llm-kosh add --kind project --title "SelectiveOS" \
    --body "UK 11+ prep platform."
llm-kosh add --kind decision --project "SelectiveOS" \
    --title "Teacher approval queue" \
    --body "AI lessons must be teacher-approved before they go student-facing."
```

Or capture quick thoughts to the inbox and promote later:

```bash
llm-kosh inbox "Maybe use pgvector for ranking" --project SelectiveOS
llm-kosh inbox                      # list pending
llm-kosh promote --id <note-id> --to decision
```

## 3. Bring in your history (optional)

```bash
llm-kosh import-backup ~/Downloads/chatgpt_export.zip --dry-run
llm-kosh import-backup ~/Downloads/chatgpt_export.zip --project "AI Portfolio"
```

## 4. Find things

```bash
llm-kosh query "teacher approval"
llm-kosh query "ranking" --kind decision --project SelectiveOS
```

For semantic search:

```bash
llm-kosh embed                      # tfidf, offline, default
llm-kosh query "lesson sign-off" --semantic
```

## 5. Pack for an LLM

```bash
llm-kosh pack "SelectiveOS teacher lessons and registration" \
    --for chatgpt --out selectiveos.zip
llm-kosh explain-pack selectiveos.zip
llm-kosh validate-pack selectiveos.zip
```

Upload `selectiveos.zip` to ChatGPT/Claude/Gemini and say: *"Boot from this cartridge. Read
01_BOOT.md first, then 02-12 in order. Return a MEMORY_RECEIPT at the end."*

## 6. Absorb what comes back

Save the model's `MEMORY_RECEIPT` to `MEMORY_RECEIPT.md`, then manually absorb:

```bash
llm-kosh absorb MEMORY_RECEIPT.md
llm-kosh resolve         # finish any corrections it couldn't auto-match
```

### Alternatively: Real-Time Auto-Absorption (Daemon)

Run the background watchdog daemon to monitor `receipts/` and absorb automatically:

```bash
llm-kosh daemon start --mode watchdog
```

Save your `MEMORY_RECEIPT*.md` files directly in `receipts/` directory. The daemon instantly processes the receipt, triggers correction auto-resolution, and archives the completed file into `receipts/processed/` automatically!

## 7. Keep it healthy

```bash
llm-kosh today           # glance at gaps / corrections / packs
llm-kosh audit
llm-kosh heal --safe
llm-kosh workbench       # Starts the local Web UI to explore memories visually
```

## 8. Back up

```bash
llm-kosh export-backup --out cartridge-backup.zip
```

That's the whole loop. Everything is plain files under `$R` you can read, grep, and commit
to git.
