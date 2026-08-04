# llm-kosh Desktop (Phase 1)

## Installer-led first run

The packaged Windows installer asks for two folders before completing:

- **Work folder** — existing files remain in place and are referenced.
- **LLM-Kosh data folder** — local index, metadata, citations, and configuration.

The installer writes a one-time handoff. On first launch Electron initializes
the destination, configures the source, starts the local service, and shows the
source/index data flow on the Home screen. The normal user does not need to run
the CLI or configure a watcher manually.

Run the desktop acceptance flow in Docker with:

```bash
docker compose -f docker-compose.playwright.yml up --build --abort-on-container-exit
```

This is the minimal Electron desktop shell for the `llm-kosh` system.

## Cartridge modes

Onboarding makes the cartridge profile explicit:

- **Personal** is the default and keeps the classic local-memory workflow.
- **Company Brain** enables governed reference evidence, external source
  folders, and cited context retrieval.

The profile is stored per cartridge. The desktop app does not silently convert
a personal cartridge into a Company Brain; selecting Company Brain runs the
explicit `brain init` transition.

## Architecture

- **Frontend**: React + Tailwind CSS
- **Backend**: Electron Main Process
- **IPC**: Strict `contextBridge` with `contextIsolation: true` and `nodeIntegration: false`.

## Security

This desktop shell acts as a thin wrapper around the local Python CLI. To prevent RCE and shell injection:
- The `spawn` command is strictly used with an array of arguments. The `shell: false` option is enforced.
- **Command Allowlist**: The main process exposes only the commands used by the UI (status, search, intake, audit, pack, receipt, and service commands). Arbitrary Python or shell execution is rejected. All file system access (like selecting watched folders) is safely routed through specific IPC handlers, keeping the renderer isolated.
- The `--allow-secrets` flag is explicitly blocked by the UI security policy.
- No external CDNs are loaded.
- No telemetry or cloud syncing.

## Running the App

Ensure you have your python environment set up with `llm-kosh` available.

1. Navigate to `desktop-app`
2. `npm install`
3. `npm run dev`

The dev script starts Vite and Electron concurrently.

## Testing

A Jest test suite validates the security model of the IPC command builder and configuration storage:

```bash
npm run test
```

## Current packaging behavior
The electron-builder installer creates normal Desktop and Start Menu shortcuts.
The configured source and destination are handed to Electron on first launch;
the local service starts automatically so the Home screen immediately shows
the source/index data flow.

## Packaging

For instructions on how to build installers (`.exe`, `.dmg`, `.AppImage`) using `electron-builder`, see [DESKTOP_PACKAGING.md](DESKTOP_PACKAGING.md).

## Documentation Index
- [Packaging Instructions](./DESKTOP_PACKAGING.md)
- [Sidecar Bundle Architecture](../SIDECAR.md)
- [Daemon & Auto-Start](./DESKTOP_DAEMON.md)
- [Tray Icon](./DESKTOP_TRAY.md)
- [Security Model](./DESKTOP_SECURITY.md)
- [Troubleshooting](./DESKTOP_TROUBLESHOOTING.md)

## Sidecar Layout
For packaged releases, the Python CLI engine should be bundled as a sidecar binary. The application will automatically detect the executable if it is placed at:
```
resources/bin/llm-kosh (or llm-kosh.exe on Windows)
```
