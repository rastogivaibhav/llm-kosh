r"""
Integration test with real llm-kosh cartridge

Tests ReasoningEngine on actual memories from:
C:\Users\vrast\OneDrive\Apps\Documents\llm-kosh-cart
"""
import json
import time
from pathlib import Path
from datetime import datetime, timezone, timedelta

import pytest

from llm_kosh.core.memory import init_cartridge
from llm_kosh.engine.reasoning import ReasoningEngine


# Path to real cartridge
REAL_CARTRIDGE = Path(r"C:\Users\vrast\OneDrive\Apps\Documents\llm-kosh-cart")


class TestReasoningRealCartridge:
    """Integration tests using real cartridge data"""

    @pytest.fixture
    def real_docs(self):
        """Load real documents from cartridge"""
        source_dir = REAL_CARTRIDGE / "source"
        if not source_dir.exists():
            pytest.skip(f"Real cartridge not found at {REAL_CARTRIDGE}")

        docs = []
        for md_file in source_dir.glob("**/*.md"):
            try:
                with open(md_file, "r", encoding="utf-8") as f:
                    content = f.read()
                    docs.append({
                        "id": md_file.stem,
                        "path": str(md_file),
                        "content": content,
                        "name": md_file.name,
                    })
            except Exception as e:
                print(f"Warning: Could not read {md_file}: {e}")

        return docs

    def test_cartridge_exists(self):
        """Verify real cartridge is accessible"""
        assert REAL_CARTRIDGE.exists(), f"Cartridge not found at {REAL_CARTRIDGE}"
        assert (REAL_CARTRIDGE / "source").exists()
        assert (REAL_CARTRIDGE / "indexes" / "index_state.json").exists()

    def test_load_documents(self, real_docs):
        """Verify we can load documents from cartridge"""
        assert len(real_docs) > 0, "No documents found in cartridge/source"
        print(f"\nLoaded {len(real_docs)} documents from cartridge")
        for doc in real_docs[:3]:
            print(f"  - {doc['name']}: {len(doc['content'])} chars")

    def test_ingest_into_reasoning_engine(self, real_docs):
        """Ingest real cartridge documents into ReasoningEngine"""
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)

            # Initialize engine
            init_cartridge(tmpdir, "RealCartridgeTest")
            engine = ReasoningEngine(tmpdir)

            # Ingest documents
            fact_ids = []
            now = datetime.now(timezone.utc)

            for i, doc in enumerate(real_docs[:10]):  # Start with first 10
                session_time = now + timedelta(minutes=i)

                fact_id = engine.ingest(
                    content=doc["content"][:500],  # Limit to first 500 chars
                    documented_at=session_time,
                    valid_from=session_time,
                    valid_until=session_time + timedelta(days=365),
                    confidence=0.90,
                    causal_edges=[],
                )
                fact_ids.append(fact_id)

            assert len(fact_ids) == min(10, len(real_docs))
            print(f"\nIngested {len(fact_ids)} real documents")

            # Query engine
            query = "What is the main topic of this cartridge?"
            query_time = (now + timedelta(hours=1)).timestamp()

            result = engine.query(query, temporal_context=str(query_time), depth=5)

            print(f"Query: {query}")
            print(f"Anchors found: {len(result.anchors)}")
            print(f"Bundle fibers: {len(result.bundle.fibers)}")
            print(f"Stability: {result.stability.score:.3f} ({result.stability.status})")

            assert len(result.anchors) > 0, "No facts retrieved"

    def test_temporal_query_on_real_data(self, real_docs):
        """Run a temporal query on real cartridge data"""
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)

            init_cartridge(tmpdir, "RealCartridgeTest")
            engine = ReasoningEngine(tmpdir)

            # Ingest with realistic timestamps spread across time
            fact_ids = []
            base_time = datetime(2026, 1, 1, tzinfo=timezone.utc)

            for i, doc in enumerate(real_docs[:5]):
                doc_time = base_time + timedelta(days=i)

                fact_id = engine.ingest(
                    content=doc["content"][:300],
                    documented_at=doc_time,
                    valid_from=doc_time,
                    valid_until=doc_time + timedelta(days=365),
                    confidence=0.92,
                    causal_edges=[],
                )
                fact_ids.append(fact_id)

            # Temporal query
            queries = [
                "What happened first?",
                "What is the timeline?",
                "What events occurred?",
                "Summarize the sequence of events",
            ]

            query_time = (base_time + timedelta(days=10)).timestamp()

            results = []
            for query in queries:
                start = time.time()
                result = engine.query(query, temporal_context=str(query_time), depth=5)
                latency = (time.time() - start) * 1000

                results.append({
                    "query": query,
                    "anchors": len(result.anchors),
                    "fibers": len(result.bundle.fibers),
                    "stability": result.stability.score,
                    "latency_ms": latency,
                })

            print("\n" + "="*70)
            print("TEMPORAL QUERIES ON REAL CARTRIDGE")
            print("="*70)
            for r in results:
                print(f"Query: {r['query'][:50]}")
                print(f"  Anchors: {r['anchors']}, Fibers: {r['fibers']}, "
                      f"Stability: {r['stability']:.3f}, Latency: {r['latency_ms']:.1f}ms")

            # Verify some queries succeeded
            assert any(r["anchors"] > 0 for r in results), "No queries found facts"

    def test_memory_usage(self, real_docs):
        """Measure memory usage with real documents"""
        import tempfile
        import psutil
        import os

        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)

            process = psutil.Process(os.getpid())
            initial_memory = process.memory_info().rss / 1024 / 1024  # MB

            init_cartridge(tmpdir, "RealCartridgeTest")
            engine = ReasoningEngine(tmpdir)

            now = datetime.now(timezone.utc)

            # Ingest 100 documents
            for i, doc in enumerate(real_docs[:min(100, len(real_docs))]):
                doc_time = now + timedelta(minutes=i)
                engine.ingest(
                    content=doc["content"][:500],
                    documented_at=doc_time,
                    valid_from=doc_time,
                    valid_until=doc_time + timedelta(days=365),
                    confidence=0.90,
                    causal_edges=[],
                )

                if (i + 1) % 25 == 0:
                    current_memory = process.memory_info().rss / 1024 / 1024
                    delta = current_memory - initial_memory
                    print(f"\nAfter {i+1} documents: {current_memory:.1f}MB "
                          f"(+{delta:.1f}MB)")

            final_memory = process.memory_info().rss / 1024 / 1024
            memory_per_doc = (final_memory - initial_memory) / min(100, len(real_docs))

            print(f"\nMemory per document: {memory_per_doc:.2f}MB")
            assert memory_per_doc < 1.0, "Memory usage too high"

    def test_cartridge_metadata(self):
        """Read and display cartridge metadata"""
        metadata_file = REAL_CARTRIDGE / "LLM_KOSH.json"

        if metadata_file.exists():
            with open(metadata_file) as f:
                metadata = json.load(f)
            print("\n" + "="*70)
            print("CARTRIDGE METADATA")
            print("="*70)
            print(json.dumps(metadata, indent=2)[:500])


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
