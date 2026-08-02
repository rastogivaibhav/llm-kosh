"""Install and uninstall helpers for llm-kosh.

This module owns the user-facing lifecycle:
- create/remove the local home directory structure
- register/unregister the sustained background service
- patch/unpatch Claude Desktop MCP config
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path
from typing import Optional
from xml.sax.saxutils import escape as xml_escape

from llm_kosh.global_config import (
    DEFAULT_CONFIG_TOML,
    get_default_cartridge_root,
    get_llmkosh_home,
)


# ---------------------------------------------------------------------------
# Home directory / config
# ---------------------------------------------------------------------------

def create_home_dir() -> None:
    """Create ~/.llmkosh and ~/.llmkosh/cartridge if they don't exist."""
    home = get_llmkosh_home()
    home.mkdir(parents=True, exist_ok=True)
    (home / "cartridge").mkdir(parents=True, exist_ok=True)
    print(f"  [ok] Home directory: {home}")


def write_default_config() -> None:
    """Write DEFAULT_CONFIG_TOML to ~/.llmkosh/config.toml only if not present."""
    config_path = get_llmkosh_home() / "config.toml"
    if config_path.exists():
        print(f"  [skip] Config already exists: {config_path}")
        return
    config_path.write_text(DEFAULT_CONFIG_TOML, encoding="utf-8")
    print(f"  [ok] Wrote default config: {config_path}")


def init_default_cartridge() -> None:
    """Ensure the default cartridge root has been initialised."""
    from llm_kosh.core.memory import init_cartridge
    root = get_default_cartridge_root()
    try:
        init_cartridge(root, "llm-kosh")
        print(f"  [ok] Cartridge root: {root}")
    except Exception as exc:
        print(f"  [warn] Could not initialise cartridge: {exc}")


# ---------------------------------------------------------------------------
# OS service registration
# ---------------------------------------------------------------------------

def _python_exe() -> str:
    return sys.executable


def _service_command() -> list[str]:
    """Command used by OS service managers for source and frozen installs."""
    if getattr(sys, "frozen", False):
        return [_python_exe(), "service", "run"]
    return [_python_exe(), "-m", "llm_kosh.service", "run"]


def _mcp_command(root: str) -> tuple[str, list[str]]:
    """Reliable Claude Desktop command for source and frozen installs."""
    if getattr(sys, "frozen", False):
        return _python_exe(), ["--root", root, "mcp-server"]
    return _python_exe(), ["-m", "llm_kosh.cli", "--root", root, "mcp-server"]


def _pip_cmd(*args: str) -> list[str]:
    return [_python_exe(), "-m", "pip", *args]


def _run_pip(*args: str) -> subprocess.CompletedProcess[str]:
    """Run pip in-process-friendly mode and capture output for diagnostics."""
    return subprocess.run(
        _pip_cmd(*args),
        check=False,
        capture_output=True,
        text=True,
    )


def _print_pip_result(label: str, result: subprocess.CompletedProcess[str]) -> bool:
    if result.returncode == 0:
        print(f"  [ok] {label}")
        return True
    stderr = (result.stderr or result.stdout or "").strip()
    if stderr:
        print(f"  [warn] {label} failed: {stderr}")
    else:
        print(f"  [warn] {label} failed with exit code {result.returncode}")
    return False


def uninstall_python_package() -> bool:
    """Remove the installed llm-kosh distribution from the current Python environment."""
    print("Removing Python package installation...")
    result = _run_pip("uninstall", "-y", "llm-kosh")
    if result.returncode == 0:
        print("  [ok] pip uninstall llm-kosh")
        return True

    stderr = (result.stderr or result.stdout or "")
    if "No files were found to uninstall" in stderr or "The system cannot find the file specified" in stderr:
        print("  [warn] pip uninstall llm-kosh hit a stale-entrypoint cleanup issue; continuing.")
        return True

    if stderr.strip():
        print(f"  [warn] pip uninstall llm-kosh failed: {stderr.strip()}")
    else:
        print(f"  [warn] pip uninstall llm-kosh failed with exit code {result.returncode}")
    return False


