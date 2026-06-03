import pytest
from pathlib import Path
from koush.cli import main
from koush.core.utils import read_json

def test_imports_flow(tmp_path, monkeypatch, capsys):
    root = tmp_path / "cart"
    monkeypatch.setattr("sys.argv", ["koush", "--root", str(root), "init"])
    main()
    
    # 1. Create a fixture
    fixture = tmp_path / "chatgpt_conversations.json"
    fixture.write_text("""[
        {
            "id": "123",
            "title": "A Chat",
            "create_time": "123456",
            "mapping": {
                "msg1": {
                    "message": {
                        "author": {"role": "user"},
                        "content": {"parts": ["Hello"]}
                    }
                }
            }
        }
    ]""")
    
    # 2. Preview
    monkeypatch.setattr("sys.argv", ["koush", "--root", str(root), "import", "preview", str(fixture)])
    main()
    out, _ = capsys.readouterr()
    assert '"provider": "chatgpt"' in out
    assert '"conversations_found": 1' in out
    assert '"messages_found": 1' in out
    
    # 3. Apply
    monkeypatch.setattr("sys.argv", ["koush", "--root", str(root), "import", "apply", str(fixture)])
    main()
    out, _ = capsys.readouterr()
    assert '"status": "applied"' in out
    
    # 4. Attempt duplicate apply
    monkeypatch.setattr("sys.argv", ["koush", "--root", str(root), "import", "apply", str(fixture)])
    main()
    out, _ = capsys.readouterr()
    assert '"status": "skipped"' in out
    
    # Get import ID
    import_list = read_json(root / "reports" / "imports.json")
    import_id = list(import_list.keys())[0]
    
    # 5. Rollback
    monkeypatch.setattr("sys.argv", ["koush", "--root", str(root), "import", "rollback", import_id])
    main()
    out, _ = capsys.readouterr()
    assert '"status": "ok"' in out
    assert "Rolled back 1 records" in out
    
    # Check that record is marked superseded
    record_path = import_list[import_id]["record_ids"][0]
    rec_text = (root / record_path).read_text(encoding="utf-8")
    assert "status: superseded" in rec_text
    
def test_migration_dryrun(tmp_path, monkeypatch, capsys):
    root = tmp_path / "cart"
    monkeypatch.setattr("sys.argv", ["koush", "--root", str(root), "init"])
    main()
    
    monkeypatch.setattr("sys.argv", ["koush", "--root", str(root), "migrate", "check"])
    main()
    out, _ = capsys.readouterr()
    assert '"status": "up_to_date"' in out
