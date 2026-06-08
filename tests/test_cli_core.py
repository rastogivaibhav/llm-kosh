import json
from pathlib import Path
import pytest

def test_cli_init_and_status(runner, temp_workspace):
    # init
    code, out, err = runner("init", "--owner", "testuser", workspace=temp_workspace)
    assert code == 0
    
    # status
    code, out, err = runner("status", workspace=temp_workspace)
    assert code == 0

def test_cli_add_and_query(runner, temp_workspace):
    runner("init", workspace=temp_workspace)
    
    # add
    code, out, err = runner("add", "--kind", "note", "--title", "Test Memory", "--body", "This is a body", workspace=temp_workspace)
    assert code == 0
    
    # query
    code, out, err = runner("query", "body", workspace=temp_workspace)
    assert code == 0
    
    # query json
    code, out, err = runner("query", "body", "--json", workspace=temp_workspace)
    assert code == 0
    results = json.loads(out)
    assert len(results) >= 1
    assert "Test Memory" in results[0]["title"]

def test_cli_ingest(runner, temp_workspace, tmp_path):
    runner("init", workspace=temp_workspace)
    
    file_path = tmp_path / "test.md"
    file_path.write_text("# Heading\nSome content")
    
    code, out, err = runner("ingest", str(file_path), workspace=temp_workspace)
    assert code == 0
    

