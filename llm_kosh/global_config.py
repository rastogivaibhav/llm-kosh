"""Read ~/.llmkosh/config.toml. Use tomllib (3.11+) with tomli fallback."""

from pathlib import Path
from typing import Any, Dict

DEFAULT_CONFIG_TOML: str = """\
[cartridge]
default_root = "~/.llmkosh/cartridge"

[daemon]
poll_interval_seconds = 30
mode = "auto"
enabled_jobs = [
  "scan_intake",
  "process_intake_folder",
  "poll_watched_folders",
  "process_safe_receipts",
  "rebuild_stale_index",
  "regenerate_memory_map",
  "sync_reasoning_graph"
]
watched_directories = []
log_max_bytes = 10485760
log_backup_count = 3

[mcp]
enabled = true
allow_write = false
allow_mutate = false
allow_private = false

[server]
port = 5555
host = "127.0.0.1"
"""


def _load_toml(path: Path) -> Dict[str, Any]:
    """Attempt to parse a TOML file using the best available parser."""
    try:
        import tomllib  # Python 3.11+
        with open(path, "rb") as fh:
            return tomllib.load(fh)
    except ImportError:
        pass

    try:
        import tomli as tomllib  # type: ignore[no-redef]
        with open(path, "rb") as fh:
            return tomllib.load(fh)
    except ImportError:
        pass

    # Minimal fallback: parse only top-level key = "value" lines.
    # Section headers and list values are not handled — just return {}.
    result: Dict[str, Any] = {}
    try:
        text = path.read_text(encoding="utf-8")
        for line in text.splitlines():
            line = line.strip()
            if not line or line.startswith("#") or line.startswith("["):
                continue
            if "=" in line:
                key, _, raw_value = line.partition("=")
                key = key.strip()
                raw_value = raw_value.strip()
                # Only handle simple quoted-string values
                if raw_value.startswith('"') and raw_value.endswith('"'):
                    result[key] = raw_value[1:-1]
    except OSError:
        pass
    # Return empty dict so callers fall back to defaults
    return {}


def get_global_config() -> Dict[str, Any]:
    """Read ~/.llmkosh/config.toml and return parsed dict.

    Returns an empty dict if the file does not exist.
    """
    config_path = get_llmkosh_home() / "config.toml"
    if not config_path.exists():
        return {}
    try:
        return _load_toml(config_path)
    except Exception:
        return {}


def get_default_cartridge_root() -> Path:
    """Return the configured default cartridge root.

    Reads [cartridge] default_root from config.toml. Falls back to
    ~/.llmkosh/cartridge if the key is absent or config is missing.
    """
    config = get_global_config()
    try:
        raw = config["cartridge"]["default_root"]
        return Path(raw).expanduser()
    except (KeyError, TypeError):
        return Path.home() / ".llmkosh" / "cartridge"


def get_llmkosh_home() -> Path:
    """Return the llmkosh home directory (~/.llmkosh)."""
    return Path.home() / ".llmkosh"
