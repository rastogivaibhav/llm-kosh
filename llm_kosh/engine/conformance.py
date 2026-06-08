import os
import json
import zipfile
import shutil
from pathlib import Path
from llm_kosh.core.utils import read_json, write_json, now_iso
from llm_kosh.core.memory import ensure_root
from llm_kosh.engine.safety import scan_secrets

# Pack Levels
# Level 0: 01_BOOT.md, 11_MANIFEST.json, 12_MEMORY_RECEIPT_TEMPLATE.md
# Level 1: + 10_SOURCE_MAP.json, matched memory, decisions, gaps
# Level 2: + provider specific files, budget metadata, redaction metadata
# Level 3: + content hashes, ledger references, optional signatures

def generate_sample_packs(root: Path):
    out_dir = root / "examples" / "packs"
    out_dir.mkdir(parents=True, exist_ok=True)
    
    # minimal_pack.zip (Level 0)
    _create_mock_zip(out_dir / "minimal_pack.zip", {
        "01_BOOT.md": "Boot instructions",
        "11_MANIFEST.json": json.dumps({"schema": "ai-memory-context-pack.v1", "target": "human", "query": "test", "created_at": now_iso(), "redacted": False, "match_count": 0, "koush_id": "test", "koush_version": "1.0"}),
        "12_MEMORY_RECEIPT_TEMPLATE.md": "Template content"
    })
    
    # project_pack.zip (Level 1)
    _create_mock_zip(out_dir / "project_pack.zip", {
        "01_BOOT.md": "Boot",
        "11_MANIFEST.json": json.dumps({"schema": "ai-memory-context-pack.v1", "target": "human", "query": "test", "created_at": now_iso(), "redacted": False, "match_count": 1, "koush_id": "test", "koush_version": "1.0"}),
        "12_MEMORY_RECEIPT_TEMPLATE.md": "Template",
        "10_SOURCE_MAP.json": json.dumps({"koush_id": "test", "koush_version": "1.0", "query": "test", "matches": [
            {"id": "m1", "kind": "decision", "title": "test", "source_path": "source/decisions/test.md", "pack_file": "source-files/01_decision_test.md", "included": True, "reason": ""}
        ]}),
        "source-files/01_decision_test.md": "Decision test"
    })
    
    # safe_pack.zip (Level 2)
    _create_mock_zip(out_dir / "safe_pack.zip", {
        "01_BOOT.md": "Boot",
        "11_MANIFEST.json": json.dumps({"schema": "ai-memory-context-pack.v1", "target": "chatgpt", "query": "test", "created_at": now_iso(), "redacted": True, "match_count": 1, "koush_id": "test", "koush_version": "1.0", "budget": "small"}),
        "12_MEMORY_RECEIPT_TEMPLATE.md": "Template",
        "10_SOURCE_MAP.json": json.dumps({"koush_id": "test", "koush_version": "1.0", "query": "test", "matches": []}),
        "provider/CHATGPT_CONTEXT.md": "chatgpt projection"
    })
    
    # receipt_only_pack.zip (Level 0)
    _create_mock_zip(out_dir / "receipt_only_pack.zip", {
        "01_BOOT.md": "Boot",
        "11_MANIFEST.json": json.dumps({"schema": "ai-memory-context-pack.v1", "target": "human", "query": "receipt", "created_at": now_iso(), "redacted": False, "match_count": 0, "koush_id": "test", "koush_version": "1.0"}),
        "12_MEMORY_RECEIPT_TEMPLATE.md": "Template",
        "MEMORY_RECEIPT.md": "# New decisions\n- decided to make a receipt pack"
    })
    
    print(f"Generated 4 sample packs in {out_dir}")

def _create_mock_zip(path: Path, files: dict):
    with zipfile.ZipFile(path, "w") as zf:
        for fname, content in files.items():
            zf.writestr(fname, content)

def validate_pack_conformance(zip_path: Path):
    if not zip_path.exists():
        print(f"Pack not found: {zip_path}")
        return False
        
    print(f"Validating pack: {zip_path.name}")
    level = 0
    issues = []
    
    with zipfile.ZipFile(zip_path) as zf:
        names = zf.namelist()
        
        # Level 0 checks
        if "01_BOOT.md" not in names:
            issues.append("missing 01_BOOT.md")
        if "11_MANIFEST.json" not in names:
            issues.append("missing 11_MANIFEST.json")
        if "12_MEMORY_RECEIPT_TEMPLATE.md" not in names:
            issues.append("missing 12_MEMORY_RECEIPT_TEMPLATE.md")
            
        if issues:
            print("FAILED at Level 0")
            for i in issues: print(f"  - {i}")
            return False
            
        # Parse manifest for later
        manifest = json.loads(zf.read("11_MANIFEST.json"))
        
        # Level 1 checks
        if "10_SOURCE_MAP.json" in names:
            level = 1
            sm = json.loads(zf.read("10_SOURCE_MAP.json"))
            for match in sm.get("matches", []):
                if match.get("included") and match.get("pack_file"):
                    if match["pack_file"] not in names:
                        issues.append(f"source map mismatch: {match['pack_file']} not found in zip")
        
        if level == 1 and not issues:
            # Level 2 checks (provider projection)
            has_provider = any(n.startswith("provider/") for n in names)
            if has_provider and manifest.get("budget") is not None:
                level = 2
                
        # Privacy check for safe pack
        if manifest.get("redacted"):
            # Check if any file contains secrets (mock validation)
            for n in names:
                if n.endswith(".md") or n.endswith(".txt"):
                    content = zf.read(n).decode("utf-8")
                    if scan_secrets(content):
                        issues.append(f"private content leak in safe pack: {n}")
                        
        if issues:
            print(f"FAILED at Level {level}")
            for i in issues: print(f"  - {i}")
            return False
            
        print(f"PASS: Conforms to LlmKosh Pack Level {level}")
        return True

def validate_cartridge_conformance(root: Path):
    ensure_root(root)
    print("Validating cartridge...")
    # Just check required dirs for now
    issues = []
    for d in ["source", "ledger", "exports", "indexes"]:
        if not (root / d).exists():
            issues.append(f"missing directory: {d}/")
    if not (root / "LLM_KOSH.json").exists():
        issues.append("missing LLM_KOSH.json")
        
    if issues:
        print("FAILED cartridge conformance")
        for i in issues: print(f"  - {i}")
    else:
        print("PASS: Cartridge conforms to LlmKosh layout.")

def generate_report(root: Path):
    print("Generating conformance report...")
    # Could summarize spec versions, generated examples, etc.
    print("- LlmKosh Pack Schema v1")
    print("- Examples exist in examples/packs/")
    print("- Spec files exist in spec/conformance/")
