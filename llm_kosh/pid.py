"""PID file utilities shared by service.py and cli.py."""

import os
from pathlib import Path


def write_pid(path: Path) -> None:
    """Write the current process ID to path."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(str(os.getpid()), encoding="utf-8")


def read_pid(path: Path) -> int:
    """Return the integer PID stored in path, or 0 if missing or invalid."""
    try:
        return int(path.read_text(encoding="utf-8").strip())
    except (FileNotFoundError, ValueError, OSError):
        return 0


def is_running(pid: int) -> bool:
    """Return True if a process with the given PID is running.

    Uses os.kill(pid, 0) which sends no signal but raises OSError if the
    process does not exist or we have no permission to signal it.
    A pid of 0 always returns False.
    """
    if pid == 0:
        return False
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def clear_pid(path: Path) -> None:
    """Write '0' to path, effectively marking the PID slot as unused."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("0", encoding="utf-8")
