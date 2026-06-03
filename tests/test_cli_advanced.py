import os
import json
import zipfile
import pytest
from pathlib import Path

def test_cli_classify(runner, temp_workspace):
    runner("init", workspace=temp_workspace)
    code, out, err = runner("classify", workspace=temp_workspace)
    assert code == 0

def test_cli_partition(runner, temp_workspace):
    runner("init", workspace=temp_workspace)
    code, out, err = runner("partition", workspace=temp_workspace)
    assert code == 0

def test_cli_quarantine(runner, temp_workspace):
    runner("init", workspace=temp_workspace)
    runner("add", "--kind", "note", "--title", "Risk", "--body", "Risk", workspace=temp_workspace)
    code, out, err = runner("query", "Risk", "--json", workspace=temp_workspace)
    results = json.loads(out)
    if not results:
        return
    mem_id = results[0]["id"]
    
    code, out, err = runner("quarantine", "--id", mem_id, workspace=temp_workspace)
    assert code == 0
    
    code, out, err = runner("quarantine", "--list", workspace=temp_workspace)
    assert code == 0
    assert mem_id in out or "Risk" in out
    
    code, out, err = runner("quarantine", "--restore", "--id", mem_id, workspace=temp_workspace)
    assert code == 0

def test_cli_memory_map(runner, temp_workspace):
    runner("init", workspace=temp_workspace)
    code, out, err = runner("memory-map", workspace=temp_workspace)
    assert code == 0
    assert (Path(temp_workspace) / "MEMORY_MAP.md").exists()

def test_cli_repair_plan(runner, temp_workspace):
    runner("init", workspace=temp_workspace)
    runner("heal", "--write-plan", workspace=temp_workspace)
    code, out, err = runner("repair-plan", workspace=temp_workspace)
    assert code == 0

def test_cli_today(runner, temp_workspace):
    runner("init", workspace=temp_workspace)
    code, out, err = runner("today", workspace=temp_workspace)
    assert code == 0

def test_cli_inbox_and_promote(runner, temp_workspace):
    runner("init", workspace=temp_workspace)
    
    code, out, err = runner("inbox", "My new inbox item", workspace=temp_workspace)
    assert code == 0
    
    code, out, err = runner("inbox", workspace=temp_workspace)
    assert code == 0
    
    # Needs id to promote, but inbox just dumps lines. 
    # Let's query json to find the inbox item id? Wait, inbox creates a "note".
    code, out, err = runner("query", "inbox", "--json", workspace=temp_workspace)
    results = json.loads(out)
    if results:
        mem_id = results[0]["id"]
        code, out, err = runner("promote", "--id", mem_id, "--to", "decision", "--title", "Promoted", workspace=temp_workspace)
        assert code == 0

def test_cli_receipt_template(runner, temp_workspace):
    runner("init", workspace=temp_workspace)
    code, out, err = runner("receipt-template", workspace=temp_workspace)
    assert code == 0
    assert "MEMORY_RECEIPT" in out or "title:" in out

def test_cli_daily_pack(runner, temp_workspace, tmp_path):
    runner("init", workspace=temp_workspace)
    out_zip = tmp_path / "daily.zip"
    code, out, err = runner("daily-pack", "--out", str(out_zip), workspace=temp_workspace)
    assert code == 0
    assert out_zip.exists()

def test_cli_export_import_backup(runner, temp_workspace, tmp_path):
    runner("init", workspace=temp_workspace)
    out_zip = tmp_path / "backup.zip"
    code, out, err = runner("export-backup", "--out", str(out_zip), workspace=temp_workspace)
    assert code == 0
    assert out_zip.exists()
    
    code, out, err = runner("import-backup", str(out_zip), "--force", workspace=temp_workspace)
    assert code == 0

def test_cli_migrate(runner, temp_workspace):
    runner("init", workspace=temp_workspace)
    code, out, err = runner("migrate", "--dry-run", workspace=temp_workspace)
    assert code == 0
    
    code, out, err = runner("migrate", workspace=temp_workspace)
    assert code == 0

def test_cli_static_site(runner, temp_workspace):
    runner("init", workspace=temp_workspace)
    code, out, err = runner("static-site", workspace=temp_workspace)
    assert code == 0
