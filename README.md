# llm-kosh

<!-- mcp-name: io.github.rastogivaibhav/llm-kosh -->

Local-first, persistent memory for MCP-compatible AI clients. Memories remain
plain files on your machine, with SQLite FTS5 search and a tamper-evident event
ledger.

## Install and run

Python 3.9 or newer is required.

```bash
python -m pip install --upgrade llm-kosh
llm-kosh install --yes
llm-kosh status
```

`llm-kosh install` creates `~/.llmkosh/cartridge`, registers the background
service when the operating system permits it, and adds a read-only MCP entry to
Claude Desktop. Restart Claude Desktop after setup.

If service registration is unavailable, run it for the current login session:

```bash
llm-kosh service start
llm-kosh service status
```

## Minimal manual setup

To use a cartridge outside the default location:

```bash
llm-kosh --root ./my-cartridge init --owner "Your Name"
llm-kosh --root ./my-cartridge add --kind note --title "First memory" --body "Hello"
llm-kosh --root ./my-cartridge query "Hello"
```

Run the MCP server over stdio:

```bash
llm-kosh --root ./my-cartridge mcp-server
```

Or use local streamable HTTP:

```bash
llm-kosh --root ./my-cartridge mcp-server --http --port 8000
# endpoint: http://127.0.0.1:8000/mcp
```

The MCP server is read-only by default. Enable capabilities explicitly only
when the connected client should have them:

```bash
llm-kosh --root ./my-cartridge mcp-server --allow-write
```

Additional capability flags are `--allow-mutate` and `--allow-private`.

## Background service

The sustained service watches intake and receipt folders, maintains derived
indexes, and exposes a local health check. Manage it with:

```bash
llm-kosh service start
llm-kosh service status
llm-kosh service stop
```

`llm-kosh daemon` remains as a legacy foreground scheduler interface. New
installations should use `llm-kosh service`.

## Optional features

```bash
python -m pip install "llm-kosh[watch]"     # filesystem events
python -m pip install "llm-kosh[server]"    # FastAPI service
python -m pip install "llm-kosh[semantic]"  # local vector search
python -m pip install "llm-kosh[all]"       # every optional feature
```

MCP support is included in the normal installation.

## Desktop app

The desktop app is distributed as a separate installer on the GitHub Releases
page. It contains a bundled CLI sidecar, so end users do not need a separate
Python installation. The Python command `llm-kosh desktop` configures and starts
the service expected by that app; it does not install the Electron application.

## Security model

- Storage and search are local; there is no telemetry or automatic cloud sync.
- MCP starts read-only.
- Private exports, writes, and mutations require separate opt-in capabilities.
- Context packs are checked for common secret formats before export.
- Local files are plaintext; use operating-system disk encryption for data at rest.

See [SECURITY.md](SECURITY.md) for boundaries and limitations.

## Development

```bash
python -m pip install -e ".[server,watch,ingest]"
python -m pytest -q
```

Native C++ math acceleration is optional. Set `LLM_KOSH_BUILD_NATIVE=1` and
install `pybind11` before building if you want it; release wheels use the tested
pure-Python fallback for portability.

## Documentation

- [Quickstart](QUICKSTART.md)
- [MCP guide](docs/MCP_GUIDE.md)
- [CLI reference](docs/CLI_REFERENCE.md)
- [Architecture](docs/ARCHITECTURE.md)

Licensed under the MIT License.
