# CLI Reference Guide

The `llm-kosh` CLI is an extensive, utilitarian toolchain for managing local AI memory. 

> [!TIP]
> For any command, append `--help` (e.g., `llm-kosh pack --help`) to see the full list of supported flags.

## 1. Core Memory Management

Manage the ingestion and promotion of memory items.

### `intake`
The control plane to scan, validate, and process raw directories.
```bash
# Scan for new raw files and create intake records
llm-kosh intake scan
```

### `inbox` & `promote`
Quick-capture notes and promote them to structured memories.
```bash
# Capture a quick thought
llm-kosh inbox "Need to optimize the database query latency"

# Promote an inbox item (by ID) to a 'decision' memory
llm-kosh promote --id 12345 --to decision --title "DB Optimization"
```

## 2. Context Packing (Outbound)

Prepare sanitized, budget-constrained context packs to send to LLMs.

### `pack` / `safe-pack`
Generate an optimized context zip based on a query.
```bash
# Pack context for Claude with a medium budget, safely redacting secrets
llm-kosh safe-pack "How do I implement auth?" --for claude --out ./claude_context.zip --budget medium
```

| Argument | Description |
| :--- | :--- |
| `query` | The natural language intent for the pack. |
| `--for` | The target AI (e.g., `chatgpt`, `claude`, `gemini`). |
| `--out` | Destination path for the `.zip` file. |
| `--budget` | Size budget constraints (`small`, `medium`, `large`). |

## 3. Receipt Absorption (Inbound)

Ingest the structured output (`MEMORY_RECEIPT.md`) returned by an AI.

### `review-receipt` & `absorb`
Review AI changes before committing them to your cartridge.
```bash
# Step 1: Generate a diff review to see what the AI wants to change
llm-kosh review-receipt ./MEMORY_RECEIPT.md

# Step 2: Absorb the receipt directly into the cartridge
llm-kosh absorb ./MEMORY_RECEIPT.md
```

## 4. Search & Indexing

Keep your memories highly retrievable.

### `embed` & `query`
Build vector indices and search semantically.
```bash
# Build the vector index using local sentence-transformers
llm-kosh embed --backend st

# Search the cartridge semantically, outputting raw JSON
llm-kosh query "database latency" --semantic --json
```

## 5. Security & Privacy

Prevent sensitive data leakage.

### `classify` & `quarantine`
```bash
# Scan memories and downgrade visibility if secrets are found
llm-kosh classify --apply

# Move a high-risk item out of the export flow
llm-kosh quarantine --id mem_98765
```

## 6. Daemons & Servers

Background operations for automation and IDE integration.

### `daemon`
Start the self-healing background OS.
```bash
# Start the daemon in filesystem watchdog mode
llm-kosh daemon start --mode watchdog
```

### `mcp-server`
Launch a Model Context Protocol server.
```bash
# Allow AI clients like Claude Desktop to connect to the cartridge via stdio
llm-kosh mcp-server --stdio --allow-write
```

## 7. CLI Composability & Workflows

Because `llm-kosh` commands execute cleanly with predictable outputs, they can be chained together in CI/CD pipelines or bash scripts to automate repetitive tasks.

### The Automated Intake Loop
Automatically scan new files, parse them using declarative processors, and immediately rebuild the search indices:
```bash
llm-kosh intake scan && llm-kosh processor run --all && llm-kosh index && llm-kosh embed
```

### The Safety Pre-Commit Hook
Before committing your codebase, ensure that no secrets have leaked into shareable memories and immediately quarantine them:
```bash
llm-kosh classify --apply && llm-kosh audit
```
