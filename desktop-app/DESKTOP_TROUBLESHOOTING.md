# llm-kosh Desktop Troubleshooting

This document outlines common issues when running the packaged desktop application.

## 1. Antivirus Flagging the App or Sidecar
Because the app bundles a standalone Python executable built with PyInstaller, it is common for aggressive antivirus solutions (like Windows Defender) to flag the executable (`llm-kosh.exe`) as a false positive. 

**Solution**:
1. Add an exclusion in your antivirus software for the installation directory or the `llm-kosh.exe` executable inside `resources/bin/`.
2. Alternatively, switch the app's **CLI Resolution Mode** to **Custom Path** or **System PATH** and point it to a standard Python installation of `llm-kosh`.

## 2. "Executable not found" in Bundled Mode
If you select **Bundled Sidecar** and the app reports an error finding the executable, it means the sidecar was not generated before the Electron app was packaged.

**Solution**:
Developers must run `python scripts/build_sidecar.py` before running the Electron `npm run build` or packaging scripts.

## 3. macOS App is Damaged / Cannot be Opened
If you download the `.dmg` from the internet, macOS Gatekeeper may quarantine the application.

**Solution**:
Remove the quarantine attribute using terminal:
```bash
xattr -cr /Applications/llm-kosh.app
```

## 4. Permission Denied on Linux/macOS Sidecar
If the bundled sidecar lacks executable permissions after installation, the app will fail to communicate with the daemon.

**Solution**:
Run `chmod +x` on the binary inside the app bundle:
- macOS: `chmod +x /Applications/llm-kosh.app/Contents/Resources/bin/llm-kosh`
- Linux: `chmod +x /opt/llm-kosh/resources/bin/llm-kosh`
