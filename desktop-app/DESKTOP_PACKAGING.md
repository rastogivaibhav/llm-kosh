# Packaging llm-kosh Desktop (v0.2)

This document describes how to build installers and executables for the llm-kosh desktop app. We use `electron-builder` to bundle the React UI and Electron main process into standalone applications.

## Prerequisites
- Node.js (v18+)
- npm
- (Optional) `llm-kosh` Python CLI. The desktop app can call the CLI for install, uninstall, and service control when it is available, or you can configure a custom executable path.

## Build Instructions

1. **Build Python Sidecar** (Required for Bundled mode)
   From the project root:
   ```bash
   python scripts/build_sidecar.py
   ```

2. **Package the Electron App**
   From the `desktop-app/` folder, run the script for your target OS:
   ```bash
   npm run package:win
   # or
   npm run package:mac
   # or
   npm run package:linux
   ```

Alternatively, you can package for specific OS targets if you have the necessary cross-compilation tools:
- `npm run package:win` -> Generates an NSIS installer `.exe` for Windows.
- `npm run package:mac` -> Generates a macOS `.dmg`.
- `npm run package:linux` -> Generates Linux `.AppImage` and `.deb` files.

## Build Artifacts & Output
All packaged artifacts will be output to the `desktop-app/dist-electron` folder. This includes:
- The installer (e.g., `llm-kosh Setup 0.2.0.exe`)
- The unpacked app directory (for debugging)

## Limitations and OS Warnings

### 1. CLI Resolution
- The app resolves the `llm-kosh` executable via:
  1. User Configuration (`~/.config/llm-kosh-config.json` -> `executablePath`)
  2. Sidecar path (e.g., `resources/bin/llm-kosh`)
  3. System `PATH`.
- If the CLI is not found, the app gracefully opens an onboarding screen where the user can locate a custom executable.

### 2. macOS Unsigned App Warning
- The macOS build is currently unsigned. When users download and launch the `.dmg`, macOS Gatekeeper may block it. Users will need to bypass this by right-clicking the app and selecting "Open".
- Notarization is not configured in this release.

### 3. Windows SmartScreen
- Windows builds are not signed with an EV certificate. Windows SmartScreen may show a "Windows protected your PC" warning. Users will need to click "More info" -> "Run anyway".

### 4. Linux AppImage Permissions
- AppImages downloaded from a browser often lose their executable permissions. Users must run `chmod +x llm-kosh-0.2.0.AppImage` before running.

## Placeholder Icons
Currently, `build/icon.ico`, `build/icon.icns`, and `build/icon.png` are simple placeholder files to satisfy `electron-builder` constraints. Real icons should be swapped in before a production release.
