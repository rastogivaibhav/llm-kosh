# llm-kosh Desktop Daemon

The Desktop App manages the `llm-kosh` daemon process to automatically detect and ingest memory receipts.

## Lifecycle
- **Auto-Start**: The daemon can be configured to start automatically when the desktop app opens.
- **Monitoring**: The app tracks the daemon's PID, uptime, and logs. It displays these in the **Daemon** tab.
- **Shutdown**: The daemon is automatically stopped when the desktop app is closed.

## Modes
- **Auto**: The daemon decides the best monitoring mode (polling vs watchdog).
- **Polling**: Explicitly polls the file system at regular intervals.
- **Watchdog**: Uses OS-level file system events to detect new files immediately.

## Notifications
The desktop app parses the stdout/stderr of the daemon process. When it detects phrases like "Receipt detected" or "Receipt absorbed", it triggers a native OS notification.

To protect privacy, the desktop app **does not** include the contents of private receipts in these notifications.
