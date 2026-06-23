# llm-kosh — Claude Code Project Guide

## What this project is

**llm-kosh** is a local-first AI memory cartridge: a persistent, air-gapped SQLite-backed knowledge store that plugs into Claude Desktop, Claude Code, and any MCP-compatible tool. It gives LLMs permanent memory across sessions with a temporal causal reasoning engine that understands *why* things happened, not just *what* was stored.

**Stack:** Python (CLI + daemon + MCP server) + Electron/React (desktop app) + SQLite FTS5 (storage) + optional sentence-transformers (vector search)

**Current version:** 2.1.1 — see [CHANGELOG_v2_1_1.md](CHANGELOG_v2_1_1.md)

---

## Repository layout

```
llm_kosh/              Python package (installed via pip)
  cli.py               Entry point — all CLI subcommands
  install.py           One-shot install: cartridge, OS service, Claude Desktop config
  mcp_server.py        MCP server (14 tools, stdio transport)
  service.py           Daemon service entry point
  daemon.py            Background job scheduler
  engine/
    reasoning/         Temporal causal reasoning engine (30 modules)
    commands.py        Core ledger/audit commands
    search.py          FTS5 + semantic search
    healing.py         Self-healing repair logic
    intake.py          Intake queue processor
  core/
    memory.py          Cartridge read/write primitives
    utils.py           Ledger (hash-chained), config helpers
  processors/builtin/  Typed memory processors (decision, gap, receipt, …)

desktop-app/           Electron + React UI
  electron/main.js     Main process — tray, daemon manager, Quick Capture
  src/                 React views (Home, Search, Daemon, Intake, …)
  build/               Generated icons (icon.ico, icon.icns, icon.png)

tests/                 589 tests — pytest, asyncio_mode=auto
scripts/               Dev utilities, benchmarks
packaging/             PyInstaller spec for CLI binary
brew-formula/          Homebrew formula (llm-kosh.rb)
server.json            MCP registry entry (modelcontextprotocol/registry)
website/               GitHub Pages site
```

---

## Dev environment setup

```powershell
# Install Python package in editable mode with all deps
pip install -e ".[all]"

# Wire up cartridge, daemon auto-start, Claude Desktop MCP config
llm-kosh install

# Start daemon
llm-kosh service start

# Run desktop app (Electron) in dev mode
cd desktop-app && npm install && npm run dev
```

The cartridge root defaults to `~/.llmkosh/cartridge`. The MCP server auto-connects to Claude Code via `.mcp.json` in this directory — **restart Claude Code after first install** to pick it up.

---

## Running tests

```powershell
# Fast — unit tests only (skip integration)
pytest tests/ -v -k "not integration" --timeout=30

# Full suite (589 tests)
pytest tests/ -v --timeout=60

# Specific engine
pytest tests/test_reasoning*.py -v

# With coverage
pytest tests/ --cov=llm_kosh --cov-report=html
```

**Target:** 579 passed / 0 failed. The 8–10 skipped are integration tests that require a running service.

---

## Key CLI commands

```powershell
llm-kosh init                          # Create a new cartridge
llm-kosh add "My note"                 # Add a memory
llm-kosh query "auth system history"   # FTS5 search
llm-kosh reason --query "..."          # Temporal causal query
llm-kosh status                        # Cartridge health
llm-kosh verify-ledger                 # Check hash-chain integrity
llm-kosh daemon status                 # Background job status
llm-kosh service start/stop/status     # OS service
llm-kosh mcp-server --stdio --allow-write   # Start MCP server
llm-kosh mcp-tools                     # List MCP tools as JSON
llm-kosh install                       # Full one-shot setup
```

---

## MCP server

The MCP server exposes 14 tools over stdio. Claude Code connects via `.mcp.json` in the project root. Claude Desktop is configured at `%APPDATA%\Claude\claude_desktop_config.json`.

**To reconnect after config changes:** restart Claude Code. The MCP server is read once at session startup.

Key tools: `search_memory`, `reasoning_query`, `reasoning_ingest`, `reasoning_critique`, `get_project_context`, `submit_memory_receipt`, `get_daemon_status`.

---

## Architecture: memory layers