def install_python_package(editable: bool = True) -> bool:
    """Install llm-kosh from the current source tree into the active Python environment."""
    print("Installing Python package from current workspace...")
    install_args = ["install"]
    if editable:
        install_args.extend(["-e", "."])
    else:
        install_args.append(".")
    install_args.extend(["--no-deps", "--no-build-isolation", "--upgrade", "--force-reinstall"])
    result = _run_pip(*install_args)
    return _print_pip_result("pip install current workspace", result)


def repair_python_package() -> bool:
    """Reinstall the current workspace using the fastest reliable path available."""
    print("Repairing Python package installation...")
    uninstall_python_package()

    # Prefer a direct source install first; it tends to be faster than editable
    # installs in this environment and gives us a clean, current wheel-equivalent
    # record in site-packages.
    if install_python_package(editable=False):
        return True

    print("  [warn] Direct install failed; retrying editable install.")
    return install_python_package(editable=True)


def _register_darwin() -> bool:
    """Register a launchd plist on macOS."""
    plist_dir = Path.home() / "Library" / "LaunchAgents"
    plist_dir.mkdir(parents=True, exist_ok=True)
    plist_path = plist_dir / "com.llmkosh.service.plist"
    label = "com.llmkosh.service"
    log_dir = get_llmkosh_home()
    log_dir.mkdir(parents=True, exist_ok=True)

    service_command = _service_command()
    program_arguments = "\n".join(
        f"                <string>{xml_escape(arg)}</string>" for arg in service_command
    )
    plist_content = textwrap.dedent(f"""\
        <?xml version="1.0" encoding="UTF-8"?>
        <!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
          "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
        <plist version="1.0">
        <dict>
            <key>Label</key>
            <string>{label}</string>
            <key>ProgramArguments</key>
            <array>
{program_arguments}
            </array>
            <key>WorkingDirectory</key>
            <string>{xml_escape(str(get_default_cartridge_root()))}</string>
            <key>RunAtLoad</key>
            <true/>
            <key>KeepAlive</key>
            <true/>
            <key>ProcessType</key>
            <string>Background</string>
            <key>StandardOutPath</key>
            <string>{xml_escape(str(log_dir / "service.log"))}</string>
            <key>StandardErrorPath</key>
            <string>{xml_escape(str(log_dir / "service.err.log"))}</string>
        </dict>
        </plist>
    """)

    plist_path.write_text(plist_content, encoding="utf-8")
    try:
        subprocess.run(["launchctl", "bootstrap", f"gui/{os.getuid()}", str(plist_path)], check=True, capture_output=True)
        subprocess.run(["launchctl", "enable", f"gui/{os.getuid()}/{label}"], check=False, capture_output=True)
        print(f"  [ok] launchd service registered: {plist_path}")
        return True
    except subprocess.CalledProcessError as exc:
        print(f"  [warn] launchctl bootstrap failed: {exc.stderr.decode(errors='replace').strip()}")
        return False


def _register_linux() -> bool:
    """Register a systemd user unit on Linux."""
    unit_dir = Path.home() / ".config" / "systemd" / "user"
    unit_dir.mkdir(parents=True, exist_ok=True)
    unit_path = unit_dir / "llm-kosh.service"
    working_dir = get_default_cartridge_root()
    working_dir.mkdir(parents=True, exist_ok=True)

    import shlex
    exec_start = " ".join(shlex.quote(part) for part in _service_command())
    unit_content = textwrap.dedent(f"""\
        [Unit]
        Description=llm-kosh background service
        After=default.target

        [Service]
        Type=simple
        ExecStart={exec_start}
        WorkingDirectory={working_dir}
        Restart=on-failure
        RestartSec=10
        Environment="LLMKOSH_ROOT={working_dir}"

        [Install]
        WantedBy=default.target
    """)

    unit_path.write_text(unit_content, encoding="utf-8")
    try:
        subprocess.run(["systemctl", "--user", "daemon-reload"], check=False, capture_output=True)
        subprocess.run(
            ["systemctl", "--user", "enable", "--now", "llm-kosh.service"],
            check=True,
            capture_output=True,
        )
        print(f"  [ok] systemd user service registered: {unit_path}")
        return True
    except subprocess.CalledProcessError as exc:
        print(f"  [warn] systemctl failed: {exc.stderr.decode(errors='replace').strip()}")
        return False


