# Release Blockers

## Critical GA Blockers
- Windows Authenticode signing is not yet verified for the installer and bundled sidecar executable.
- macOS Developer ID signing and notarization are not yet verified.
- Linux AppImage/deb artifacts still need a clean-host smoke test.

## Resolved Issues
- **Windows Packaging Privilege Escalation**: The `electron-builder` cache extraction issue for symlinks on Windows has been resolved by enabling **Developer Mode** on the build environment. Windows installers now build successfully. Signing remains a GA release gate until Authenticode verification passes on release artifacts.

## Non-Critical Issues
- macOS/Linux sidecar scripts (`build_sidecar_mac.sh`, `build_sidecar_linux.sh`) are not fully implemented. We are currently relying on `scripts/build_sidecar.py` as a cross-platform solution, which works locally but requires hosted CI validation per target OS.
