import json
import pytest

def test_cli_import_chatgpt_dry_run(runner, temp_workspace, tmp_path):
    runner("init", workspace=temp_workspace)
    
    # Create fake chatgpt export
    fake_export = tmp_path / "conversations.json"
    fake_export.write_text(json.dumps([
        {"title": "Test Chat", "mapping": {"a": {"message": {"content": {"parts": ["Hello AI"]}}}}}
    ]))
    
    code, out, err = runner("import-chatgpt", str(fake_export), "--dry-run", workspace=temp_workspace)
    assert code == 0
    assert "would import" in out.lower() or "dry run" in out.lower() or "dry-run" in out.lower()
