# llm-kosh Desktop Sidecar

To provide a seamless experience for non-technical users, the `llm-kosh` desktop application bundles the Python CLI as a standalone executable "sidecar."

## How it Works

We use `PyInstaller` to freeze the `llm_kosh_cli.py` script into a standalone binary. This binary contains a lightweight Python interpreter and all the dependencies required to run the `llm-kosh` commands locally.

The Electron application communicates with this sidecar executable via standard input/output (stdio), securely passing arguments without using an intermediary shell.

## Target Locations

During the Electron build process, `electron-builder` copies the sidecar executable from `sidecar/bin/<platform>` into the packaged app's `resources/bin/` folder.

- **Windows**: `resources/bin/llm-kosh.exe`
- **macOS/Linux**: `resources/bin/llm-kosh`

## Building the Sidecar Locally

If you are developing or preparing for a release, you must build the sidecar on the target operating system (or use CI/CD matrix builds) because PyInstaller does not natively cross-compile.

1. Ensure you have Python installed and your dependencies (including `pyinstaller`) are installed.
2. From the root of the project, run:
   ```bash
   python scripts/build_sidecar.py
   ```
3. The script will output the executable to `sidecar/bin/<platform>/`.

## Testing the Bundled CLI

1. Run `npm run dev` in the `desktop-app` directory.
2. Navigate to **Settings** in the desktop app.
3. Select **Bundled Sidecar** from the **CLI Resolution Mode** dropdown.
4. If the sidecar was built correctly, the "CLI Health" section should turn green and display the version of the bundled executable.

## Why keep Custom / System PATH modes?

Bundled sidecars are convenient, but they can be larger in file size and sometimes trigger false-positive warnings from antivirus software. Advanced users who already have Python and `llm-kosh` installed globally can choose "System PATH" or "Custom Path" to use their existing, native Python environment.
