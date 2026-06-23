# llm-kosh Desktop (Phase 1)

This is the minimal Electron desktop shell for the `llm-kosh` system.

## Architecture

- **Frontend**: React + Tailwind CSS
- **Backend**: Electron Main Process
- **IPC**: Strict `contextBridge` with `contextIsolation: true` and `nodeIntegration: false`.

## Security

This desktop shell acts as a thin wrapper around the local Python CLI. To prevent RCE and shell injection:
- The `spawn` command is strictly used with an array of arguments. The `shell: false` option is enforced.
- **Phase 5 Command Allowlist**: The main process ONLY executes `status`, `init`, `pack`, `safe-pack`, `validate-pack`, `validate-receipt`, `absorb`, and `daemon`. All file system access (like selecting watched folders) is safely routed through specific IPC handlers, keeping the renderer isolated.
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

## Known Limitations (Phase 6)
- The UI is restricted to Home (with Daemon and Watched Folders controls), Prompt Library, Settings, Generate Pack, and Receipt Inbox views.
- App discovery automation is not yet implemented.

## Next Phase Recommendation
For Phase 7, we should explore packaging the Electron app into a standalone installer, and building out the app discovery automation feature.

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
