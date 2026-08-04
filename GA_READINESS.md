# GA Readiness Review

Date: 2026-08-03

## Decision by product profile

- **Personal mode:** the Python package, classic MCP path, receipts, safe packs,
  and local service are suitable for a controlled pilot. This is the default
  profile and does not enable external source-folder watching.
- **Company Brain mode:** the governed evidence and cited-context path is still
  pilot-only until the source-folder-to-context acceptance flow passes on a
  clean install with a real MCP client.
- **Desktop installers:** not public GA until Windows signing, macOS
  signing/notarization, and clean-host install checks are configured and
  verified. Company Brain desktop mode has the additional governed-context
  acceptance gate above.

The package is shared; the mode is stored per cartridge in `LLM_KOSH.json`.

## Verified locally

These items were verified in the current work session and are no longer
just aspirational:

- Python suite: 588 passed, 6 explicitly skipped real-cartridge tests.
- Windows concurrent ledger stress: 100 writes preserve one intact hash chain.
- Portable wheel: `py3-none-any`, accepted by `twine check`, installed in a clean virtual environment.
- MCP registry manifest: valid.
- MCP stdio registration: 13 tools.
- MCP streamable HTTP: initialized with the official client and listed 13 tools.
- Sustained service: health endpoint started and reported the correct cartridge root.
- Desktop: 42 Jest tests, strict lint, Vite production build, and 2 Electron Playwright flows passed.
- Frozen Windows sidecar: init, status, MCP self-test, and streamable HTTP passed.
- Windows NSIS installer: built with the sidecar at `resources/bin/llm-kosh.exe` and tray icon at `resources/icon.png`.

The 588-test figure above is a historical baseline. The current engineering
pass adds explicit profile and direct-evidence coverage; record its exact suite
result in the release candidate report rather than carrying this number
forward.

Current engineering pass: **621 passed, 6 skipped**, with one non-failing
warning (FastAPI/httpx deprecation; local pytest cache permission was avoided
in this run).

## Verified in this session

These are the newest checks we completed while updating the repo:

- Top-level README refresh and developer FAQ additions were committed and pushed.
- Service runtime now supports configured external folder watching via
  `[daemon].watched_directories`.
- `python -m pytest tests/test_service_lifecycle.py tests/test_ga_lifecycle.py -q`
  passed locally.
- GitHub Actions publish workflows were run from the current branch and passed
  for the Python package and MCP registry after the version bump to `2.1.2`.

## Remaining release gates

These are still the true GA gaps. They are documented requirements, not
historical assumptions:

1. Let the expanded GitHub Actions matrix pass on Python 3.10-3.13 across Windows, macOS, and Linux.
2. For Company Brain mode, prove external source registration -> bounded evidence retrieval -> cited `company_context_compile` output on a clean install and real MCP client.
3. Configure a Windows code-signing certificate and verify Authenticode on the installer and bundled executables. The local test artifact is unsigned.
4. Configure Apple Developer ID signing and notarization; validate the DMG on a clean macOS host.
5. Build and smoke-test the Linux AppImage/deb on a clean Linux host.
6. Review or accept the remaining npm audit findings: no high/critical findings remain; the reported findings are low/moderate development/test-tool dependencies.

## GitHub Actions release path

This section describes the intended release path. The workflows are current,
but not every gate listed here has been exercised on every platform in this
session:

- `test.yml` exercises the Python matrix on pushes and pull requests.
- `publish.yml` builds, wheel-smokes, validates, and publishes the PyPI package through trusted publishing.
- `publish-mcp.yml` publishes `server.json` to the MCP registry after the PyPI workflow succeeds on `master`, or by manual dispatch.
- `desktop.yml` builds CLI sidecars and desktop artifacts on release publish or manual dispatch.
- `pages.yml` deploys the `website/` folder to GitHub Pages.

The MCP publish workflow should always use the exact commit SHA that produced
the published package so `server.json`, `pyproject.toml`, and the uploaded
artifact version stay aligned.

## Desktop signing configuration

The desktop packaging config no longer forces unsigned macOS builds, so release
hosts can use Electron Builder'"'"'s normal signing/notarization environment.
Public GA artifacts should be produced only from release jobs where signing
material is configured and the resulting installer/app signatures are verified.

## Supported install path

```bash
python -m pip install --upgrade llm-kosh
llm-kosh install --yes
llm-kosh status
```

Manual MCP run:

```bash
llm-kosh mcp-server
```

The normal package includes MCP. Optional extras remain available for filesystem watching, FastAPI, ingestion, and semantic models.