| Layer | Implementation | Install flag |
|-------|---------------|--------------|
| Working memory | `llm-kosh pack` — context pack export | core |
| Episodic (causal) | Temporal causal graph — `engine/reasoning/` | core |
| Semantic (FTS) | SQLite FTS5 — `engine/search.py` | core |
| Vector (dense) | sentence-transformers embeddings | `[semantic]` |
| Procedural | Receipt/decision/prompt processors | core |

**The causal graph** (`engine/reasoning/`) is the unique layer: typed edges (`ENABLES`, `CAUSES`, `CONTRADICTS`, `SUPERSEDES`), Lyapunov stability scoring, bidirectional fiber bundle traversal. No vector DB has this.

---

## Install variants

```bash
pip install llm-kosh               # Core only — CLI, FTS5, causal graph, MCP
pip install "llm-kosh[server]"     # + FastAPI, uvicorn, MCP SDK
pip install "llm-kosh[semantic]"   # + sentence-transformers (vector search)
pip install "llm-kosh[watch]"      # + watchdog (folder monitoring)
pip install "llm-kosh[ingest]"     # + markitdown (PDF/DOCX/XLSX ingestion)
pip install "llm-kosh[all]"        # Everything above
```

After any install: `llm-kosh install` wires the OS service, Claude Desktop, and tells you where to download the desktop app binary.

**Desktop app** (Electron — not pip-installable): download `.exe`/`.dmg`/`.AppImage` from https://github.com/rastogivaibhav/llm-kosh/releases/latest

---

## Release process

1. All tests pass: `pytest tests/ -v -k "not integration"`
2. Bump version in `pyproject.toml`
3. Update `CHANGELOG_vX_Y_Z.md`
4. Commit: `git commit -m "chore: bump version to X.Y.Z"`
5. Tag and push: `git tag -a vX.Y.Z -m "Release vX.Y.Z" && git push origin vX.Y.Z`
6. Create GitHub Release — this auto-triggers:
   - `publish.yml` → PyPI
   - `desktop.yml` → `.exe` / `.dmg` / `.AppImage` attached to release

---

## Distribution channels

| Channel | Status | How |
|---------|--------|-----|
| PyPI | Auto on release | `publish.yml` workflow |
| GitHub Releases | Auto on release | `desktop.yml` workflow |
| MCP Registry | `server.json` in repo root | PR to `modelcontextprotocol/registry` |
| Homebrew | `brew-formula/llm-kosh.rb` | Needs `homebrew-llm-kosh` tap repo |
| Claude Desktop | `llm-kosh install` patches config | Done on install |

---

## Important files to know

- [`llm_kosh/install.py`](llm_kosh/install.py) — one-shot setup logic, touch this for install changes
- [`llm_kosh/mcp_server.py`](llm_kosh/mcp_server.py) — all 14 MCP tools defined here
- [`llm_kosh/engine/reasoning/__init__.py`](llm_kosh/engine/reasoning/__init__.py) — reasoning engine public API
- [`llm_kosh/core/utils.py`](llm_kosh/core/utils.py) — ledger (hash-chain), config read/write
- [`.mcp.json`](.mcp.json) — Claude Code MCP config (points to `~/.llmkosh/cartridge`)
- [`desktop-app/electron/main.js`](desktop-app/electron/main.js) — Electron main: tray, global shortcut (`Ctrl+Shift+Space` = Quick Capture), daemon manager
- [`packaging/llm_kosh.spec`](packaging/llm_kosh.spec) — PyInstaller spec for standalone binary
- [`.github/workflows/`](.github/workflows/) — `test.yml`, `publish.yml`, `desktop.yml`

---

## Known constraints

- **Windows Task Scheduler**: `llm-kosh install` uses the Startup folder (no admin required), not `schtasks`. Service starts on next login, or manually via `llm-kosh service start`.
- **macOS Gatekeeper**: Desktop `.dmg` is unsigned — users must right-click → Open on first launch.
- **Vector search**: `[semantic]` installs `sentence-transformers` which is ~1GB. Skip it if you only need FTS.
- **MCP reconnect**: changing `.mcp.json` requires restarting Claude Code to take effect.
- **C++ extension**: `setup.py` tries to build a Pybind11 math extension. It silently falls back to pure Python if compilation fails — all functionality works without it.
