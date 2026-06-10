"""Integration tests for daemon lifecycle. Marked @pytest.mark.integration."""

import os
from pathlib import Path
from unittest import mock

import pytest

from llm_kosh.pid import clear_pid, is_running, read_pid, write_pid


pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# pid.py tests
# ---------------------------------------------------------------------------


def test_pid_write_read(tmp_path: Path) -> None:
    """write_pid writes the current process ID; read_pid returns it."""
    pid_file = tmp_path / "test.pid"
    write_pid(pid_file)
    assert read_pid(pid_file) == os.getpid()


def test_stale_pid_cleanup(tmp_path: Path) -> None:
    """A PID that belongs to a non-existent process is not running."""
    # PID 99999 is almost certainly not in use; if by chance it is, the test
    # will still be valid because is_running() returns True only when the
    # process exists AND we have permission to signal it.
    stale_pid = 99999
    pid_file = tmp_path / "stale.pid"
    pid_file.write_text(str(stale_pid), encoding="utf-8")
    assert is_running(stale_pid) is False


def test_clear_pid(tmp_path: Path) -> None:
    """clear_pid writes '0'; read_pid returns 0 afterwards."""
    pid_file = tmp_path / "clear.pid"
    write_pid(pid_file)
    assert read_pid(pid_file) != 0  # sanity: we wrote a real PID

    clear_pid(pid_file)
    assert read_pid(pid_file) == 0


# ---------------------------------------------------------------------------
# maybe_spawn tests
# ---------------------------------------------------------------------------


def test_maybe_spawn_skips_if_env_set(monkeypatch: pytest.MonkeyPatch) -> None:
    """maybe_spawn() does nothing when LLMKOSH_NO_AUTOSPAWN=1."""
    monkeypatch.setenv("LLMKOSH_NO_AUTOSPAWN", "1")

    with mock.patch("subprocess.Popen") as mock_popen:
        from llm_kosh.service import maybe_spawn
        maybe_spawn()
        mock_popen.assert_not_called()


# ---------------------------------------------------------------------------
# global_config tests
# ---------------------------------------------------------------------------


def test_global_config_defaults(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """When config.toml is missing, get_default_cartridge_root() returns a
    path that ends with '.llmkosh/cartridge' (or similar)."""
    # Point the home at a tmp dir with no config.toml
    monkeypatch.setenv("HOME", str(tmp_path))
    # On Windows, Path.home() uses USERPROFILE
    monkeypatch.setenv("USERPROFILE", str(tmp_path))

    # Force module-level cache to be bypassed by reimporting
    import importlib
    import llm_kosh.global_config as gc
    importlib.reload(gc)

    root = gc.get_default_cartridge_root()
    assert root.parts[-1] == "cartridge"
    assert ".llmkosh" in str(root)


# ---------------------------------------------------------------------------
# install tests
# ---------------------------------------------------------------------------


def test_install_create_home_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """create_home_dir() creates ~/.llmkosh and ~/.llmkosh/cartridge."""
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))

    import importlib
    import llm_kosh.global_config as gc
    importlib.reload(gc)

    import llm_kosh.install as install_mod
    importlib.reload(install_mod)

    install_mod.create_home_dir()

    llmkosh_home = tmp_path / ".llmkosh"
    assert llmkosh_home.is_dir(), "~/.llmkosh should be created"
    assert (llmkosh_home / "cartridge").is_dir(), "~/.llmkosh/cartridge should be created"
