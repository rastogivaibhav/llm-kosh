# llm-kosh

**Give your local LLMs a permanent, air-gapped memory cartridge.**

`llm-kosh` is a lightning-fast, SQLite-backed memory system that gives AI assistants (like Claude and Cursor) permanent recall across sessions. Stop copy-pasting the same 15 architectural decisions and database schemas into every new chat. 

By running completely locally, it guarantees zero cloud syncing, zero API costs, and absolute privacy for your proprietary codebase.

## 🚀 The Killer Feature: Native MCP Server
`llm-kosh` natively supports the **Model Context Protocol (MCP)**. This means tools like Claude Desktop and Cursor can automatically search and read your memory cartridge *without you doing anything*.

### Claude Desktop Setup
Simply add this to your `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "llm-kosh": {
      "command": "uvx",
      "args": ["llm-kosh", "mcp", "--root", "C:/path/to/your/cartridge", "--allow-write"]
    }
  }
}
```
*Now, when you ask Claude "What database are we using for auth?", it automatically searches your `llm-kosh` cartridge and knows the answer.*

## ✨ Features

- 🧠 **Lightning Fast Local Memory:** Powered by an embedded SQLite FTS5 database. Sub-50ms search times across thousands of context files.
- ⚡ **Global Quick Capture:** Press `Ctrl+Shift+Space` anywhere on your OS to instantly dump a thought, decision, or code snippet into your cartridge.
- 🛡️ **Air-Gapped & Secure:** Built-in safety Airlock prevents destructive writes. No data ever leaves your machine unless you explicitly pack it.
- 🖥️ **Beautiful Desktop UI:** Comes with a glassmorphism Electron/React desktop app to manage your memory, monitor the MCP daemon, and configure hotkeys.

## 📦 Quickstart

Get from zero to a running memory cartridge in under 2 minutes.

**1. Install the core system**
```bash
pip install llm-kosh
```

**2. Initialize a new cartridge**
```bash
# Creates a new .llm-kosh root in your current directory
llm-kosh init --owner "Your Name"
```

**3. Launch the Desktop App & Daemon**
```bash
# Starts the UI, the background watcher, and the MCP bridge
llm-kosh desktop
```

---

### 📚 Deep Dives:
- [Architecture Overview](docs/ARCHITECTURE.md)
- [MCP Integration Guide](docs/MCP_GUIDE.md)
- [Comprehensive CLI Reference](docs/CLI_REFERENCE.md)
