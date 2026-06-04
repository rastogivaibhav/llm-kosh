# llm-kosh

**The ultimate local AI memory cartridge system and self-healing daemon.**

`llm-kosh` acts as a secure, local bridge between human developers and Large Language Models (LLMs). It allows you to ingest raw context, pack it securely for any AI, and seamlessly absorb the AI's structured output back into your personal memory system.

## Features at a Glance

- 🧠 **Structured Local Memory:** Type-safe memory primitives (decisions, projects, gaps) with powerful FTS and vector search backends.
- 🔄 **The "Pack & Absorb" Loop:** Generate optimized, budget-constrained context zips (`pack`) and effortlessly ingest AI outputs via `MEMORY_RECEIPT.md` (`absorb`).
- 🛡️ **Privacy-First & Secure:** Completely local and air-gapped. Built-in redaction, export policies, and quarantine workflows to prevent secret leakage.
- ⚡ **Self-Healing Daemon OS:** Background watcher that auto-heals corrupted structures, processes intake, and maintains indices.
- 🔌 **Native MCP Server:** Exposes your local cartridge directly to AI IDEs (like Claude Desktop) via the Model Context Protocol.

## Quickstart

Get from zero to a running memory cartridge in under 2 minutes.

> [!NOTE]
> `llm-kosh` requires Python 3.10+ and operates entirely on your local filesystem.

**1. Install**
```bash
pip install llm-kosh
```

**2. Initialize a Cartridge**
```bash
# Creates a new .llm-kosh root in your current directory
llm-kosh init --owner "Your Name"
```

**3. Start the Background Daemon**
```bash
# Starts the self-healing background OS to watch for changes
llm-kosh daemon start --mode watchdog
```

You are now ready to start packing context and absorbing memories. 

---
📚 **Deep Dives:**
- [Architecture Overview](docs/ARCHITECTURE.md)
- [Comprehensive CLI Reference](docs/CLI_REFERENCE.md)
