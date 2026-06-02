# EXAMPLES

Copy-paste recipes. `R` is your cartridge root: `R=~/AI-Cartridge`.

## Set up a project and its decisions

```bash
python3 koush_cli.py --root $R add --kind project --title "SelectiveOS" \
    --body "UK 11+ prep platform: parent-led practice, AI tutor, teacher-approved content."
python3 koush_cli.py --root $R add --kind decision --project "SelectiveOS" \
    --title "Teacher approval queue" \
    --body "AI lessons must be teacher-approved before student visibility."
python3 koush_cli.py --root $R add --kind gap --project "SelectiveOS" \
    --title "DPIA for student answers" --body "Need a data protection impact assessment."
```

## Capture-then-promote

```bash
python3 koush_cli.py --root $R inbox "Idea: parents get a weekly progress digest" --project SelectiveOS
python3 koush_cli.py --root $R inbox                       # find the id
python3 koush_cli.py --root $R promote --id <note-id> --to decision --title "Weekly parent progress digest"
```

## Pack for different audiences

```bash
# ChatGPT, full context, private allowed
python3 koush_cli.py --root $R pack "SelectiveOS lessons registration" --for chatgpt --out cg.zip --include-private

# DeepSeek, tight budget
python3 koush_cli.py --root $R pack "SelectiveOS lessons" --for deepseek --out ds.zip --budget small

# Codex, engineering decisions emphasised
python3 koush_cli.py --root $R pack "SelectiveOS architecture" --for codex --out cx.zip --max-docs 8

# Human handover narrative
python3 koush_cli.py --root $R pack "SelectiveOS status" --for human --out handover.zip --include-private

# Inspect before sending
python3 koush_cli.py --root $R explain-pack cg.zip
python3 koush_cli.py --root $R validate-pack cg.zip
```

## The absorb loop

After an LLM returns a `MEMORY_RECEIPT` (save it as `MEMORY_RECEIPT.md`):

```bash
python3 koush_cli.py --root $R absorb MEMORY_RECEIPT.md
python3 koush_cli.py --root $R absorb MEMORY_RECEIPT.md --dry-run   # preview only
python3 koush_cli.py --root $R resolve                             # list open corrections + candidates
python3 koush_cli.py --root $R resolve --auto --semantic           # auto-match what it can
python3 koush_cli.py --root $R resolve --correction <id> --target <id>   # apply one by hand
```

Or automate it in real-time with the background watchdog observer:

```bash
# Monitor the receipts directory for files named like MEMORY_RECEIPT*.md
python3 koush_cli.py --root $R watch
```

Get the template to paste into a chat:

```bash
python3 koush_cli.py --root $R receipt-template
```

## Semantic search

```bash
python3 koush_cli.py --root $R embed                    # tfidf (offline default)
python3 koush_cli.py --root $R embed --backend st       # local sentence-transformers
python3 koush_cli.py --root $R query "lesson sign-off process" --semantic
```

## Safety

```bash
python3 koush_cli.py --root $R policy --init
python3 koush_cli.py --root $R classify                 # suggest downgrades
python3 koush_cli.py --root $R classify --apply         # enact them
python3 koush_cli.py --root $R partition                # see the visibility split
python3 koush_cli.py --root $R quarantine --id <id>     # pull something out of export flow
python3 koush_cli.py --root $R safe-pack "public roadmap" --for chatgpt --out safe.zip
```

## Health

```bash
python3 koush_cli.py --root $R audit
python3 koush_cli.py --root $R heal --dry-run
python3 koush_cli.py --root $R heal --write-plan
python3 koush_cli.py --root $R heal --apply-plan reports/REPAIR_PLAN.json
python3 koush_cli.py --root $R heal --safe --fix-visibility
python3 koush_cli.py --root $R verify-ledger
python3 koush_cli.py --root $R memory-map
```

## Daily

```bash
python3 koush_cli.py --root $R today
python3 koush_cli.py --root $R daily-pack --out today.zip
python3 koush_cli.py --root $R static-site && open $R/exports/site/index.html
```

## Backup / move / migrate

```bash
python3 koush_cli.py --root $R export-backup --out backup.zip
python3 koush_cli.py --root ~/AI-Cartridge-new import-backup backup.zip
python3 koush_cli.py --root ~/AI-Cartridge-new import-backup backup.zip --force   # over an existing one
python3 koush_cli.py --root $R migrate --dry-run
python3 koush_cli.py --root $R migrate
```

## Import history

```bash
python3 koush_cli.py --root $R import-chatgpt ~/Downloads/chatgpt_export.zip --dry-run
python3 koush_cli.py --root $R import-chatgpt ~/Downloads/chatgpt_export.zip --project "AI Portfolio"
python3 koush_cli.py --root $R import-claude  ~/Downloads/claude_export.json
python3 koush_cli.py --root $R import-gemini  ~/Downloads/MyActivity.json --limit 50
python3 koush_cli.py --root $R import-generic ~/notes/chat.md
python3 koush_cli.py --root $R import-report
```
