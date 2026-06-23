import json
import sys

from llm_kosh import install


def test_setup_does_not_reinstall_the_running_package(monkeypatch):
    calls = []
    monkeypatch.setattr(install, "clean_local_state", lambda: calls.append("clean"))
    monkeypatch.setattr(install, "create_home_dir", lambda: calls.append("home"))
    monkeypatch.setattr(install, "write_default_config", lambda: calls.append("config"))
    monkeypatch.setattr(install, "init_default_cartridge", lambda: calls.append("init"))
    monkeypatch.setattr(install, "register_os_service", lambda: calls.append("service") or True)
    monkeypatch.setattr(install, "patch_claude_desktop_config", lambda yes=False: calls.append("mcp"))
    monkeypatch.setattr(install, "check_path_variable", lambda: calls.append("path"))
    monkeypatch.setattr(
        install,
        "repair_python_package",
        lambda: (_ for _ in ()).throw(AssertionError("setup must not invoke pip")),
    )

    install.run_install(yes=True)

    assert calls == ["home", "config", "init", "service", "mcp", "path"]


def test_claude_config_uses_absolute_python_module_command(tmp_path, monkeypatch):
    config_path = tmp_path / "claude_desktop_config.json"
    root = tmp_path / "cartridge"
    monkeypatch.setattr(install, "_claude_desktop_config_path", lambda: config_path)
    monkeypatch.setattr(install, "get_default_cartridge_root", lambda: root)
    monkeypatch.setattr(install, "_python_exe", lambda: str(tmp_path / "python"))

    install.patch_claude_desktop_config(yes=True)

    entry = json.loads(config_path.read_text(encoding="utf-8"))["mcpServers"]["llm-kosh"]
    assert entry["command"] == str(tmp_path / "python")
    assert entry["args"][:3] == ["-m", "llm_kosh.cli", "--root"]
    assert entry["args"][-1] == "mcp-server"


def test_frozen_commands_reenter_the_cli(monkeypatch):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(install, "_python_exe", lambda: "llm-kosh.exe")

    assert install._service_command() == ["llm-kosh.exe", "service", "run"]
    assert install._mcp_command("C:/cartridge") == (
        "llm-kosh.exe",
        ["--root", "C:/cartridge", "mcp-server"],
    )