def _register_windows() -> bool:
    """Register a Task Scheduler task on Windows."""
    local_app_data = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    task_dir = local_app_data / "llm-kosh"
    task_dir.mkdir(parents=True, exist_ok=True)
    task_xml_path = task_dir / "task.xml"

    service_command = _service_command()
    executable, service_args = service_command[0], service_command[1:]

    task_xml = textwrap.dedent(f"""\
        <?xml version="1.0" encoding="UTF-16"?>
        <Task version="1.2" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
          <Triggers><LogonTrigger><Enabled>true</Enabled></LogonTrigger></Triggers>
          <Principals>
            <Principal id="Author">
              <RunLevel>LeastPrivilege</RunLevel>
            </Principal>
          </Principals>
          <Actions><Exec>
            <Command>{xml_escape(executable)}</Command>
            <Arguments>{xml_escape(subprocess.list2cmdline(service_args))}</Arguments>
            <WorkingDirectory>{xml_escape(str(get_default_cartridge_root()))}</WorkingDirectory>
          </Exec></Actions>
          <Settings><ExecutionTimeLimit>PT0S</ExecutionTimeLimit></Settings>
        </Task>
    """)

    task_xml_path.write_text(task_xml, encoding="utf-16")

    try:
        result = subprocess.run(
            [
                "schtasks",
                "/Create",
                "/TN", "llm-kosh-service",
                "/XML", str(task_xml_path),
                "/F",
            ],
            check=True,
            capture_output=True,
        )
        print(f"  [ok] Windows Task Scheduler task registered from {task_xml_path}")
        return True
    except subprocess.CalledProcessError as exc:
        stderr = exc.stderr.decode(errors="replace").strip() if exc.stderr else ""
        if "The system cannot find the path specified" in stderr:
            print("  [warn] schtasks reported a path issue while creating the task; check the packaged executable path.")
            return False
        print(f"  [warn] schtasks failed: {stderr}")
        return False
    except FileNotFoundError:
        print("  [warn] schtasks not found; Task Scheduler registration skipped")
        return False


def register_os_service() -> bool:
    """Register the service as an OS service. Returns True on success."""
    print("Registering OS service...")
    if sys.platform == "darwin":
        return _register_darwin()
    elif sys.platform == "linux":
        return _register_linux()
    elif sys.platform == "win32":
        return _register_windows()
    else:
        print(f"  [skip] Unsupported platform: {sys.platform}")
        return False


def unregister_os_service() -> bool:
    """Remove the OS service registration. Returns True on success."""
    print("Unregistering OS service...")
    if sys.platform == "darwin":
        plist_path = Path.home() / "Library" / "LaunchAgents" / "com.llmkosh.service.plist"
        label = "com.llmkosh.service"
        try:
            subprocess.run(["launchctl", "bootout", f"gui/{os.getuid()}", str(plist_path)], check=False, capture_output=True)
            subprocess.run(["launchctl", "disable", f"gui/{os.getuid()}/{label}"], check=False, capture_output=True)
            if plist_path.exists():
                plist_path.unlink()
            print(f"  [ok] launchd service removed: {plist_path}")
            return True
        except OSError as exc:
            print(f"  [warn] Could not remove launchd service: {exc}")
            return False
    elif sys.platform == "linux":
        unit_path = Path.home() / ".config" / "systemd" / "user" / "llm-kosh.service"
        try:
            subprocess.run(["systemctl", "--user", "disable", "--now", "llm-kosh.service"], check=False, capture_output=True)
            subprocess.run(["systemctl", "--user", "daemon-reload"], check=False, capture_output=True)
            if unit_path.exists():
                unit_path.unlink()
            print(f"  [ok] systemd user service removed: {unit_path}")
            return True
        except OSError as exc:
            print(f"  [warn] Could not remove systemd user service: {exc}")
            return False
    elif sys.platform == "win32":
        try:
            all_ok = True
            # Both task names have shipped. End each task before deleting its
            # registration so uninstall cannot leave a live orphan process.
            for task_name in ("llm-kosh-service", "llm-kosh-daemon"):
                subprocess.run(
                    ["schtasks", "/End", "/TN", task_name],
                    check=False, capture_output=True, text=True,
                )
                result = subprocess.run(
                    ["schtasks", "/Delete", "/TN", task_name, "/F"],
                    check=False, capture_output=True, text=True,
                )
                output = (result.stderr or result.stdout or "").lower()
                missing = "cannot find" in output or "does not exist" in output
                if result.returncode == 0:
                    print(f"  [ok] Windows Task Scheduler task removed: {task_name}")
                elif missing:
                    print(f"  [skip] Windows Task Scheduler task not present: {task_name}")
                else:
                    all_ok = False
                    print(
                        f"  [warn] Could not remove scheduled task {task_name}: "
                        f"{(result.stderr or result.stdout or '').strip()}"
                    )
            return all_ok
        except FileNotFoundError:
            print("  [warn] schtasks not found; Task Scheduler removal skipped")
            return False
        except OSError as exc:
            print(f"  [warn] Could not remove scheduled task: {exc}")
            return False
    else:
        print(f"  [skip] Unsupported platform: {sys.platform}")
        return False


