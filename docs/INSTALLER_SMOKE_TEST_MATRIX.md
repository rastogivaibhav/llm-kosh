# Installer Smoke Test Matrix

Use this checklist when validating packaged builds and service registration.

## macOS
- Install from the `.dmg`
- Launch the app and confirm the service starts
- Verify `llm-kosh service status`
- Quit the app and confirm the service stops cleanly or remains registered as expected
- Uninstall with `llm-kosh uninstall`
- Confirm the LaunchAgent plist is removed and Claude Desktop config is cleaned up

## Linux
- Install from the packaged artifact or local CLI
- Run `llm-kosh service install`
- Confirm `systemctl --user status llm-kosh.service`
- Confirm `LLMKOSH_ROOT` is honored by the running service
- Run `llm-kosh service uninstall`
- Confirm the user unit file is removed and `daemon-reload` was applied

## Windows
- Install from the `.exe` or `.msi`
- Run `llm-kosh service install`
- Confirm the scheduled task exists as `llm-kosh-service`
- Start the desktop app and confirm service health
- Run `llm-kosh service uninstall`
- Confirm the scheduled task is removed and the Claude Desktop config is cleaned up

## Shared Checks
- `llm-kosh --help` shows `service`, `install`, `uninstall`, and `desktop`
- The desktop app can resolve the CLI path
- The service IPC layer works through both `service-*` and legacy `daemon-*` aliases
- No regression in `tests/test_service_lifecycle.py`
