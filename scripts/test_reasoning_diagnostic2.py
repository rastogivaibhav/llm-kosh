"""Check why path enumeration is failing"""
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from datetime import datetime, timezone, timedelta

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from llm_kosh.core.memory import init_cartridge
from llm_kosh.engine.reasoning import ReasoningEngine
from llm_kosh.engine.reasoning.causal_dag import EdgeType
from llm_kosh.engine.reasoning.fiber_bundle import _enumerate_paths

# Setup
tmpdir = Path(TemporaryDirectory().name)
init_cartridge(tmpdir, "Test")
engine = ReasoningEngine(tmpdir)

# Ingest simple temporal sequence
sessions = [
    "Database provisioned on Day 1.",
    "Application servers configured on Day 3.",
    "Load balancer setup completed on Day 5.",
]

fact_ids = []
now = datetime.now(timezone.utc)

for i, text in enumerate(sessions):
    session_time = now + timedelta(days=i)
    fact_id = engine.ingest(
        content=text,
        documented_at=session_time,
        valid_from=session_time,
        valid_until=session_time + timedelta(days=365),
        confidence=0.95,
        causal_edges=[],
    )
    fact_ids.append(fact_id)

# Add causal edges
for i in range(len(fact_ids) - 1):
    engine.dag.add_edge(
        source_id=fact_ids[i],
        target_id=fact_ids[i + 1],
        edge_type=EdgeType.ENABLES,
        confidence=0.85,
        valid_from=now + timedelta(days=i),
        valid_until=None,
        established_by="test",
    )

print("FACT IDS:")
for fid in fact_ids:
    print(f"  {fid}")

print("\nEDGES FROM FIRST FACT:")
query_time = (now + timedelta(days=10)).timestamp()
edges = engine.dag.get_outgoing_edges(fact_ids[0], query_time)
print(f"Found {len(edges)} edges from {fact_ids[0]} at time {query_time}:")
for edge in edges:
    print(f"  -> {edge.target_id} (confidence={edge.confidence})")

print("\nPATH ENUMERATION:")
target_ids = {fid for fid in fact_ids}
paths = _enumerate_paths(engine.dag, fact_ids[0], target_ids, max_hops=3, query_time=query_time)
print(f"Found {len(paths)} target facts with paths:")
for target_id, path_list in paths.items():
    print(f"  {target_id}: {len(path_list)} paths")
    for path in path_list:
        print(f"    - edges={len(path.edges)} conf={path.confidence_product}")

