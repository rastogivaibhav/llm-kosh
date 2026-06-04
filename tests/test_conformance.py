import pytest
from pathlib import Path
from llm_kosh.cli import main
import zipfile

def test_conformance_flow(tmp_path, monkeypatch, capsys):
    root = tmp_path / "cart"
    monkeypatch.setattr("sys.argv", ["llm-kosh", "--root", str(root), "init"])
    main()
    
    # 1. Generate sample packs
    monkeypatch.setattr("sys.argv", ["llm-kosh", "--root", str(root), "conformance", "generate-sample"])
    main()
    
    out, _ = capsys.readouterr()
    assert "Generated 4 sample packs" in out
    
    pack_dir = root / "examples" / "packs"
    assert (pack_dir / "minimal_pack.zip").exists()
    assert (pack_dir / "project_pack.zip").exists()
    
    # 2. Validate a Level 0 pack
    monkeypatch.setattr("sys.argv", ["llm-kosh", "--root", str(root), "conformance", "pack", str(pack_dir / "minimal_pack.zip")])
    main()
    out, _ = capsys.readouterr()
    assert "PASS: Conforms to LlmKosh Pack Level 0" in out
    
    # 3. Validate a Level 1 pack
    monkeypatch.setattr("sys.argv", ["llm-kosh", "--root", str(root), "conformance", "pack", str(pack_dir / "project_pack.zip")])
    main()
    out, _ = capsys.readouterr()
    assert "PASS: Conforms to LlmKosh Pack Level 1" in out
    
    # 4. Intentionally remove BOOT.md to trigger failure
    bad_pack = pack_dir / "bad_pack.zip"
    with zipfile.ZipFile(pack_dir / "minimal_pack.zip", "r") as z_in:
        with zipfile.ZipFile(bad_pack, "w") as z_out:
            for item in z_in.infolist():
                if item.filename != "01_BOOT.md":
                    z_out.writestr(item, z_in.read(item.filename))
                    
    monkeypatch.setattr("sys.argv", ["llm-kosh", "--root", str(root), "conformance", "pack", str(bad_pack)])
    main()
    out, _ = capsys.readouterr()
    assert "FAILED at Level 0" in out
    assert "missing 01_BOOT.md" in out

    # 5. Check report output
    monkeypatch.setattr("sys.argv", ["llm-kosh", "--root", str(root), "conformance", "report"])
    main()
    out, _ = capsys.readouterr()
    assert "LlmKosh Pack Schema v1" in out
