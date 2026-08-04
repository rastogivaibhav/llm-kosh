import pytest
import json
from pathlib import Path
from llm_kosh.cli import main
from llm_kosh.core.utils import read_json
from llm_kosh.core.memory import init_cartridge
from llm_kosh.core.profile import set_cartridge_mode
from llm_kosh.daemon import job_poll_watched_folders

def test_daemon_flow(tmp_path, monkeypatch, capsys):
    root = tmp_path / "cart"
    monkeypatch.setattr("sys.argv", ["llm-kosh", "--root", str(root), "init"])
    main()
    
    # 1. Provide a receipt
    receipt = root / "receipts" / "MEMORY_RECEIPT_1.md"
    receipt.parent.mkdir(exist_ok=True)
    receipt.write_text("""
# New decisions
- [project: test] Decide to test daemon:: Testing.
""", encoding="utf-8")

    # High impact receipt
    receipt_high = root / "receipts" / "MEMORY_RECEIPT_2.md"
    receipt_high.write_text("""
# Corrections
- [ref: some_id] Delete everything:: I will delete all context.
""", encoding="utf-8")

    # 2. Configure policy
    policy_path = root / "LLM_KOSH_POLICY.json"
    policy_path.write_text('{"daemon": {"enabled_jobs": ["process_safe_receipts"]}}')

    # 3. Run daemon once
    monkeypatch.setattr("sys.argv", ["llm-kosh", "--root", str(root), "daemon", "once"])
    main()
    out, _ = capsys.readouterr()
    
    # Check it ran
    assert "[Daemon] Running 1 scheduled jobs" in out
    
    # Check status.json
    status = read_json(root / "reports" / "daemon" / "status.json")
    assert "process_safe_receipts" in status["jobs"]
    assert status["jobs"]["process_safe_receipts"]["status"] == "success"
    
    # Check events log
    log = (root / "reports" / "daemon" / "events.jsonl").read_text()
    assert "receipt_absorbed" in log
    assert "MEMORY_RECEIPT_1.md" in log
    
    assert "receipt_held" in log
    assert "MEMORY_RECEIPT_2.md" in log
    
    # Check processed directory
    assert (root / "receipts" / "processed" / "MEMORY_RECEIPT_1.md").exists()
    assert (root / "receipts" / "MEMORY_RECEIPT_2.md").exists() # Left alone because it's risky
    
    # 4. Check status command
    monkeypatch.setattr("sys.argv", ["llm-kosh", "--root", str(root), "daemon", "status"])
    main()
    out, _ = capsys.readouterr()
    assert "[SUCCESS] process_safe_receipts" in out


def test_watched_folder_registers_reference_without_copying(tmp_path):
    root = tmp_path / "cart"
    source = tmp_path / "existing-source"
    source.mkdir()
    init_cartridge(root, "tester")
    set_cartridge_mode(root, "company_brain")
    watched_file = source / "notes.md"
    watched_file.write_text("Keep this file in place.", encoding="utf-8")
    (root / "LLM_KOSH_POLICY.json").write_text(json.dumps({
        "daemon": {"watched_directories": [str(source)]}
    }), encoding="utf-8")

    ok, message = job_poll_watched_folders(root)

    assert ok is True
    assert "Referenced 1 files" in message
    assert watched_file.read_text(encoding="utf-8") == "Keep this file in place."
    assert not any(path.name == "notes.md" for path in root.rglob("*"))
    ledger = read_json(root / "reports" / "daemon" / "watched_files_ledger.json")
    entry = ledger[str(watched_file.resolve())]
    assert isinstance(entry, float)
    from llm_kosh.company_brain.store import CompanyBrainStore
    assert CompanyBrainStore(root).health()["references"] == 1


def test_personal_mode_registers_configured_source_without_copying(tmp_path):
    root = tmp_path / "cart"
    source = tmp_path / "existing-source"
    source.mkdir()
    init_cartridge(root, "tester")
    watched_file = source / "notes.md"
    watched_file.write_text("Personal source stays outside the cartridge.", encoding="utf-8")
    (root / "LLM_KOSH_POLICY.json").write_text(json.dumps({
        "daemon": {"watched_directories": [str(source)]}
    }), encoding="utf-8")

    ok, message = job_poll_watched_folders(root)

    assert ok is True
    assert "Referenced 1 files" in message
    assert not any(path.name == "notes.md" for path in root.rglob("*"))
    from llm_kosh.company_brain.store import CompanyBrainStore
    assert CompanyBrainStore(root).health()["references"] == 1
