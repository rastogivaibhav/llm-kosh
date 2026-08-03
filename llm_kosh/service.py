"""Persistent daemon service for llm-kosh.

Ports:
    API    5555  (managed by llm_kosh.server)
    Health 5556  (this module)

PID file : ~/.llmkosh/daemon.pid
Log file : ~/.llmkosh/daemon.log  (RotatingFileHandler, 10 MB, 3 backups)
"""

from __future__ import annotations

import argparse
import json
import logging
import logging.handlers
import os
import signal
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Optional

from llm_kosh.global_config import get_global_config, get_default_cartridge_root, get_llmkosh_home
from llm_kosh.pid import write_pid, read_pid, is_running, clear_pid

# ---------------------------------------------------------------------------
# Health HTTP handler
# ---------------------------------------------------------------------------

_startup_time: float = time.time()
_health_pid: int = os.getpid()
_health_root: str = ""


class _HealthHandler(BaseHTTPRequestHandler):
    """Minimal HTTP handler that serves GET /health."""

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/health":
            payload = json.dumps({
                "status": "ok",
                "pid": _health_pid,
                "uptime_s": int(time.time() - _startup_time),
                "root": _health_root,
            }).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, fmt: str, *args: object) -> None:  # noqa: N802
        # Suppress default access log spam
        pass


# ---------------------------------------------------------------------------
# Watchdog event handlers (inline, mirrors daemon.py handlers)
# ---------------------------------------------------------------------------

try:
    from watchdog.observers import Observer as _Observer
    from watchdog.events import FileSystemEventHandler as _FSEventHandler
    _HAS_WATCHDOG = True
except ImportError:
    _HAS_WATCHDOG = False
    _Observer = None  # type: ignore[assignment,misc]
    _FSEventHandler = object  # type: ignore[assignment,misc]


class _ReceiptHandler(_FSEventHandler):  # type: ignore[misc]
    def __init__(self, root: Path, logger: logging.Logger) -> None:
        super().__init__()
        self._root = root
        self._log = logger

    def on_created(self, event: object) -> None:  # type: ignore[override]
        src = getattr(event, "src_path", "")
        if "MEMORY_RECEIPT" in src and src.endswith(".md"):
            self._log.info("Receipt detected by watchdog: %s", src)
            try:
                from llm_kosh.daemon import daemon_once
                daemon_once(self._root)
            except Exception as exc:
                self._log.warning("daemon_once after receipt event failed: %s", exc)


class _IntakeFolderHandler(_FSEventHandler):  # type: ignore[misc]
    def __init__(self, root: Path, logger: logging.Logger) -> None:
        super().__init__()
        self._root = root
        self._log = logger

    def on_created(self, event: object) -> None:  # type: ignore[override]
        src = getattr(event, "src_path", "")
        self._log.debug("Intake folder event: %s", src)
        try:
            from llm_kosh.daemon import daemon_once
            daemon_once(self._root)
        except Exception as exc:
            self._log.warning("daemon_once after intake event failed: %s", exc)


class _ExternalFolderHandler(_FSEventHandler):  # type: ignore[misc]
    def __init__(self, root: Path, logger: logging.Logger) -> None:
        super().__init__()
        self._root = root
        self._log = logger

    def on_created(self, event: object) -> None:  # type: ignore[override]
        self._handle(event)

    def on_modified(self, event: object) -> None:  # type: ignore[override]
        self._handle(event)

    def _handle(self, event: object) -> None:
        if getattr(event, "is_directory", False):
            return
        src = Path(getattr(event, "src_path", ""))
        if not src.name or src.name.startswith("."):
            return
        lower_name = src.name.lower()
        ignored_endings = {
            ".tmp", ".pyc", ".db", ".sqlite", ".zip", ".exe", ".dll", ".log",
            ".db-wal", ".db-shm", ".sqlite-wal", ".sqlite-shm", ".journal",
            ".lock", ".partial", ".crdownload",
        }
        if any(lower_name.endswith(ending) for ending in ignored_endings):
            return
        try:
            from llm_kosh.engine.intake import intake_file_or_dir
            intake_file_or_dir(self._root, src)
            from llm_kosh.daemon import daemon_once
            daemon_once(self._root)
            self._log.info("External file ingested by watchdog: %s", src)
        except Exception as exc:
            self._log.warning("external file event failed for %s: %s", src, exc)


