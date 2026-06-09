"""
save_cartridge_snapshot.py
--------------------------
Load a cartridge that only has events.jsonl (no dag.json) and materialise
dag.json from it.  Subsequent loads will skip log-replay and be fast.

Usage:
    python scripts/save_cartridge_snapshot.py [cartridge_dir]

Default cartridge_dir: C:/Users/vrast/Downloads/llm-kosh-judis-bench
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

CARTRIDGE_DIR = Path(
    sys.argv[1] if len(sys.argv) > 1 else "C:/Users/vrast/Downloads/llm-kosh-judis-bench"
)


def main() -> None:
    events = CARTRIDGE_DIR / "reasoning" / "events.jsonl"
    dag_file = CARTRIDGE_DIR / "dag.json"

    if not events.exists():
        print(f"ERROR: no events.jsonl found at {events}")
        sys.exit(1)

    if dag_file.exists():
        print(f"dag.json already exists at {dag_file} — nothing to do.")
        print("Delete it first if you want to force a rebuild.")
        sys.exit(0)

    print(f"Loading cartridge from events.jsonl ({events.stat().st_size / 1024:.0f} KB)...")
    t0 = time.time()

    # Add project root to sys.path so llm_kosh is importable
    project_root = Path(__file__).resolve().parent.parent
    sys.path.insert(0, str(project_root))

    from llm_kosh.engine.reasoning import ReasoningEngine

    engine = ReasoningEngine(CARTRIDGE_DIR)
    load_time = time.time() - t0
    print(f"Engine loaded in {load_time:.1f}s")

    node_count = len(engine.dag.nodes)
    edge_count = len(engine.dag.edges)
    print(f"  Nodes (facts): {node_count:,}")
    print(f"  Edges:         {edge_count:,}")
    if node_count:
        print(f"  Avg degree:    {edge_count / node_count:.2f}")

    print("Saving DAG snapshot...")
    t1 = time.time()
    engine.dag.save_snapshot()
    snap_time = time.time() - t1
    print(f"Snapshot saved to {dag_file} in {snap_time:.1f}s")
    print(f"Size: {dag_file.stat().st_size / 1024:.0f} KB")
    print()
    print("Done. Subsequent loads will read dag.json directly (no log replay).")


if __name__ == "__main__":
    main()
