import os
from pathlib import Path
import zipfile
import pytest

def test_cli_pack(runner, temp_workspace, tmp_path):
    runner("init", workspace=temp_workspace)
    runner("add", "--kind", "note", "--title", "Packable Memory", "--body", "Some packable content", workspace=temp_workspace)
    
    out_zip = tmp_path / "test_pack.zip"
    code, out, err = runner("pack", "packable", "--out", str(out_zip), workspace=temp_workspace)
    
    assert code == 0
    assert out_zip.exists()
    
    with zipfile.ZipFile(out_zip, 'r') as z:
        files = z.namelist()
        assert len(files) > 0
        
def test_cli_validate_pack(runner, temp_workspace, tmp_path):
    runner("init", workspace=temp_workspace)
    runner("add", "--kind", "note", "--title", "Valid Memory", "--body", "body", workspace=temp_workspace)
    
    out_zip = tmp_path / "valid_pack.zip"
    runner("pack", "Valid", "--out", str(out_zip), workspace=temp_workspace)
    
    code, out, err = runner("validate-pack", str(out_zip), workspace=temp_workspace)
    assert code == 0
    
def test_cli_explain_pack(runner, temp_workspace, tmp_path):
    runner("init", workspace=temp_workspace)
    runner("add", "--kind", "note", "--title", "Explain Memory", "--body", "body", workspace=temp_workspace)
    
    out_zip = tmp_path / "explain_pack.zip"
    runner("pack", "Explain", "--out", str(out_zip), workspace=temp_workspace)
    
    code, out, err = runner("explain-pack", str(out_zip), workspace=temp_workspace)
    assert code == 0

def test_cli_safe_pack(runner, temp_workspace, tmp_path):
    runner("init", workspace=temp_workspace)
    runner("add", "--kind", "note", "--title", "Safe Memory", "--body", "body", workspace=temp_workspace)
    
    out_zip = tmp_path / "safe_pack.zip"
    code, out, err = runner("safe-pack", "Safe", "--out", str(out_zip), workspace=temp_workspace)
    assert code == 0
    assert out_zip.exists()
