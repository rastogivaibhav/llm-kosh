import os
import pytest
from pathlib import Path

def test_engine_audit_and_heal(temp_workspace):
    from llm_kosh.core.memory import init_cartridge
    from llm_kosh.engine.commands import audit, heal_safe
    
    root = Path(temp_workspace)
    init_cartridge(root, "user")
    
    # inject bad files to trigger audit warnings
    active = root / "source" / "notes"
    active.mkdir(parents=True, exist_ok=True)
    
    # 1. Missing frontmatter
    (active / "bad1.md").write_text("No frontmatter here")
    
    # 2. Duplicate ID
    (active / "dup1.md").write_text("---\nid: dup_123\ntype: note\n---\nbody")
    (active / "dup2.md").write_text("---\nid: dup_123\ntype: note\n---\nbody")
    
    # 3. Secret in shareable
    (active / "sec.md").write_text("---\nid: sec_123\ntype: note\nvisibility: shareable\n---\nAPI_KEY=AKIAIOSFODNN7EXAMPLE\n")
    
    # 4. Dangling superseded
    (active / "dang.md").write_text("---\nid: dang_123\ntype: note\nsuperseded_by: missing_456\n---\nbody")
    
    # 5. Duplicate Title
    (active / "title1.md").write_text("---\nid: t1\ntype: note\ntitle: Same Title\n---\n")
    (active / "title2.md").write_text("---\nid: t2\ntype: note\ntitle: Same Title\n---\n")
    
    # 6. Generated file without source
    (active / "gen.md").write_text("---\nid: g1\ntype: file\n---\n")
    
    report = audit(root)
    assert len(report["issues"]) > 0
    
    # heal
    heal_safe(root, write_plan=True)
    plan_file = root / "reports" / "REPAIR_PLAN.json"
    assert plan_file.exists()
    
    heal_safe(root, apply_plan=plan_file)
    heal_safe(root, fix_visibility=True)

def test_engine_search_and_index(temp_workspace):
    from llm_kosh.core.memory import init_cartridge, add_memory
    from llm_kosh.engine.search import rebuild_index, query_memory, semantic_search, print_query_results
    import io
    from contextlib import redirect_stdout
    
    root = Path(temp_workspace)
    init_cartridge(root, "user")
    add_memory(root, "note", "Test Search", "Body search content")
    
    rebuild_index(root, force=True)
    
    results = query_memory(root, "search", limit=10)
    assert len(results) > 0

def test_engine_retrieval_weights(temp_workspace):
    from llm_kosh.core.memory import init_cartridge, add_memory
    from llm_kosh.engine.search import rebuild_index, query_memory
    from llm_kosh.core.utils import read_json, write_json
    
    root = Path(temp_workspace)
    init_cartridge(root, "user")
    add_memory(root, "note", "Test Search Note", "Body search content")
    
    rebuild_index(root, force=True)
    
    # Run query with default weights
    results_default = query_memory(root, "search", limit=1)
    assert len(results_default) > 0
    score_default = results_default[0]["score"]
    
    # Inject zero search weights into LLM_KOSH.json
    cfg_path = root / "LLM_KOSH.json"
    cfg = read_json(cfg_path, {})
    cfg["retrieval_weights"] = {
        "beta_sem": 0.0,
        "beta_proc": 0.0,
        "alpha": 0.02,
        "gamma": 0.5,
        "tau": 0.5
    }
    write_json(cfg_path, cfg)
    
    # Run query with modified weights
    results_decayed = query_memory(root, "search", limit=1)
    assert len(results_decayed) > 0
    score_decayed = results_decayed[0]["score"]
    
    # Score must be exactly 0.0 because semantic and procedural biases are both zeroed out
    assert score_decayed == 0.0

def test_engine_compiler(temp_workspace, tmp_path):
    from llm_kosh.core.memory import init_cartridge, add_memory
    from llm_kosh.engine.compiler import pack_context, explain_pack
    root = Path(temp_workspace)
    init_cartridge(root, "user")
    add_memory(root, "note", "Secret Note", "AKIAIOSFODNN7EXAMPLE")
    add_memory(root, "decision", "Dec", "Body")
    
    out_zip = tmp_path / "out.zip"
    pack_context(root, "", "chatgpt", out_zip, redact=True)
    assert out_zip.exists()
    
    explain_pack(out_zip)
    
def test_engine_daemon(temp_workspace):
    from llm_kosh.daemon import daemon_once
    # Just checking it imports without error
    pass
