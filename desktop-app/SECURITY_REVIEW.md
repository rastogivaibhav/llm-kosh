# Security Review: v0.4 Release Candidate

## Architecture Hardening
The `llm-kosh` desktop application has been rigorously secured against common Electron vulnerabilities and prompt-injection risks.

### Electron Context Isolation
- **`nodeIntegration` is `false`**: The renderer process has absolutely no access to Node.js APIs (e.g., `fs`, `child_process`).
- **`contextIsolation` is `true`**: The IPC boundary is strictly enforced via a secure `preload.js` bridge.

### Command Execution Sanitization
- The `command-builder.js` script in the Main process serves as a hardened gateway for all `child_process.spawn` calls.
- Arbitrary commands, executable paths, or unapproved flags (e.g., `--allow-secrets`) sent by the Renderer are aggressively dropped or throw errors.
- We never invoke `shell: true`, neutralizing shell-injection attacks via manipulated cartridge paths or filenames.

### Privacy & Telemetry
- **Air-Gapped Operation**: The application does not contain `fetch()`, `axios`, or any remote telemetry tracking. All operations run locally.
- **Notification Privacy**: OS Notifications spawned by the Daemon Manager omit the actual content of memory receipts, protecting sensitive data from leaking into system notification centers or screen recordings.
- **Include-Private Warning**: Users attempting to extract private context files are explicitly warned by the UI.

## Verdict
The security posture of the v0.4 Release Candidate is exceptionally strong and fully aligned with the project's local-first privacy goals.
