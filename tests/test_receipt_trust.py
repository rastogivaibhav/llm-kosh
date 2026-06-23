import pytest
from pathlib import Path
from llm_kosh.cli import main
import json

def test_receipt_trust_flow(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("LLMKOSH_NO_AUTOSPAWN", "1")
    root = tmp_path / "cart"
    monkeypatch.setattr("sys.argv", ["llm-kosh", "--root", str(root), "init"])
    main()
    
    # Create a mock receipt
    receipt = root / "receipts" / "MEMORY_RECEIPT.md"
    receipt.parent.mkdir(exist_ok=True)
    receipt.write_text("""
# New decisions
- [project: test] Decide to test receipt logic:: We need to test the receipt review.

# Corrections
- [ref: memory.id] Fix typo:: Fixed typo in memory.

# Generated files
- [project: src] Added main.py:: Print hello world.

# Open gaps
- [project: tests] Missing tests:: We need to add tests for main.py.
""", encoding="utf-8")

    # 1. Validate
    monkeypatch.setattr("sys.argv", ["llm-kosh", "--root", str(root), "validate-receipt", str(receipt)])
    main()
    out, _ = capsys.readouterr()
    assert "Validating MEMORY_RECEIPT.md..." in out
    assert "decisions_found: 1" in out
    
    # 2. Review
    monkeypatch.setattr("sys.argv", ["llm-kosh", "--root", str(root), "review-receipt", str(receipt)])
    main()
    out, _ = capsys.readouterr()
    assert "Review rev_" in out
    
    # Extract review_id
    rev_id = out.split("Review ")[1].split()[0]
    
    jpath = root / "reports" / "receipt_reviews" / f"{rev_id}.json"
    assert jpath.exists()
    
    # 3. Absorb --review
    monkeypatch.setattr("sys.argv", ["llm-kosh", "--root", str(root), "absorb", str(receipt), "--review"])
    main()
    out, _ = capsys.readouterr()
    assert "Generated review rev_" in out
    
    rev_id_2 = out.split("Generated review ")[1].split()[0]
    jpath2 = root / "reports" / "receipt_reviews" / f"{rev_id_2}.json"
    
    # 4. Absorb --apply-review on untrusted
    monkeypatch.setattr("sys.argv", ["llm-kosh", "--root", str(root), "absorb", "--apply-review", rev_id_2])
    main()
    out, _ = capsys.readouterr()
    assert "Cannot apply: Review" in out
    
    # 5. Trust review
    monkeypatch.setattr("sys.argv", ["llm-kosh", "--root", str(root), "trust-receipt", rev_id_2, "--trusted"])
    main()
    
    report = json.loads(jpath2.read_text())
    assert report["trust_state"] == "trusted"
    
    # 6. Apply trusted review
    monkeypatch.setattr("sys.argv", ["llm-kosh", "--root", str(root), "absorb", "--apply-review", rev_id_2])
    main()
    
    out, _ = capsys.readouterr()
    assert "decisions added:        1" in out
    
    # 7. Check list
    monkeypatch.setattr("sys.argv", ["llm-kosh", "--root", str(root), "receipt", "list"])
    main()
    out, _ = capsys.readouterr()
    assert "TRUSTED" in out
    
    # 8. Check show
    monkeypatch.setattr("sys.argv", ["llm-kosh", "--root", str(root), "receipt", "show", rev_id_2])
    main()
    out, _ = capsys.readouterr()
    assert "Status:** trusted" in out
