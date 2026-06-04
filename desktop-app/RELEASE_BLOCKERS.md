# Release Blockers

## Critical Blockers
*None. All previous critical blockers have been resolved.*

## Resolved Issues
- **Windows Packaging Privilege Escalation**: The `electron-builder` cache extraction issue for symlinks on Windows has been resolved by enabling **Developer Mode** on the build environment. Windows installers (`.exe`) now build and sign successfully.

## Non-Critical Issues
- macOS/Linux sidecar scripts (`build_sidecar_mac.sh`, `build_sidecar_linux.sh`) are not fully implemented. We are currently relying on `scripts/build_sidecar.py` as a cross-platform solution, which works locally but might require specific CI/CD setups for GitHub Actions cross-compilation.
