"""Quick diagnostic of ReasoningEngine retrieval"""
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
    "SSL certificates issued on Day 6.",
    "Production traffic cutover on Day 7.",
]

print("INGESTING FACTS:")
print("-" * 60)

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
    print(f"[{i}] {fact_id}: {text[:50]}...")

# Add causal edges
print("\nADDING CAUSAL EDGES:")
print("-" * 60)
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
    print(f"{fact_ids[i]} --ENABLES--> {fact_ids[i+1]}")

# Query
query = "In what order was the infrastructure provisioned?"
print(f"\nQUERY: {query}")
print("-" * 60)

# Direct retrieval
print("\nDIRECT RETRIEVAL (CausalRetrieval.retrieve):")
query_time = (now + timedelta(days=10)).timestamp()
candidates = engine._retrieval.retrieve(query, query_time, depth=5, top_anchors=5)
print(f"Found {len(candidates)} candidates:")
for i, (fact, dist, score) in enumerate(candidates[:10]):
    print(f"  [{i}] {fact.id}: F1={score:.3f} dist={dist} | {fact.content[:50]}...")

# Engine query
print("\nENGINE QUERY (full pipeline):")
result = engine.query(query, depth=5)
print(f"Anchors: {result.anchors}")
print(f"Bundle fibers: {len(result.bundle.fibers)}")
print(f"Stability: {result.stability.status} (score={result.stability.score})")

print("\nFiber contents:")
for fid, fiber in list(result.bundle.fibers.items())[:5]:
    print(f"  {fid}: paths={len(fiber.paths)} deg={fiber.degeneracy} conf={fiber.max_confidence}")
    if fiber.fact:
        print(f"         {fiber.fact.content[:50]}...")

