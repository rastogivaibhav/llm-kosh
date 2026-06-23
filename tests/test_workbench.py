import pytest
from pathlib import Path
from llm_kosh.cli import main
from llm_kosh.engine.search import rebuild_index

def test_workbench_build(tmp_path, monkeypatch):
    monkeypatch.setenv("LLMKOSH_NO_AUTOSPAWN", "1")
    root = tmp_path / "cart"
    # init
    monkeypatch.setattr("sys.argv", ["llm-kosh", "--root", str(root), "init"])
    main()
    
    # add private memory
    monkeypatch.setattr("sys.argv", ["llm-kosh", "--root", str(root), "add", "--kind", "note", "--title", "Secret", "--body", "Private data", "--visibility", "private"])
    main()
    
    # add public memory
    monkeypatch.setattr("sys.argv", ["llm-kosh", "--root", str(root), "add", "--kind", "decision", "--title", "Public Decision", "--body", "Public data", "--visibility", "public"])
    main()
    
    rebuild_index(root)
    
    # build default (safe)
    monkeypatch.setattr("sys.argv", ["llm-kosh", "--root", str(root), "workbench", "build"])
    main()
    
    site = root / "exports" / "workbench"
    assert site.exists()
    assert (site / "index.html").exists()
    assert (site / "projects.html").exists()
    assert (site / "decisions.html").exists()
    assert (site / "data" / "memory_map.json").exists()
    
    # check that private body is NOT in the public files
    idx = (site / "index.html").read_text(encoding="utf-8")
    assert "1 private/blocked item(s) excluded" in idx
    
    # build with private
    monkeypatch.setattr("sys.argv", ["llm-kosh", "--root", str(root), "workbench", "build", "--include-private"])
    main()
    
    idx_priv = (site / "index.html").read_text(encoding="utf-8")
    assert "private/blocked item(s) excluded" not in idx_priv

def test_workbench_export(tmp_path, monkeypatch):
    monkeypatch.setenv("LLMKOSH_NO_AUTOSPAWN", "1")
    root = tmp_path / "cart2"
    monkeypatch.setattr("sys.argv", ["llm-kosh", "--root", str(root), "init"])
    main()
    
    # export safe
    monkeypatch.setattr("sys.argv", ["llm-kosh", "--root", str(root), "workbench", "export", "--safe"])
    main()
    
    zip_path = root / "exports" / "workbench_export.zip"
    assert zip_path.exists()

def test_workbench_clean(tmp_path, monkeypatch):
    monkeypatch.setenv("LLMKOSH_NO_AUTOSPAWN", "1")
    root = tmp_path / "cart3"
    monkeypatch.setattr("sys.argv", ["llm-kosh", "--root", str(root), "init"])
    main()
    
    monkeypatch.setattr("sys.argv", ["llm-kosh", "--root", str(root), "workbench", "build"])
    main()
    
    site = root / "exports" / "workbench"
    assert site.exists()
    
    monkeypatch.setattr("sys.argv", ["llm-kosh", "--root", str(root), "workbench", "clean"])
    main()
    
    assert not site.exists()
