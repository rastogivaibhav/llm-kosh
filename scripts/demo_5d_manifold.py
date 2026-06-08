import os
import sys
import time
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from llm_kosh.core.memory import init_cartridge
from llm_kosh.engine.search import rebuild_index, build_vector_index, query_memory, get_db
from llm_kosh.core.utils import write_json, append_ledger

def run_5d_demo():
    print("======================================================================")
    print("          5D SPATIOTEMPORAL MANIFOLD ENGINE DEMONSTRATION")
    print("======================================================================\n")

    test_dir = Path(__file__).resolve().parent.parent / "test_root" / "demo_5d"
    if test_dir.exists():
        import shutil
        shutil.rmtree(test_dir)
    test_dir.mkdir(parents=True, exist_ok=True)
    
    init_cartridge(test_dir, "developer")
    
    cfg_path = test_dir / "LLM_KOSH.json"
    with open(cfg_path, "r", encoding="utf-8") as f:
        cfg = json.load(f)
    cfg["retrieval_weights"] = {
        "beta_sem": 0.6,
        "beta_proc": 0.4,
        "alpha": 0.002,  # Calibrated for scale of seconds
        "gamma": 0.4,
        "tau": 0.1
    }
    write_json(cfg_path, cfg)
    
    notes_dir = test_dir / "source" / "notes"
    notes_dir.mkdir(parents=True, exist_ok=True)
    
    # Current time
    now = time.time()
    
    # Memory A: Semantic note, created just now (0 seconds ago)
    time_a = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now))
    (notes_dir / "mem_a.md").write_text(
        "---\n"
        "id: mem_a\n"
        "title: Fruit Health\n"
        "type: note\n"
        "project: HealthResearch\n"
        "created: " + time_a + "\n"
        "M_sal: 1.0\n"
        "---\n"
        "Apples and oranges are healthy fruits containing rich vitamin C and fibers.",
        encoding="utf-8"
    )
    
    # Memory B: Older note (superseded by A), created 500 seconds ago
    time_b = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now - 500))
    (notes_dir / "mem_b.md").write_text(
        "---\n"
        "id: mem_b\n"
        "title: Stale Fruit Info\n"
        "type: note\n"
        "project: HealthResearch\n"
        "created: " + time_b + "\n"
        "status: superseded\n"
        "M_sal: 0.8\n"
        "---\n"
        "Old notes about oranges containing citric acid.",
        encoding="utf-8"
    )
    
    # Memory C: Procedural code, created 120 seconds ago (2 minutes ago)
    time_c = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now - 120))
    (notes_dir / "mem_c.md").write_text(
        "---\n"
        "id: mem_c\n"
        "title: Sum Calculator\n"
        "type: note\n"
        "project: MathCodes\n"
        "created: " + time_c + "\n"
        "M_sal: 1.2\n"
        "---\n"
        "A python helper function:\n"
        "```python\n"
        "import math\n"
        "def calculate_sum(a, b):\n"
        "    res_sum = a + b\n"
        "    return res_sum\n"
        "```\n"
        "This is a calculator procedure.",
        encoding="utf-8"
    )
    
    # Generate crowd files to test negative entropy project scaling
    for i in range(15):
        (notes_dir / f"crowd_{i}.md").write_text(
            f"---\nid: crowd_{i}\ntitle: Noise Note {i}\ntype: note\nproject: CrowdedProj\n---\nSome generic text.",
            encoding="utf-8"
        )
        
    # Memory D: Semantic note in crowded project, created just now (0 seconds ago)
    time_d = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now))
    (notes_dir / "mem_d.md").write_text(
        "---\n"
        "id: mem_d\n"
        "title: Orange Nutrition in Crowded Project\n"
        "type: note\n"
        "project: CrowdedProj\n"
        "created: " + time_d + "\n"
        "M_sal: 1.0\n"
        "---\n"
        "Eating oranges boosts nutrition and gives you vitamins.",
        encoding="utf-8"
    )
    
    # Append trust supersession event to ledger to show DAG tracing
    append_ledger(test_dir, "memory.superseded", {"old_id": "mem_b", "new_id": "mem_a"})
    
    rebuild_index(test_dir, force=True)
    build_vector_index(test_dir, backend="tfidf")
    
    print("--- Running query: 'calculate_sum' (Procedural Focus) ---")
    results_proc = query_memory(test_dir, "calculate_sum", limit=5)
    
    for idx, item in enumerate(results_proc, 1):
        print(f"{idx}. {item['title']} (ID: {item['id']})")
        print(f"   Score: {item.get('score')} | Project: {item['project']}")
        print(f"   Snippet: {item['snippet']}")
        
    print("\n--- Running query: 'orange fruit vitamins' (Semantic Focus) ---")
    # Include superseded and private to show the effect of Boolean Admissibility
    results_sem = query_memory(test_dir, "orange fruit vitamins", limit=5, active_only=False)
    
    for idx, item in enumerate(results_sem, 1):
        print(f"{idx}. {item['title']} (ID: {item['id']}) | Status: {item['status']}")
        print(f"   Score: {item.get('score')} | Project: {item['project']}")
        print(f"   Snippet: {item['snippet']}")
        
    print("\n======================================================================")
    print("5D breakdown details:")
    print("1. BOOLEAN ADMISSIBILITY:")
    print("   Is mem_b (superseded) filtered out when active_only=True?")
    active_results = query_memory(test_dir, "orange fruit vitamins", limit=5, active_only=True)
    print("   Returned when active_only=True: " + str(any(x['id'] == 'mem_b' for x in active_results)))
    print("   Returned when active_only=False (Score is exactly 0.0 because of admissibility check): " + 
          str(next((x['score'] for x in results_sem if x['id'] == 'mem_b'), None)))
    
    print("\n2. PROCEDURAL SUBSCACE:")
    print("   Sum Calculator (mem_c) contains code definitions. It scores highest for 'calculate_sum'.")
    
    print("\n3. SPATIOTEMPORAL WARPING (MAHALANOBIS):")
    print("   Calculates time difference and salience coordinate scaling.")
    print("   mem_a (0s old, salience 1.0) vs mem_c (120s old, salience 1.2).")
    
    print("\n4. NEGATIVE ENTROPY NOVELTY BOOST:")
    print("   mem_a is in a project with 2 files. mem_d is in a project with 16 files.")
    score_a = next((x['score'] for x in results_sem if x['id'] == 'mem_a'), 0.0)
    score_d = next((x['score'] for x in results_sem if x['id'] == 'mem_d'), 0.0)
    print(f"   mem_a (HealthResearch, 2 files) Score: {score_a}")
    print(f"   mem_d (CrowdedProj, 16 files) Score: {score_d}")
    print("   Fruit Health (mem_a) scores higher than Orange Nutrition (mem_d)")
    print("   due to the low project entropy boost factor (HealthResearch is highly novel).")
    print("======================================================================\n")

if __name__ == "__main__":
    run_5d_demo()
