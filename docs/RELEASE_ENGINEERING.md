# Release engineering

This runbook covers Python package, MCP manifest, service, sidecar, and desktop
release checks.

## Release posture

As of the GA readiness review:

- Python package and MCP server are release-candidate ready after hosted CI.
- The background service is release-candidate ready after cross-platform
  lifecycle checks.
- Desktop installers are not public GA until signing and notarization are
  configured and verified.

See [GA_READINESS.md](../GA_READINESS.md).

Hosted automation currently lives in these workflows:

- `.github/workflows/test.yml` — cross-platform Python test matrix
- `.github/workflows/publish.yml` — build, validate, and publish the PyPI package
- `.github/workflows/publish-mcp.yml` — publish `server.json` to the MCP registry after PyPI succeeds
- `.github/workflows/desktop.yml` — build CLI binaries and desktop artifacts
- `.github/workflows/pages.yml` — deploy `website/` to GitHub Pages

## Python package

Build and inspect distributions:

```bash
python -m pip install --upgrade build twine
python -m build
python -m twine check dist/*
```

Smoke a built wheel from a clean virtual environment before publishing.

## MCP manifest

Check version alignment:

```bash
python - <<'PY'
import json, tomllib
from pathlib import Path
py = tomllib.loads(Path("pyproject.toml").read_text())
srv = json.loads(Path("server.json").read_text())
assert py["project"]["version"] == srv["version"]
print(srv["name"], srv["version"])
PY
```

Validate syntax:

```bash
python -m json.tool server.json
```

If the MCP publisher is available and authenticated:

```bash
mcp-publisher validate server.json
mcp-publisher publish server.json
```

Publishing is an external release action. Do not run it from an unreviewed
working tree. In GitHub Actions, publish `server.json` from the same commit SHA
that produced the PyPI package artifact.

## CLI and service checks

```bash
python -m pytest -q
llm-kosh --version
llm-kosh --root ./tmp-release init --owner "Release Smoke"
llm-kosh --root ./tmp-release status
llm-kosh --root ./tmp-release mcp-test
llm-kosh --root ./tmp-release mcp-tools
```

Service lifecycle checks should be run on each supported OS.

## Frozen sidecar

Build the sidecar with PyInstaller:

```bash
python -m PyInstaller packaging/llm_kosh.spec --clean --noconfirm
```

Smoke the resulting executable:

```bash
dist/llm-kosh/llm-kosh --version
dist/llm-kosh/llm-kosh --root ./tmp-sidecar init --owner "Sidecar Smoke"
dist/llm-kosh/llm-kosh --root ./tmp-sidecar mcp-test
```

## Desktop installers

Required checks before building:

```bash
cd desktop-app
npm ci
npm run lint -- --max-warnings=0
npm test -- --runInBand
npm run build
npm audit --audit-level=high
npm run test:e2e
```

After building, verify:

- sidecar is present under `resources/bin`;
- the app can initialize a cartridge;
- Settings and MCP controls render;
- renderer has no direct filesystem access;
- Windows signatures are valid;
- macOS notarization passes;
- Linux artifacts launch on a clean host.

## Rollback

For Python package issues, publish a patched version rather than replacing an
existing artifact. For desktop issues, remove the affected release artifact or
mark it pre-release while a fixed build is prepared.
