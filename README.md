# llm-kosh

<!-- mcp-name: io.github.rastogivaibhav/llm-kosh -->

`llm-kosh` is a local-first memory cartridge for MCP-compatible AI clients.
It gives your agents durable memory without handing your workspace to a hosted
memory service.

Think of it as a structured, inspectable memory layer for agents:

- plain files you can back up, diff, and review
- a tamper-evident ledger for every mutation
- a read-only-by-default MCP server
- a background service for intake and maintenance
- a CLI for local control and automation

## Why teams use it

- Keep AI context local and auditable.
- Separate the cartridge root from the repository root.
- Drop receipts or intake files into watched folders and let the service absorb them.
- Connect MCP clients with minimal privilege by default.
- Publish and verify the same artifact through GitHub Actions.

## What works today

The core project is usable now:

- the CLI runs locally
- the Python package installs and works
- the MCP server runs locally
- the service can watch intake folders
- the GitHub Actions publish path is working

The remaining work is release polish for Windows, macOS, and Linux packaging.

## Quick start

Python 3.10 or newer is required.

```bash
python -m pip install --upgrade llm-kosh
llm-kosh install --yes
llm-kosh status
```

That installs the package, creates the default cartridge at
`~/.llmkosh/cartridge`, configures local defaults, and registers the supported
desktop integration where possible.

To manage the background service:

```bash
llm-kosh service start
llm-kosh service status
llm-kosh service stop
```

If you want to work in a custom cartridge location, set the root explicitly:

```bash
llm-kosh --root ./my-cartridge init --owner "Local User"
llm-kosh --root ./my-cartridge add --kind note --title "First memory" --body "Hello"
llm-kosh --root ./my-cartridge query "Hello"
```

## Core concepts

There are three folders worth knowing:

- the repository root: the code checkout you are reading now
- the cartridge root: the live memory store selected by `--root` or `LLMKOSH_ROOT`
- watched intake folders: `receipts/`, `intake/`, and any configured external drop folders

If you drop files into the cartridge’s intake areas, the service can process
them asynchronously. If you configure external folders through
`[daemon].watched_directories`, the service can absorb those too.

## Use with MCP clients

```bash
llm-kosh --root ./my-cartridge mcp-server
```

The MCP server starts read-only.

Enable stronger capabilities only for clients that should be allowed to write,
mutate, or export private context:

```bash
llm-kosh --root ./my-cartridge mcp-server --allow-write
llm-kosh --root ./my-cartridge mcp-server --allow-write --allow-mutate
llm-kosh --root ./my-cartridge mcp-server --allow-private
```

You can also run MCP over local HTTP:

```bash
llm-kosh --root ./my-cartridge mcp-server --http --port 8000
# endpoint: http://127.0.0.1:8000/mcp
```

## What’s included

- Python CLI for creating, searching, packing, importing, and verifying cartridges
- read-only-by-default MCP server
- local background service for intake and maintenance jobs
- optional desktop packaging with a bundled CLI sidecar
- plain-file storage that stays inspectable, backupable, and Git-friendly
- optional extras for filesystem watching, service integration, semantic search, and ingest helpers

## Optional features

```bash
python -m pip install "llm-kosh[watch]"     # filesystem events
python -m pip install "llm-kosh[server]"    # FastAPI service
python -m pip install "llm-kosh[semantic]"  # local vector search
python -m pip install "llm-kosh[ingest]"    # document conversion helpers
python -m pip install "llm-kosh[all]"       # all optional features
```

MCP support is included in the base installation.

## Developer workflow

```bash
python -m pip install -e ".[server,watch,ingest]"
python -m pytest -q
```

If you are changing packaging or release behavior, also run:

```bash
python -m build
python -m twine check dist/*
```

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

## Desktop app status

The Electron desktop app is packaged separately from the Python package. Local
developer builds and Windows installer smoke tests are supported. Public GA
desktop distribution still requires verified Windows code signing and macOS
Developer ID signing/notarization.

For the current release posture across package, MCP, service, and desktop,
see [GA_READINESS.md](GA_READINESS.md).

## Documentation

- [Quickstart](QUICKSTART.md)
- [Architecture](docs/ARCHITECTURE.md)
- [CLI reference](docs/CLI_REFERENCE.md)
- [MCP guide](docs/MCP_GUIDE.md)
- [Developer guide](docs/DEVELOPER_GUIDE.md)
- [Developer FAQ](docs/DEVELOPER_FAQ.md)
- [MCP developer guide](docs/MCP_DEVELOPER_GUIDE.md)
- [Service developer guide](docs/SERVICE_DEVELOPER_GUIDE.md)
- [Desktop developer guide](docs/DESKTOP_DEVELOPER_GUIDE.md)
- [Release engineering](docs/RELEASE_ENGINEERING.md)
- [Documentation standards](docs/DOCUMENTATION_STANDARDS.md)
- [GA readiness](GA_READINESS.md)
- [Archived historical docs](docs/archive/README.md)

## Native acceleration

Native C++ math acceleration is optional. Set `LLM_KOSH_BUILD_NATIVE=1` and
install `pybind11` before building if you want to test it. Release wheels use
the portable pure-Python fallback.

Licensed under the MIT License.
