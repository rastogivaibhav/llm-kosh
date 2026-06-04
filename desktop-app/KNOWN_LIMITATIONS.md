# Known Limitations

## Architecture
- The Electron frontend does not implement any of the core ingestion or healing logic itself. It relies entirely on the Python `llm-kosh` executable.
- Large context packs may exceed standard OS clipboard limits depending on the target system. 
- Auto-absorb functionality is intentionally unsupported in the UI to prevent catastrophic context corruption. Users must manually validate and approve all incoming receipts.

## System Dependencies
- If the user selects "System PATH" for the CLI executable, they must have Python and the `llm-kosh` package installed globally.
- macOS and Linux packaging workflows are theoretically supported via `electron-builder` but require the sidecar binary to be pre-built on the matching OS architecture (no cross-compilation for PyInstaller).

## UI/UX
- Currently, there is no built-in log rotation or viewer for historical daemon logs beyond the last 100 entries.
- Missing an in-app visual diff viewer for `validate-receipt` output. Users must parse the diff from the text log area.
