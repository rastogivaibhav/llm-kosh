# llm-kosh Desktop Security Model

The Desktop application is designed with safety and local execution as a top priority.

## IPC boundaries
- `contextIsolation` is enabled and `nodeIntegration` is disabled in the renderer process.
- The renderer communicates with the main process exclusively through a heavily restricted `contextBridge` (`window.llmKosh`).
- Arbitrary commands cannot be passed from the renderer to the `child_process.spawn`. All arguments are sanitized and built within `command-builder.js`.

## Process Execution
- We never use `shell: true` when spawning the Python sidecar. This mitigates shell injection vulnerabilities.
- We restrict daemon start arguments to `['start', 'once', 'status']` and mode to `['auto', 'polling', 'watchdog']`.
- The executable path is resolved by the Main process, not dictated by the Renderer.

## Notifications
- Notifications about memory receipts intentionally exclude the payload/body of the receipt to prevent accidentally leaking private memory content onto screen recordings or system notification logs.

## No Telemetry
- The app operates fully locally and makes zero remote API requests. There is no telemetry, tracking, or automated bug reporting.
