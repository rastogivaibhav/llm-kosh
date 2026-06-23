# llm-kosh

<!-- mcp-name: io.github.rastogivaibhav/llm-kosh -->

`llm-kosh` is a local-first memory cartridge for MCP-compatible AI clients.
It stores user-controlled memory as plain files, indexes it with SQLite FTS5,
and records mutations in a tamper-evident ledger.

The project is designed for developers who want durable AI context without
handing a private workspace to a hosted memory service.

## What it provides

- A Python CLI for creating, searching, packing, and verifying memory cartridges.
- A read-only-by-default MCP server for AI clients such as Claude Desktop.
- A background service for local intake processing and maintenance jobs.
- Optional desktop packaging with a bundled CLI sidecar.
- Plain-file storage that remains inspectable, backupable, and Git-friendly.

## Install and run

Python 3.9 or newer is required.

```bash
python -m pip install --upgrade llm-kosh
llm-kosh install --yes
llm-kosh status
```

`llm-kosh install` creates the default cartridge at `~/.llmkosh/cartridge`,
configures local defaults, and registers a read-only MCP entry for supported
desktop clients where possible.

To manage the background service manually:

```bash
llm-kosh service start
llm-kosh service status
llm-kosh service stop
```

## Minimal manual setup

Use `--root` when you want a cartridge outside the default location:

```bash
llm-kosh --root ./my-cartridge init --owner "Local User"
llm-kosh --root ./my-cartridge add --kind note --title "First memory" --body "Hello"
llm-kosh --root ./my-cartridge query "Hello"
```

Run the MCP server over stdio:

```bash
llm-kosh --root ./my-cartridge mcp-server
```

Or run local streamable HTTP:

```bash
llm-kosh --root ./my-cartridge mcp-server --http --port 8000
# endpoint: http://127.0.0.1:8000/mcp
```

The MCP server starts read-only. Enable stronger capabilities only for clients
that should be allowed to write, mutate, or export private context:

```bash
llm-kosh --root ./my-cartridge mcp-server --allow-write
llm-kosh --root ./my-cartridge mcp-server --allow-write --allow-mutate
llm-kosh --root ./my-cartridge mcp-server --allow-private
```

## Optional features

```bash
python -m pip install "llm-kosh[watch]"     # filesystem events
python -m pip install "llm-kosh[server]"    # FastAPI service
python -m pip install "llm-kosh[semantic]"  # local vector search
python -m pip install "llm-kosh[ingest]"    # document conversion helpers
python -m pip install "llm-kosh[all]"       # all optional features
```

MCP support is included in the base installation.

## Desktop app status

The Electron desktop app is packaged separately from the Python package. Local
developer builds and Windows installer smoke tests are supported. Public GA
desktop distribution still requires verified Windows code signing and macOS
Developer ID signing/notarization.

For the current release posture across package, MCP, service, and desktop,
see [GA_READINESS.md](GA_READINESS.md).

## Security model

- Storage and search are local by default.
- There is no automatic cloud sync or telemetry in the Python package.
- MCP starts read-only.
- Write, mutation, and private-export capabilities require explicit opt-in.
- Context exports are checked for common secret patterns before sharing.
- Cartridge files are plaintext; use operating-system disk encryption if local
  data at rest needs encryption.

See [SECURITY.md](SECURITY.md) and [docs/SECURITY.md](docs/SECURITY.md) for
boundaries and limitations.

## Development

```bash
python -m pip install -e ".[server,watch,ingest]"
python -m pytest -q
```

Native C++ math acceleration is optional. Set `LLM_KOSH_BUILD_NATIVE=1` and
install `pybind11` before building if you want to test it. Release wheels use
the portable pure-Python fallback.

## Documentation

- [Quickstart](QUICKSTART.md)
- [Architecture](docs/ARCHITECTURE.md)
- [CLI reference](docs/CLI_REFERENCE.md)
- [MCP guide](docs/MCP_GUIDE.md)
- [Developer guide](docs/DEVELOPER_GUIDE.md)
- [MCP developer guide](docs/MCP_DEVELOPER_GUIDE.md)
- [Service developer guide](docs/SERVICE_DEVELOPER_GUIDE.md)
- [Desktop developer guide](docs/DESKTOP_DEVELOPER_GUIDE.md)
- [Release engineering](docs/RELEASE_ENGINEERING.md)
- [Documentation standards](docs/DOCUMENTATION_STANDARDS.md)
- [GA readiness](GA_READINESS.md)
- [Archived historical docs](docs/archive/README.md)

Licensed under the MIT License.
