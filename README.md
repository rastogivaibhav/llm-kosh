# Koush

**Local-first AI Memory Cartridge System v2.0**

Koush is a zero-dependency, local-first context compiler that turns your file system into a structured memory graph for large language models (LLMs). It solves the problem of "context amnesia" by providing a standardized, auditable, and transportable memory cartridge.

## Features

- **Human-Readable Storage**: Memory is stored as standard Markdown files with YAML frontmatter. No proprietary databases.
- **Pack System**: Compile specific subsets of your memory graph into minimal `.koushpack.zip` files for transport to Claude, ChatGPT, or Gemini.
- **MEMORY_RECEIPT Loop**: Asynchronous state synchronization. Give the AI a pack, receive a `MEMORY_RECEIPT.md` back, and apply the diff directly to your cartridge.
- **Safe by Default**: The Trust Gate explicitly requires human approval for destructive or high-impact state changes.
- **Background OS**: The Koush Daemon runs silently to heal relationships, generate memory maps, and index vectors.
- **MCP Native**: Exposes your local cartridge to Model Context Protocol (MCP) compatible editors (like Cursor) without sacrificing your CLI workflow.

## Installation

```bash
pip install "koush[all]"
```
*Optional Extras: `[watch]` for the daemon, `[semantic]` for vector search, `[server]` for HTTP MCP.*

## Quick Start

```bash
# Initialize a new cartridge in the current directory
koush init

# Add some memory
koush add --kind decision "Use PostgreSQL for the backend" --project "MyApp"

# View your memory graph
koush query

# Generate a pack to send to an LLM
koush pack --project "MyApp"

# Start the background daemon
koush daemon start --mode watchdog
```

## Documentation

- [Quickstart Guide](docs/QUICKSTART.md)
- [Design Philosophy](docs/DESIGN.md)
- [Architecture Map](docs/ARCHITECTURE.md)
- [Security & Trust](docs/SECURITY.md)
- [Receipt Review Guide](docs/RECEIPT_GUIDE.md)
- [Daemon Operating Guide](docs/DAEMON_GUIDE.md)
- [MCP Adapter Guide](docs/MCP_GUIDE.md)
- [Local Workbench](docs/WORKBENCH_GUIDE.md)
- [Data Imports & Migrations](docs/IMPORT_GUIDE.md)
- [Koush Specification Index](docs/SPEC_INDEX.md)
