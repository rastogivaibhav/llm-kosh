# QUICKSTART

A short path from install to a working local cartridge, MCP server, and receipt loop.

## 0. Install

Python 3.9 or newer is required.

```bash
python -m pip install --upgrade llm-kosh
llm-kosh install --yes
llm-kosh status
```

`install` creates the default cartridge and registers a read-only MCP entry for
supported desktop clients where possible.

## 1. Use a custom cartridge (optional)

```bash
llm-kosh --root ./my-cartridge init --owner "Your Name"
llm-kosh --root ./my-cartridge add --kind note --title "First memory" --body "Hello"
llm-kosh --root ./my-cartridge query "Hello"
```

## 2. Run MCP locally

stdio transport:

```bash
llm-kosh --root ./my-cartridge mcp-server
```

Local streamable HTTP:

```bash
llm-kosh --root ./my-cartridge mcp-server --http --port 8000
```

Sanity-check registration:

```bash
llm-kosh --root ./my-cartridge mcp-test
llm-kosh --root ./my-cartridge mcp-tools
```

## 3. Share context safely

Create a pack for an LLM:

```bash
llm-kosh safe-pack "What should I work on next?" --for claude --out ./context.zip
```

## 4. Absorb reviewed output

Ask the model to return a `MEMORY_RECEIPT.md`, then review it before absorbing:

```bash
llm-kosh validate-receipt MEMORY_RECEIPT.md
llm-kosh review-receipt MEMORY_RECEIPT.md
llm-kosh absorb MEMORY_RECEIPT.md
```

## 5. Run the background service when needed

```bash
llm-kosh service start
llm-kosh service status
llm-kosh service stop
```

The older `daemon` command remains as a compatibility alias, but `service` is
the supported interface going forward.
