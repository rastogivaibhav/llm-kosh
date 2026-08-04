import json
import sys

from llm_kosh.cli import main
from llm_kosh.core.memory import init_cartridge
from llm_kosh.core.profile import (
    COMPANY_BRAIN_MODE,
    PERSONAL_MODE,
    cartridge_mode,
    set_cartridge_mode,
)


def test_new_cartridges_default_to_personal_mode(tmp_path):
    root = tmp_path / "cartridge"
    init_cartridge(root, "tester")

    assert cartridge_mode(root) == PERSONAL_MODE
    assert json.loads((root / "LLM_KOSH.json").read_text())['mode'] == PERSONAL_MODE


def test_company_brain_mode_is_explicit_and_persisted(tmp_path):
    root = tmp_path / "cartridge"
    init_cartridge(root, "tester")

    assert set_cartridge_mode(root, "company-brain") == COMPANY_BRAIN_MODE
    assert cartridge_mode(root) == COMPANY_BRAIN_MODE
    assert json.loads((root / "LLM_KOSH_POLICY.json").read_text())['mode'] == COMPANY_BRAIN_MODE


def test_legacy_cartridge_without_mode_remains_personal(tmp_path):
    root = tmp_path / "legacy"
    root.mkdir()
    (root / "LLM_KOSH.json").write_text(json.dumps({"version": "1.0.0"}))

    assert cartridge_mode(root) == PERSONAL_MODE


def test_cli_init_can_select_company_brain_mode(tmp_path, monkeypatch):
    root = tmp_path / "company"
    monkeypatch.setattr(
        sys, "argv", ["llm-kosh", "--root", str(root), "init", "--mode", "company-brain"]
    )

    main()

    assert cartridge_mode(root) == COMPANY_BRAIN_MODE


def test_reinitializing_a_cartridge_does_not_downgrade_its_mode(tmp_path):
    root = tmp_path / "company"
    init_cartridge(root, "tester")
    set_cartridge_mode(root, COMPANY_BRAIN_MODE)

    init_cartridge(root, "tester")

    assert cartridge_mode(root) == COMPANY_BRAIN_MODE
