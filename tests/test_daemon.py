import pytest
from pathlib import Path
from koush.cli import main
from koush.core.utils import read_json

def test_daemon_flow(tmp_path, monkeypatch, capsys):
    root = tmp_path / "cart"
    monkeypatch.setattr("sys.argv", ["koush", "--root", str(root), "init"])
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
    policy_path = root / "KOUSH_POLICY.json"
    policy_path.write_text('{"daemon": {"enabled_jobs": ["process_safe_receipts"]}}')

    # 3. Run daemon once
    monkeypatch.setattr("sys.argv", ["koush", "--root", str(root), "daemon", "once"])
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
    monkeypatch.setattr("sys.argv", ["koush", "--root", str(root), "daemon", "status"])
    main()
    out, _ = capsys.readouterr()
    assert "[SUCCESS] process_safe_receipts" in out