# ---------------------------------------------------------------------------
# ServiceRunner
# ---------------------------------------------------------------------------

class ServiceRunner:
    """Manages the full daemon lifecycle."""

    _PID_PATH = get_llmkosh_home() / "daemon.pid"
    _LOG_PATH = get_llmkosh_home() / "daemon.log"
    _HEALTH_PORT = 5556

    def __init__(self) -> None:
        self._shutdown_event = threading.Event()
        self._logger: Optional[logging.Logger] = None
        self._observers: list = []
        self._config: dict = {}

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    def run(self) -> None:
        """Main entry point: sets up everything and enters the run loop."""
        global _health_pid, _startup_time, _health_root
        _startup_time = time.time()
        _health_pid = os.getpid()

        self._config = get_global_config()
        env_root = os.environ.get("LLMKOSH_ROOT")
        cartridge_root = Path(env_root).expanduser().resolve() if env_root else get_default_cartridge_root()
        cartridge_root = cartridge_root.expanduser().resolve()
        _health_root = str(cartridge_root)

        self._handle_stale_pid()
        self._write_pid()
        self._setup_logging()

        log = self._logger
        assert log is not None

        self._install_signal_handlers()

        try:
            from llm_kosh.core.memory import ensure_root
            ensure_root(cartridge_root)
        except SystemExit:
            log.error("Cartridge root invalid: %s — daemon exiting. "
                      "Set LLMKOSH_ROOT or run `llm-kosh --root <path> init`.", cartridge_root)
            clear_pid(self._PID_PATH)
            raise SystemExit(1)
        except Exception as exc:
            log.warning("ensure_root failed: %s", exc)

        self._start_health_server()
        self._setup_watchdog_observers(cartridge_root)

        log.info("Daemon started (pid=%d, root=%s)", os.getpid(), cartridge_root)

        try:
            self._run_loop(cartridge_root)
        finally:
            self._shutdown(cartridge_root)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _handle_stale_pid(self) -> None:
        existing = read_pid(self._PID_PATH)
        if existing and existing != os.getpid() and is_running(existing):
            raise SystemExit(f"llm-kosh service is already running (pid={existing})")
        if existing and not is_running(existing):
            clear_pid(self._PID_PATH)

    def _write_pid(self) -> None:
        write_pid(self._PID_PATH)

    def _setup_logging(self) -> None:
        log_dir = self._LOG_PATH.parent
        log_dir.mkdir(parents=True, exist_ok=True)

        daemon_cfg = self._config.get("daemon", {})
        max_bytes: int = int(daemon_cfg.get("log_max_bytes", 10 * 1024 * 1024))
        backup_count: int = int(daemon_cfg.get("log_backup_count", 3))

        logger = logging.getLogger("llm_kosh.service")
        logger.setLevel(logging.DEBUG)

        if not logger.handlers:
            fh = logging.handlers.RotatingFileHandler(
                str(self._LOG_PATH),
                maxBytes=max_bytes,
                backupCount=backup_count,
                encoding="utf-8",
            )
            fh.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
            logger.addHandler(fh)

            sh = logging.StreamHandler(sys.stderr)
            sh.setLevel(logging.INFO)
            sh.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
            logger.addHandler(sh)

        self._logger = logger

    def _install_signal_handlers(self) -> None:
        shutdown_event = self._shutdown_event

        def _handle_sigterm(signum: int, frame: object) -> None:
            shutdown_event.set()

        signal.signal(signal.SIGTERM, _handle_sigterm)

        if hasattr(signal, "SIGINT"):
            signal.signal(signal.SIGINT, _handle_sigterm)

    def _start_health_server(self) -> None:
        server = HTTPServer(("127.0.0.1", self._HEALTH_PORT), _HealthHandler)
        t = threading.Thread(target=server.serve_forever, daemon=True, name="llmkosh-health")
        t.start()
        log = self._logger
        if log:
            log.info("Health server listening on port %d", self._HEALTH_PORT)

    def _setup_watchdog_observers(self, root: Path) -> None:
        if not _HAS_WATCHDOG:
            log = self._logger
            if log:
                log.info("watchdog not available; running in polling-only mode")
            return

        receipts_dir = root / "receipts"
        intake_dir = root / "intake"
        receipts_dir.mkdir(parents=True, exist_ok=True)
        intake_dir.mkdir(parents=True, exist_ok=True)

        log = self._logger
        assert log is not None

        receipt_obs = _Observer()
        receipt_obs.schedule(_ReceiptHandler(root, log), str(receipts_dir), recursive=False)
        receipt_obs.start()
        self._observers.append(receipt_obs)

        intake_obs = _Observer()
        intake_obs.schedule(_IntakeFolderHandler(root, log), str(intake_dir), recursive=False)
        intake_obs.start()
        self._observers.append(intake_obs)

        watched_dirs = self._config.get("daemon", {}).get("watched_directories", [])
        for watched in watched_dirs:
            watched_path = Path(watched).expanduser()
            if not watched_path.exists() or not watched_path.is_dir():
                log.warning("Skipping external watch path that does not exist: %s", watched_path)
                continue
            external_obs = _Observer()
            external_obs.schedule(_ExternalFolderHandler(root, log), str(watched_path), recursive=True)
            external_obs.start()
            self._observers.append(external_obs)
            log.info("Watchdog observer started for external folder: %s", watched_path)

        log.info("Watchdog observers started for receipts/, intake/, and configured external folders")

    def _run_loop(self, root: Path) -> None:
        daemon_cfg = self._config.get("daemon", {})
        poll_interval: float = float(daemon_cfg.get("poll_interval_seconds", 30))

        log = self._logger
        assert log is not None

        while not self._shutdown_event.is_set():
            try:
                from llm_kosh.daemon import daemon_once
                daemon_once(root)
            except Exception as exc:
                log.error("daemon_once error: %s", exc, exc_info=True)

            # Sleep in small increments so we can respond to shutdown quickly
            deadline = time.monotonic() + poll_interval
            while not self._shutdown_event.is_set():
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    break
                time.sleep(min(1.0, remaining))

    def _shutdown(self, root: Path) -> None:
        log = self._logger

        for obs in self._observers:
            try:
                obs.stop()
                obs.join(timeout=5)
            except Exception:
                pass
        self._observers.clear()

        clear_pid(self._PID_PATH)

        if log:
            log.info("Daemon stopped (pid=%d)", os.getpid())


