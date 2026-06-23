# Developer guide

This guide is for contributors working on the Python package, MCP server,
service runtime, or desktop integration.

## Supported runtimes

- Python 3.9 through 3.13.
- Node.js 20 for the desktop app.
- Windows, macOS, and Linux are expected to remain supported.

The core Python package should stay lightweight. Optional features belong in
extras such as `watch`, `server`, `semantic`, and `ingest`.

## Local setup

```bash
python -m pip install --upgrade pip setuptools wheel
python -m pip install -e ".[server,watch,ingest]"
python -m pip install pytest pytest-asyncio build twine
```

Desktop setup:

```bash
cd desktop-app
npm ci
npm run lint -- --max-warnings=0
npm test -- --runInBand
npm run build
```

## Repository map

- `llm_kosh/cli.py` — primary command-line entry point.
- `llm_kosh/core/` — cartridge utilities, memory helpers, ledger support.
- `llm_kosh/engine/` — search, packing, intake, reasoning, and command logic.
- `llm_kosh/mcp_server.py` — MCP tool registration and transport startup.
- `llm_kosh/service.py` — sustained background service.
- `llm_kosh/install.py` — install, clean-install, service registration, client config.
- `desktop-app/` — Electron renderer, main process, tests, and packaging.
- `packaging/` — PyInstaller sidecar spec.
- `tests/` — Python regression and lifecycle coverage.

## Validation tiers

Fast Python checks:

```bash
python -m pytest tests/test_ga_lifecycle.py tests/test_mcp_adapter.py tests/test_service_lifecycle.py -q
```

Full Python checks:

```bash
python -m pytest -q
```

Build checks:

```bash
python -m build
python -m twine check dist/*
```

Desktop checks:

```bash
cd desktop-app
npm run lint -- --max-warnings=0
npm test -- --runInBand
npm run build
npm audit --audit-level=high
```

## Generated files

Do not commit generated build directories, local virtual environments, desktop
`dist` output, or `llm_kosh.egg-info/` unless the release process explicitly
requires it. Prefer temporary directories for smoke-test artifacts.

## Coding rules

- Preserve the default read-only MCP posture.
- Keep cartridge mutations auditable through the ledger.
- Avoid hidden network calls in core package code.
- Keep GUI code behind explicit IPC handlers.
- Prefer cross-platform paths and avoid assuming POSIX-only behavior.
- Add tests for lifecycle, packaging, or security-sensitive changes.

## Common smoke commands

```bash
llm-kosh --version
llm-kosh --root ./tmp-cartridge init --owner "Smoke Test"
llm-kosh --root ./tmp-cartridge status
llm-kosh --root ./tmp-cartridge mcp-test
llm-kosh --root ./tmp-cartridge mcp-tools
```
