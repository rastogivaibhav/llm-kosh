"""Check what's passed to build_fiber_bundle"""
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from datetime import datetime, timezone, timedelta

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from llm_kosh.core.memory import init_cartridge
from llm_kosh.engine.reasoning import ReasoningEngine
from llm_kosh.engine.reasoning.causal_dag import EdgeType

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

query = "In what order was the infrastructure provisioned?"
query_time = (now + timedelta(days=10)).timestamp()

# Step through the query process
print("STEP 1: Retrieve candidates")
candidates = engine._retrieval.retrieve(query, query_time, depth=5, top_anchors=5)
print(f"  Found {len(candidates)} candidates")
for i, (fact, dist, score) in enumerate(candidates):
    print(f"    [{i}] {fact.id}: score={score}")

print("\nSTEP 2: Select anchors")
anchor_ids = [c[0].id for c in candidates[:5]]
print(f"  Selected {len(anchor_ids)} anchors:")
for aid in anchor_ids:
    print(f"    {aid}")

print("\nSTEP 3: Check what build_fiber_bundle receives")
target_ids = {fact.id for fact, _, _ in candidates}
print(f"  Candidates target_ids: {target_ids}")
print(f"  Anchor IDs: {set(anchor_ids)}")

print("\nSTEP 4: Check path enumeration for each anchor")
from llm_kosh.engine.reasoning.fiber_bundle import _enumerate_paths
for anchor_id in anchor_ids:
    paths_to = _enumerate_paths(engine.dag, anchor_id, target_ids, 3, query_time)
    print(f"  From {anchor_id}: found paths to {len(paths_to)} targets")

