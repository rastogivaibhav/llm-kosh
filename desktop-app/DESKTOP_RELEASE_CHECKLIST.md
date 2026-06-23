# Desktop Release Checklist

Before tagging and building a release for `llm-kosh` desktop, perform the following verification:

## 1. Automated Tests
- [ ] Run `npm run test` in the `desktop-app` directory.
- [ ] Ensure all Jest suites (security, config, resolver, smoke) pass with 100% success.
- [ ] Run `npm run lint -- --max-warnings=0`.

## 2. Onboarding Flow
- [ ] Clear `~/.config/llm-kosh-config.json` (or equivalent `userData` path).
- [ ] Launch the app. Verify the Onboarding screen appears.
- [ ] Verify "CLI Not Found" appears if the path is explicitly broken.
- [ ] Verify "Create New Cartridge" properly initializes a root.

## 3. Core Functionality
- [ ] **Home:** Verify Daemon status updates correctly. Toggle the daemon on and off.
- [ ] **Watched Folders:** Add a folder, verify the daemon restart prompt appears.
- [ ] **Generate Pack:** Generate a safe-pack. Verify the Output directory opens when clicking "Reveal".
- [ ] **Generate Pack (Private):** Toggle "Include Private Context" and verify the warning modal appears.
- [ ] **Receipts:** Load a valid receipt. Verify "Approve & Absorb" is disabled until "Validate Receipt" is clicked.
- [ ] **Receipts:** Verify the confirmation modal appears upon Absorb.

## 4. Smoke Test
- [ ] Navigate to Settings.
- [ ] Click "Run Local Smoke Test".
- [ ] Verify all steps return `PASS`.

## 5. Packaging Validation
- [ ] Run `npm run package:win` (or appropriate OS command).
- [ ] Verify the installer artifact is generated in `dist-electron/`.
- [ ] Install and launch the packaged app.
- [ ] Verify the Onboarding screen appears correctly.
- [ ] Verify Settings persist across restarts.
- [ ] Verify the "CLI Missing" state is clear if the path is invalid.
- [ ] Verify the renderer has no raw `fs` access (e.g. no errors logged in developer console about Node modules).
- [ ] Ensure no external network calls are required to use the Prompt Library.
- [ ] Verify the bundled sidecar exists at `resources/bin/llm-kosh` (or `.exe`).
- [ ] Verify Windows installers and executables have a valid Authenticode signature.
- [ ] Verify the macOS app is Developer ID signed and notarized; do not publish an unsigned DMG as GA.
