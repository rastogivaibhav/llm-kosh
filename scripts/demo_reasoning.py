#!/usr/bin/env python3
"""
Demo: Keyword Search vs. Temporal Causal Reasoning
Shows how llm-kosh's Temporal Causal Reasoning Engine
traces causal chains instead of returning disconnected facts.
"""
import sys
import os
from pathlib import Path
from datetime import datetime, timezone, timedelta
from tempfile import TemporaryDirectory

# Allow running from repo root without install
sys.path.insert(0, str(Path(__file__).parent.parent))

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')


def main():
    with TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)

        print("=" * 60)
        print("  llm-kosh: Temporal Causal Reasoning Demo")
        print("=" * 60)
        print()

        # 1. Init cartridge
        from llm_kosh.core.memory import init_cartridge
        init_cartridge(root, "demo")

        # 2. Ingest facts into the reasoning engine WITH causal edges
        from llm_kosh.engine.reasoning import ReasoningEngine
        from llm_kosh.engine.reasoning.causal_dag import EdgeType

        engine = ReasoningEngine(root)
        now = datetime.now(timezone.utc)

        fact_ids = []
        facts_data = [
            ("Decision: Migrate authentication from session cookies to OAuth2. Approved by steering committee.", 90, 0.95),
            ("OAuth2 provider integration completed. All API endpoints updated. Staging tests passing.", 69, 0.90),
            ("Auth service deployed to production. Smoke tests passed. No regressions.", 53, 0.88),
            ("Bug report: Token refresh fails after 1 hour. Affects 12% of active sessions. Root cause: missing sliding window.", 17, 0.85),
            ("Hotfix merged: sliding window refresh implemented. Auth system fully stable. Incident closed.", 16, 0.92),
        ]

        for content, days_ago, confidence in facts_data:
            ts = now - timedelta(days=days_ago)
            fid = engine.ingest(content, ts, ts, None, confidence, [])
            fact_ids.append(fid)

        # Add causal edges
        edges = [
            (0, 1, EdgeType.ENABLES, 0.90),
            (1, 2, EdgeType.ENABLES, 0.85),
            (2, 3, EdgeType.CAUSES, 0.88),
            (3, 4, EdgeType.SUPERSEDES, 0.92),
        ]
        for src_i, tgt_i, etype, conf in edges:
            engine.dag.add_edge(
                source_id=fact_ids[src_i],
                target_id=fact_ids[tgt_i],
                edge_type=etype,
                confidence=conf,
                valid_from=now - timedelta(days=90),
                valid_until=None,
                established_by="demo",
            )
        engine.dag.save_snapshot()

        # Refresh retrieval index after adding edges
        from llm_kosh.engine.reasoning.causal_retrieval import CausalRetrieval
        engine._retrieval = CausalRetrieval(engine.dag)

        # Also add to regular memory for keyword search
        from llm_kosh.core.memory import add_memory
        for content, days_ago, _ in facts_data:
            add_memory(root, "note", content[:60], content, "auth-demo", "private")

        query = "What happened to the auth system?"

        # --- SECTION 1: Keyword Search ---
        print("KEYWORD SEARCH (traditional)")
        print("-" * 60)
        print(f'Query: "{query}"')
        print()
        from llm_kosh.engine.search import query_memory
        kw_results = query_memory(root, "auth system", limit=5)
        if kw_results:
            for i, r in enumerate(kw_results, 1):
                snippet = (r.get('snippet') or r.get('title') or '')[:80]
                print(f"  {i}. {snippet}")
        else:
            print("  (no results)")
        print()
        print("  ^ Five facts. No order. No story. You assemble it manually.")
        print()

        # --- SECTION 2: Causal Reasoning ---
        print("TEMPORAL CAUSAL REASONING (llm-kosh)")
        print("-" * 60)
        print(f'Query: "{query}"')
        print()
        from llm_kosh.engine.reasoning.formatter import format_narrative
        result = engine.query("auth system", temporal_context=str(now.timestamp()), depth=5)
        narrative = format_narrative(result, "auth system")
        print(narrative)
        print()
        print("  ^ One coherent narrative. Cause and effect. Time-ordered.")
        print()

        # --- Stats ---
        print("=" * 60)
        print(f"  Stability score : {result.stability.score:.2f} ({result.stability.status})")
        print(f"  Facts in chain  : {len(result.bundle.fibers)}")
        print(f"  Escape triggered: {result.escape_triggered}")
        print("=" * 60)


if __name__ == "__main__":
    main()