# ---------------------------------------------------------------------------
# maybe_spawn
# ---------------------------------------------------------------------------

def maybe_spawn(root: Optional[Path] = None) -> None:
    """Check health endpoint; spawn daemon if not running.

    Forwards the active cartridge root via LLMKOSH_ROOT so the daemon
    serves the same cartridge the CLI is operating on. Skips if
    LLMKOSH_NO_AUTOSPAWN=1. If a recent spawn attempt failed, skips
    silently for 10 minutes instead of stalling every CLI invocation.
    """
    import urllib.request
    import subprocess

    if os.environ.get("LLMKOSH_NO_AUTOSPAWN"):
        return

    try:
        urllib.request.urlopen("http://127.0.0.1:5556/health", timeout=0.2)
        return  # already running
    except Exception:
        pass

    # Cooldown: don't re-attempt (and re-stall) within 10 minutes of a failure
    cooldown_marker = get_llmkosh_home() / "spawn_failed"
    try:
        if cooldown_marker.exists() and (time.time() - cooldown_marker.stat().st_mtime) < 600:
            return
    except OSError:
        pass

    env = dict(os.environ)
    if root is not None:
        env["LLMKOSH_ROOT"] = str(root)

    if getattr(sys, "frozen", False):
        cmd = [sys.executable, "service", "run"]
    else:
        cmd = [sys.executable, "-m", "llm_kosh.service", "run"]
    if sys.platform == "win32":
        spawn_kwargs: dict = {"creationflags": 0x00000008}  # DETACHED_PROCESS
    else:
        spawn_kwargs = {"start_new_session": True}

    subprocess.Popen(
        cmd,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        env=env,
        **spawn_kwargs,
    )
    print("Starting llm-kosh daemon in background...", file=sys.stderr)

    for _ in range(10):
        time.sleep(0.3)
        try:
            urllib.request.urlopen("http://127.0.0.1:5556/health", timeout=0.2)
            print("Daemon ready.", file=sys.stderr)
            try:
                cooldown_marker.unlink(missing_ok=True)
            except OSError:
                pass
            return
        except Exception:
            pass

    try:
        cooldown_marker.parent.mkdir(parents=True, exist_ok=True)
        cooldown_marker.write_text(str(time.time()))
    except OSError:
        pass
    print("Warning: daemon did not start. Running in direct mode "
          "(will not retry for 10 minutes; see ~/.llmkosh/daemon.log).", file=sys.stderr)


