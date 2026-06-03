import os
import json
import pytest
from pathlib import Path

def test_cli_import_claude(runner, temp_workspace, tmp_path):
    runner("init", workspace=temp_workspace)
    fake_export = tmp_path / "conversations.json"
    fake_export.write_text(json.dumps([
        {"name": "Claude Chat", "chat_messages": [{"sender": "human", "text": "Hi"}]}
    ]))
    code, out, err = runner("import-claude", str(fake_export), "--dry-run", workspace=temp_workspace)
    assert code == 0

def test_cli_import_gemini(runner, temp_workspace, tmp_path):
    runner("init", workspace=temp_workspace)
    fake_export = tmp_path / "MyActivity.json"
    fake_export.write_text(json.dumps([
        {"header": "Gemini", "title": "Gemini Chat"}
    ]))
    code, out, err = runner("import-gemini", str(fake_export), "--dry-run", workspace=temp_workspace)
    assert code == 0

def test_cli_import_generic(runner, temp_workspace, tmp_path):
    runner("init", workspace=temp_workspace)
    fake_export = tmp_path / "test.md"
    fake_export.write_text("Hello there")
    code, out, err = runner("import-generic", str(fake_export), "--dry-run", workspace=temp_workspace)
    assert code == 0

def test_cli_import_report(runner, temp_workspace):
    runner("init", workspace=temp_workspace)
    code, out, err = runner("import-report", workspace=temp_workspace)
    assert code == 0
