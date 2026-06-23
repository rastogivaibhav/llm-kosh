# Desktop developer guide

The desktop app is an Electron client for the Python CLI, service, and MCP
server. It lives in `desktop-app/`.

## Setup

```bash
cd desktop-app
npm ci
npm run lint -- --max-warnings=0
npm test -- --runInBand
npm run build
```

Run E2E smoke tests:

```bash
npm run test:e2e
```

## Process model

- Renderer: React UI.
- Preload: context-isolated `window.llmKosh` bridge.
- Main process: filesystem dialogs, CLI execution, service control, MCP process
  management, tray integration.
- Sidecar: frozen `llm-kosh` executable bundled under `resources/bin`.

The renderer must not import Node filesystem or process modules directly.

## IPC rules

When adding renderer functionality:

1. Add a narrow preload bridge method.
2. Add an explicit main-process IPC handler.
3. Validate arguments in the main process.
4. Use the existing CLI resolver instead of shelling out to arbitrary commands.
5. Add a Jest test for the bridge or handler.

Avoid exposing generic command execution to the renderer.

## Sidecar layout

Packaged apps expect:

- Windows: `resources/bin/llm-kosh.exe`
- macOS/Linux: `resources/bin/llm-kosh`
- tray icon: `resources/icon.png`

The Electron Builder `extraResources` configuration should preserve that
layout exactly.

## Required checks

```bash
npm run lint -- --max-warnings=0
npm test -- --runInBand
npm run build
npm audit --audit-level=high
npm run test:e2e
```

The audit threshold intentionally fails on high or critical vulnerabilities.
Low/moderate dev-tool findings should be reviewed but do not automatically
block local development.

## Signing and release

Local developer builds may be unsigned. Public desktop GA builds require:

- Windows Authenticode signatures on installer and bundled executables.
- macOS Developer ID signing and notarization.
- Clean-host Linux AppImage/deb smoke tests.

See [Release engineering](RELEASE_ENGINEERING.md) and
[Desktop release checklist](../desktop-app/DESKTOP_RELEASE_CHECKLIST.md).
