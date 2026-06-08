# llm-kosh Desktop v0.4 Release Notes

We are thrilled to announce the Release Candidate for llm-kosh Desktop v0.4! 
This release marks a massive shift in usability, turning the desktop app from a simple manual interface into a seamless background memory companion.

## What's New
- **Bundled Python Engine (Sidecar)**: No more Python installations! We now ship a fully bundled, pre-compiled PyInstaller sidecar binary alongside the Electron app. Non-technical users can just click and run.
- **Auto-Start Daemon & System Tray**: The app now installs a native system tray icon and can optionally start automatically on system login. The background daemon can be configured to start automatically, quietly monitoring your memory intake folder.
- **Secure Native Notifications**: The app intelligently intercepts daemon logs and fires secure local desktop notifications when receipts are discovered or absorbed, without ever leaking the private memory contents.
- **New Daemon UI**: A dedicated "Daemon" panel in the sidebar provides live tracking of the daemon's process PID, uptime, logs, and running mode.
- **Granular CLI Control**: Advanced users can still opt out of the bundled sidecar and use their custom or system PATH `llm-kosh` executable via the Settings panel.

## Security Improvements
- Strict whitelisting enforced on all daemon arguments.
- Arbitrary shell commands are explicitly prevented (`shell: false`).
- Privacy-first context generation (`safe-pack` remains default).

## Upgrading
Just download the installer for your OS and install over your previous version. Your `llm-kosh-desktop-config.json` will be automatically preserved.
