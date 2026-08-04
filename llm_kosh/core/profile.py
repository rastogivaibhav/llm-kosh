"""Cartridge product profiles.

The Python distribution is one product, but a cartridge can be used either as
personal memory or as a governed Company Brain.  Keep this decision in the
cartridge rather than inferring it from which command happened to run.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict

from llm_kosh.core.utils import read_json, write_json


PERSONAL_MODE = "personal"
COMPANY_BRAIN_MODE = "company_brain"
DEFAULT_MODE = PERSONAL_MODE
MODES = frozenset({PERSONAL_MODE, COMPANY_BRAIN_MODE})


def normalize_mode(value: str | None) -> str:
    """Return the canonical mode name, accepting the human-facing alias."""
    candidate = (value or DEFAULT_MODE).strip().lower().replace("-", "_")
    if candidate == "company":
        candidate = COMPANY_BRAIN_MODE
    if candidate not in MODES:
        raise ValueError(
            f"Unsupported cartridge mode: {value!r}. "
            f"Choose {PERSONAL_MODE!r} or {COMPANY_BRAIN_MODE!r}."
        )
    return candidate


def cartridge_mode(root: Path) -> str:
    """Read the cartridge mode, defaulting legacy cartridges to personal."""
    config = read_json(root / "LLM_KOSH.json", {})
    policy = read_json(root / "LLM_KOSH_POLICY.json", {})
    if not policy:
        policy = read_json(root / "CARTRIDGE_POLICY.json", {})
    return normalize_mode(config.get("mode") or policy.get("mode"))


def set_cartridge_mode(root: Path, mode: str) -> str:
    """Persist a mode in both cartridge metadata and policy files."""
    canonical = normalize_mode(mode)
    root.mkdir(parents=True, exist_ok=True)

    config_path = root / "LLM_KOSH.json"
    config: Dict[str, object] = read_json(config_path, {})
    config["mode"] = canonical
    write_json(config_path, config)

    policy_path = root / "LLM_KOSH_POLICY.json"
    policy: Dict[str, object] = read_json(policy_path, {})
    if not policy:
        policy = read_json(root / "CARTRIDGE_POLICY.json", {})
    policy["mode"] = canonical
    write_json(policy_path, policy)
    return canonical


def is_company_brain(root: Path) -> bool:
    return cartridge_mode(root) == COMPANY_BRAIN_MODE

