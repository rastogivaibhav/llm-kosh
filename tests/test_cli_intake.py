import pytest
import os
import json
from pathlib import Path

from llm_kosh.core.memory import init_cartridge, ensure_root
from llm_kosh.engine.intake import intake_scan, intake_list, intake_status, intake_validate, intake_review, intake_apply, intake_reject, intake_quarantine

@pytest.fixture
def intake_workspace(temp_workspace):
    root = Path(temp_workspace)
    init_cartridge(root, "tester")
    return root

def write_receipt(root: Path, name: str, content: str) -> Path:
    p = root / "receipts" / name
    p.parent.mkdir(exist_ok=True)
    p.write_text(content, encoding="utf-8")
    return p

def test_intake_scan_receipt(intake_workspace):
    root = intake_workspace
    write_receipt(root, "MEMORY_RECEIPT_1.md", "# MEMORY_RECEIPT\n## New decisions\n- test :: test\n")
    
    records = intake_scan(root)
    assert len(records) == 1
    assert records[0]["status"] == "pending"
    assert records[0]["source_type"] == "receipt"
    
    # scan again should not duplicate
    records2 = intake_scan(root)
    assert len(records2) == 0

def test_intake_validate(intake_workspace):
    root = intake_workspace
    write_receipt(root, "MEMORY_RECEIPT_VALID.md", "# MEMORY_RECEIPT\n## New decisions\n- test :: test\n")
    write_receipt(root, "MEMORY_RECEIPT_INVALID.md", "just some text without sections")
    
    records = intake_scan(root)
    assert len(records) == 2
    
    r1, r2 = records[0], records[1]
    
    val1 = intake_validate(root, r1["intake_id"])
    val2 = intake_validate(root, r2["intake_id"])
    
    # We don't know which is which by order, so let's check by status after
    from llm_kosh.core.utils import read_json
    st1 = read_json(root / "intake" / ("validated" if val1 else "pending") / f"{r1['intake_id']}.json")["status"]
    st2 = read_json(root / "intake" / ("validated" if val2 else "pending") / f"{r2['intake_id']}.json")["status"]
    
    statuses = {st1, st2}
    assert "validated" in statuses
    assert "pending" in statuses

def test_intake_review_and_apply(intake_workspace):
    root = intake_workspace
    write_receipt(root, "MEMORY_RECEIPT.md", "# MEMORY_RECEIPT\n## New decisions\n- apply me :: yes\n")
    
    records = intake_scan(root)
    r_id = records[0]["intake_id"]
    
    report_path = intake_review(root, r_id)
    assert report_path.exists()
    assert "apply me" in report_path.read_text()
    
    res = intake_apply(root, r_id)
    assert res.get("decisions") == 1
    
    stats = intake_status(root)
    assert stats["applied"] == 1
    assert stats["pending"] == 0

def test_intake_reject_and_quarantine(intake_workspace):
    root = intake_workspace
    write_receipt(root, "MEMORY_RECEIPT_REJECT.md", "# MEMORY_RECEIPT\n")
    write_receipt(root, "MEMORY_RECEIPT_QUARANTINE.md", "# MEMORY_RECEIPT\n2\n")
    
    records = intake_scan(root)
    
    intake_reject(root, records[0]["intake_id"])
    intake_quarantine(root, records[1]["intake_id"])
    
    stats = intake_status(root)
    assert stats["rejected"] == 1
    assert stats["quarantined"] == 1

def test_intake_list_and_status(intake_workspace):
    root = intake_workspace
    write_receipt(root, "test.md", "hello")
    intake_scan(root)
    
    items = intake_list(root)
    assert len(items) == 1
    assert len(intake_list(root, status="pending")) == 1
    assert intake_list(root, status="applied") == []

    stats = intake_status(root)
    assert stats["pending"] == 1