# ---------------------------------------------------------------------------
# Status helpers
# ---------------------------------------------------------------------------

def _get_pid() -> int:
    return read_pid(ServiceRunner._PID_PATH)


def _daemon_is_running() -> bool:
    return is_running(_get_pid())


def _health_check() -> dict:
    import urllib.request
    try:
        with urllib.request.urlopen("http://127.0.0.1:5556/health", timeout=1.0) as resp:
            return json.loads(resp.read())
    except Exception:
        return {}


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main() -> None:
    """Parse daemon sub-commands and dispatch."""
    parser = argparse.ArgumentParser(
        prog="llm-kosh-service",
        description="llm-kosh background daemon manager",
    )
    parser.add_argument(
        "action",
        choices=["run", "start", "stop", "restart", "status"],
        help="Daemon action",
    )
    args = parser.parse_args()

    if args.action == "run":
        runner = ServiceRunner()
        runner.run()

    elif args.action == "start":
        if _daemon_is_running():
            print("Daemon is already running (pid=%d)." % _get_pid(), file=sys.stderr)
            raise SystemExit(0)
        maybe_spawn()

    elif args.action == "stop":
        pid = _get_pid()
        if not is_running(pid):
            print("Daemon is not running.", file=sys.stderr)
            raise SystemExit(1)
        try:
            os.kill(pid, signal.SIGTERM)
            print("Sent SIGTERM to daemon (pid=%d)." % pid, file=sys.stderr)
        except OSError as exc:
            print("Failed to stop daemon: %s" % exc, file=sys.stderr)
            raise SystemExit(1)

    elif args.action == "restart":
        pid = _get_pid()
        if is_running(pid):
            try:
                os.kill(pid, signal.SIGTERM)
                # Wait briefly for it to stop
                for _ in range(20):
                    time.sleep(0.3)
                    if not is_running(pid):
                        break
            except OSError:
                pass
        maybe_spawn()

    elif args.action == "status":
        if _daemon_is_running():
            health = _health_check()
            pid = _get_pid()
            uptime = health.get("uptime_s", "?")
            root = health.get("root", "?")
            print("Service running (pid=%d, uptime=%ss, root=%s)" % (pid, uptime, root))
        else:
            print("Service is not running.")
            raise SystemExit(1)


if __name__ == "__main__":
    main()