# ---------------------------------------------------------------------------
# Claude Desktop config patching
# ---------------------------------------------------------------------------

def _claude_desktop_config_path() -> Optional[Path]:
    """Return the platform-specific path to claude_desktop_config.json."""
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "Claude" / "claude_desktop_config.json"
    elif sys.platform == "win32":
        appdata = os.environ.get("APPDATA", "")
        if appdata:
            return Path(appdata) / "Claude" / "claude_desktop_config.json"
        return None
    else:
        return Path.home() / ".config" / "Claude" / "claude_desktop_config.json"


def _cartridge_root_str() -> str:
    """Return the cartridge root as a forward-slash string suitable for JSON."""
    return str(get_default_cartridge_root()).replace("\\", "/")


def patch_claude_desktop_config(yes: bool = False) -> None:
    """Inject the llm-kosh mcpServers entry into claude_desktop_config.json.

    If an llm-kosh entry already exists and differs, print a diff and prompt
    unless yes=True.
    """
    config_path = _claude_desktop_config_path()
    if config_path is None:
        print("  [skip] Could not determine Claude Desktop config path.")
        return

    root_str = _cartridge_root_str()
    command, command_args = _mcp_command(root_str)
    new_entry = {
        # An absolute interpreter path works even when GUI applications do not
        # inherit the user's shell PATH (common on macOS and Windows).
        "command": command,
        "args": command_args,
        "env": {"CARTRIDGE_WORKSPACE": root_str},
    }

    existing: dict = {}
    if config_path.exists():
        try:
            existing = json.loads(config_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            existing = {}

    mcp_servers: dict = existing.get("mcpServers", {})
    current_entry = mcp_servers.get("llm-kosh")

    if current_entry == new_entry:
        print(f"  [skip] Claude Desktop config already up-to-date: {config_path}")
        return

    if current_entry is not None and not yes:
        import difflib
        old_lines = json.dumps({"llm-kosh": current_entry}, indent=2).splitlines(keepends=True)
        new_lines = json.dumps({"llm-kosh": new_entry}, indent=2).splitlines(keepends=True)
        diff = "".join(difflib.unified_diff(old_lines, new_lines, fromfile="current", tofile="proposed"))
        print("  Existing llm-kosh entry differs from proposed:")
        print(diff)
        answer = input("  Apply update? [y/N] ").strip().lower()
        if answer != "y":
            print("  [skip] Claude Desktop config not updated.")
            return

    mcp_servers["llm-kosh"] = new_entry
    existing["mcpServers"] = mcp_servers

    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(json.dumps(existing, indent=2), encoding="utf-8")
    print(f"  [ok] Claude Desktop config patched: {config_path}")


def unpatch_claude_desktop_config() -> None:
    """Remove the llm-kosh entry from Claude Desktop config if present."""
    config_path = _claude_desktop_config_path()
    if config_path is None or not config_path.exists():
        print("  [skip] Claude Desktop config not found.")
        return

    try:
        existing = json.loads(config_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        print("  [warn] Claude Desktop config unreadable; leaving untouched.")
        return

    mcp_servers = existing.get("mcpServers", {})
    if "llm-kosh" not in mcp_servers:
        print("  [skip] Claude Desktop config has no llm-kosh entry.")
        return

    del mcp_servers["llm-kosh"]
    if mcp_servers:
        existing["mcpServers"] = mcp_servers
    else:
        existing.pop("mcpServers", None)
    config_path.write_text(json.dumps(existing, indent=2), encoding="utf-8")
    print(f"  [ok] Claude Desktop config cleaned: {config_path}")


def clean_local_state() -> bool:
    """Remove local llm-kosh state so install can start fresh."""
    print("Cleaning local llm-kosh state...")
    ok = True
    try:
        unregister_os_service()
    except Exception as exc:
        print(f"  [warn] Service cleanup failed: {exc}")
        ok = False
    try:
        unpatch_claude_desktop_config()
    except Exception as exc:
        print(f"  [warn] Claude Desktop cleanup failed: {exc}")
        ok = False
    try:
        home = get_llmkosh_home()
        if home.exists():
            import shutil
            shutil.rmtree(home, ignore_errors=True)
            print(f"  [ok] Removed local home directory: {home}")
    except Exception as exc:
        print(f"  [warn] Could not remove local home directory: {exc}")
        ok = False
    return ok


# ---------------------------------------------------------------------------
# PATH check
# ---------------------------------------------------------------------------

def check_path_variable() -> None:
    """Warn if the directory containing the llm-kosh executable is not on PATH."""
    import shutil

    if shutil.which("llm-kosh") is not None:
        print("  [ok] llm-kosh is on PATH.")
        return

    # Try to determine where scripts are installed
    scripts_dir: Optional[Path] = None
    try:
        import sysconfig
        scripts_dir = Path(sysconfig.get_path("scripts"))
    except Exception:
        pass

    msg = "  [warn] 'llm-kosh' not found on PATH."
    if scripts_dir:
        msg += f" You may need to add {scripts_dir} to your PATH."
    print(msg)


# ---------------------------------------------------------------------------
# Top-level orchestrator
# ---------------------------------------------------------------------------

def run_install(yes: bool = False, clean: bool = False) -> None:
    """Configure a package that has already been installed by pip/pipx."""
    print("=== llm-kosh setup ===")

    if clean:
        print("\n0. Cleaning local state...")
        clean_local_state()

    print("\n1. Creating home directory...")
    create_home_dir()

    print("\n2. Writing default configuration...")
    write_default_config()

    print("\n3. Initialising default cartridge...")
    init_default_cartridge()

    print("\n4. Registering OS service...")
    service_ok = register_os_service()

    print("\n5. Configuring Claude Desktop MCP...")
    try:
        patch_claude_desktop_config(yes=yes)
    except Exception as exc:
        print(f"  [warn] Claude Desktop config patch failed: {exc}")

    print("\n6. Checking PATH...")
    check_path_variable()

    print("\n=== Setup complete ===")
    print("Check it: llm-kosh status")
    print("MCP (stdio): llm-kosh mcp-server")
    if not service_ok:
        print("Note: OS service registration was not fully successful.")
        print("You can start the service manually with: llm-kosh service start")


def run_uninstall(yes: bool = False) -> None:
    """Reverse the install flow as cleanly as possible."""
    print("=== llm-kosh uninstall ===")
    # Service cleanup depends on installed entry points, so it must happen first.
    unregister_os_service()
    try:
        unpatch_claude_desktop_config()
    except Exception as exc:
        print(f"  [warn] Claude Desktop config cleanup failed: {exc}")
    uninstall_python_package()
    print("=== Uninstall complete ===")


def run_clean_reinstall(yes: bool = False) -> None:
    """Run a full clean reinstall cycle."""
    clean_local_state()
    run_install(yes=yes, clean=False)
