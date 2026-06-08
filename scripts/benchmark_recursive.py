#!/usr/bin/env python3
"""
Benchmark: Single-pass vs Recursive vs Dialectic-Recursive query modes.

Usage:
    python scripts/benchmark_recursive.py
"""
from __future__ import annotations

import sys
import time
import tempfile
from pathlib import Path
from datetime import datetime, timezone, timedelta

# Reconfigure stdout to UTF-8 for Windows consoles
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# Add parent to path so we can import llm_kosh
sys.path.insert(0, str(Path(__file__).parent.parent))

from llm_kosh.core.memory import init_cartridge
from llm_kosh.engine.reasoning import ReasoningEngine
from llm_kosh.engine.reasoning.causal_dag import EdgeType


# ---------------------------------------------------------------------------
# Test queries
# ---------------------------------------------------------------------------

TEST_QUERIES = [
    "What caused the system slowdowns?",
    "Is the system currently stable?",
    "What was the impact of the memory leak?",
    "What configuration is active?",
    "What was deployed in early 2022?",
    "What is the relationship between config v1.0 and v1.1?",
    "Did the hotfix resolve the issue?",
    "What caused the high error rate?",
    "What changed after the incident?",
    "What is the current system state?",
]


# ---------------------------------------------------------------------------
# Build test cartridge
# ---------------------------------------------------------------------------

def build_test_cartridge(root: Path) -> ReasoningEngine:
    """Build an in-memory test cartridge with 15+ representative facts."""
    init_cartridge(root, "benchmark")
    engine = ReasoningEngine(root, enable_recursive=True)

    def dt(year: int, month: int, day: int) -> datetime:
        return datetime(year, month, day, tzinfo=timezone.utc)

    # ---- Ingest facts (returns fact_id) ----
    # Fact 0: Initial system deploy
    f0 = engine.ingest(
        content="System deployed with config v1.0 on production cluster. Initial monitoring shows green.",
        documented_at=dt(2022, 1, 1),
        valid_from=dt(2022, 1, 1),
        valid_until=dt(2022, 3, 1),   # superseded by v1.1
        confidence=0.95,
        causal_edges=[],
    )

    # Fact 1: Memory leak introduced
    f1 = engine.ingest(
        content="Memory leak introduced in config v1.0 due to unbounded connection pool. Detected by profiler.",
        documented_at=dt(2022, 1, 15),
        valid_from=dt(2022, 1, 15),
        valid_until=dt(2022, 3, 1),
        confidence=0.88,
        causal_edges=[{"target_id": f0, "edge_type": "CAUSES", "confidence": 0.85}],
    )

    # Fact 2: Memory pressure increases
    f2 = engine.ingest(
        content="Memory pressure causes system slowdowns. Response latency increased 3x under load.",
        documented_at=dt(2022, 2, 1),
        valid_from=dt(2022, 2, 1),
        valid_until=dt(2022, 3, 1),
        confidence=0.90,
        causal_edges=[{"target_id": f1, "edge_type": "CAUSES", "confidence": 0.87}],
    )

    # Fact 3: Slowdowns cause high error rate (chain: f0 -> f1 -> f2 -> f3)
    f3 = engine.ingest(
        content="System slowdowns cause request timeouts and elevated error rate. Error rate reached 15%.",
        documented_at=dt(2022, 2, 10),
        valid_from=dt(2022, 2, 10),
        valid_until=dt(2022, 3, 5),
        confidence=0.85,
        causal_edges=[{"target_id": f2, "edge_type": "CAUSES", "confidence": 0.80}],
    )

    # Fact 4: Incident declared
    f4 = engine.ingest(
        content="P0 incident declared: system instability. On-call team paged. Rollback considered.",
        documented_at=dt(2022, 2, 15),
        valid_from=dt(2022, 2, 15),
        valid_until=dt(2022, 3, 5),
        confidence=0.92,
        causal_edges=[{"target_id": f3, "edge_type": "CAUSES", "confidence": 0.90}],
    )

    # Fact 5: Hotfix developed
    f5 = engine.ingest(
        content="Engineering team developed hotfix v1.1: connection pool bounded to 100, memory reclaim added.",
        documented_at=dt(2022, 2, 25),
        valid_from=dt(2022, 2, 25),
        valid_until=None,
        confidence=0.93,
        causal_edges=[{"target_id": f4, "edge_type": "ENABLES", "confidence": 0.88}],
    )

    # Fact 6: Hotfix deployed - supersedes v1.0
    f6 = engine.ingest(
        content="Hotfix v1.1 deployed to production on 2022-03-01. Config v1.0 retired.",
        documented_at=dt(2022, 3, 1),
        valid_from=dt(2022, 3, 1),
        valid_until=None,
        confidence=0.97,
        causal_edges=[{"target_id": f0, "edge_type": "SUPERSEDES", "confidence": 0.95}],
    )

    # Fact 7: Contradicting fact - system still unstable (contradiction)
    f7 = engine.ingest(
        content="Post-hotfix monitoring shows intermittent memory spikes. System not fully stable.",
        documented_at=dt(2022, 3, 10),
        valid_from=dt(2022, 3, 10),
        valid_until=dt(2022, 4, 1),
        confidence=0.70,
        causal_edges=[{"target_id": f6, "edge_type": "CONTRADICTS", "confidence": 0.65}],
    )

    # Fact 8: Contradicting fact resolved
    f8 = engine.ingest(
        content="Second patch v1.1.1 released on 2022-03-20. Memory spikes eliminated. System stable.",
        documented_at=dt(2022, 3, 20),
        valid_from=dt(2022, 3, 20),
        valid_until=None,
        confidence=0.94,
        causal_edges=[{"target_id": f7, "edge_type": "SUPERSEDES", "confidence": 0.90}],
    )

    # Fact 9: Performance regression in late 2022
    f9 = engine.ingest(
        content="Config v1.1.1 shows CPU regression under sustained write load. Throughput dropped 20%.",
        documented_at=dt(2022, 9, 1),
        valid_from=dt(2022, 9, 1),
        valid_until=dt(2022, 12, 1),
        confidence=0.80,
        causal_edges=[{"target_id": f8, "edge_type": "CAUSES", "confidence": 0.75}],
    )

    # Fact 10: v2.0 upgrade
    f10 = engine.ingest(
        content="Major upgrade to v2.0 deployed in December 2022. Rewrote I/O scheduler. Addresses CPU regression.",
        documented_at=dt(2022, 12, 1),
        valid_from=dt(2022, 12, 1),
        valid_until=None,
        confidence=0.96,
        causal_edges=[{"target_id": f9, "edge_type": "SUPERSEDES", "confidence": 0.92}],
    )

    # Fact 11: v2.0 enables scale-out
    f11 = engine.ingest(
        content="v2.0 enables horizontal scale-out. Auto-scaling policies configured for high-traffic events.",
        documented_at=dt(2023, 1, 15),
        valid_from=dt(2023, 1, 15),
        valid_until=None,
        confidence=0.88,
        causal_edges=[{"target_id": f10, "edge_type": "ENABLES", "confidence": 0.85}],
    )

    # Fact 12: Current system state - INFERRED origin
    f12 = engine.ingest(
        content="System is operating within normal parameters. Stability confirmed by SLO dashboards.",
        documented_at=dt(2023, 6, 1),
        valid_from=dt(2023, 6, 1),
        valid_until=None,
        confidence=0.82,
        causal_edges=[],
    )

    # Fact 13: INFERRED - predicted future issue
    f13 = engine.ingest(
        content="Projected: v2.0 storage layer may require sharding if dataset doubles by 2024.",
        documented_at=dt(2023, 8, 1),
        valid_from=dt(2023, 8, 1),
        valid_until=None,
        confidence=0.60,
        causal_edges=[],
    )

    # Fact 14: Monitoring improvement post-incident
    f14 = engine.ingest(
        content="Post-incident review: alerting thresholds lowered, runbooks updated, on-call rotation expanded.",
        documented_at=dt(2022, 4, 1),
        valid_from=dt(2022, 4, 1),
        valid_until=None,
        confidence=0.91,
        causal_edges=[{"target_id": f4, "edge_type": "ENABLES", "confidence": 0.88}],
    )

    # ---- Add INFERRED-origin edges explicitly ----
    # Inferred: memory leak indirectly caused the incident (via pressure -> slowdowns)
    engine.add_edge_at(
        source_id=f1,
        target_id=f4,
        edge_type="INFERS",
        confidence=0.72,
        valid_from=dt(2022, 2, 15),
        origin="INFERRED",
        role="CAUSAL",
    )

    # Inferred: v2.0 probably resolves any future memory issues (hypothetical)
    engine.add_edge_at(
        source_id=f10,
        target_id=f13,
        edge_type="ENABLES",
        confidence=0.55,
        valid_from=dt(2023, 1, 1),
        origin="INFERRED",
        role="PREDICTIVE",
    )

    # Save snapshot
    engine.dag.save_snapshot()

    return engine


# ---------------------------------------------------------------------------
# Benchmark runner
# ---------------------------------------------------------------------------

TEMPORAL_CTX = "2023-10-01T00:00:00+00:00"


def run_single_pass(engine: ReasoningEngine, query: str) -> float:
    """Return stability score from single-pass query."""
    result = engine.query(query, temporal_context=TEMPORAL_CTX, depth=3)
    return result.stability.score


def run_recursive(engine: ReasoningEngine, query: str):
    """Return (stability_score, iteration_count, termination_reason)."""
    result, loop_state = engine.query_recursive(
        query,
        temporal_context=TEMPORAL_CTX,
        max_iterations=3,
        stability_threshold=0.75,
    )
    score = result.stability.score if result is not None else 0.0
    iters = loop_state.iteration_count
    reason = loop_state.termination_reason or "unknown"
    return score, iters, reason


def run_dialectic_recursive(engine: ReasoningEngine, query: str):
    """Return (stability_score, iteration_count, termination_reason)."""
    result, loop_state = engine.query_dialectic_recursive(
        query,
        temporal_context=TEMPORAL_CTX,
        max_iterations=3,
        stability_threshold=0.75,
    )
    # DialecticResult has .initial_result.stability.score
    if result is not None:
        if hasattr(result, "stability"):
            score = result.stability.score
        elif hasattr(result, "initial_result"):
            score = result.initial_result.stability.score
        else:
            score = 0.0
    else:
        score = 0.0
    iters = loop_state.iteration_count
    reason = loop_state.termination_reason or "unknown"
    return score, iters, reason


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print("Building test cartridge...", flush=True)
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        engine = build_test_cartridge(root)
        print(f"Cartridge ready at {root} (temporary)\n")

        # ---- Main benchmark ----
        rows = []
        for q in TEST_QUERIES:
            sp_score = run_single_pass(engine, q)
            rec_score, rec_iters, rec_reason = run_recursive(engine, q)
            dr_score, dr_iters, dr_reason = run_dialectic_recursive(engine, q)

            delta_rec = rec_score - sp_score
            delta_dr = dr_score - sp_score

            rows.append({
                "query": q,
                "sp": sp_score,
                "rec": rec_score,
                "delta_rec": delta_rec,
                "rec_iters": rec_iters,
                "dr": dr_score,
                "delta_dr": delta_dr,
                "dr_iters": dr_iters,
            })
            print(f"  [{q[:35]:<35}] SP={sp_score:.2f}  REC={rec_score:.2f}  DR={dr_score:.2f}",
                  flush=True)

        # ---- Print markdown table ----
        print()
        print("## Benchmark Results")
        print()
        header = (
            "| Query"
            " | Single-Pass Score"
            " | Recursive Score"
            " | Δ Recursive"
            " | Recursive Iters"
            " | Dialectic-Rec Score"
            " | Δ Dialectic-Rec |"
        )
        sep = "|---|---:|---:|---:|---:|---:|---:|"
        print(header)
        print(sep)

        sp_total = rec_total = dr_total = 0.0
        delta_rec_total = delta_dr_total = 0.0
        rec_iter_total = dr_iter_total = 0.0
        n = len(rows)

        for r in rows:
            sp_total += r["sp"]
            rec_total += r["rec"]
            dr_total += r["dr"]
            delta_rec_total += r["delta_rec"]
            delta_dr_total += r["delta_dr"]
            rec_iter_total += r["rec_iters"]
            dr_iter_total += r["dr_iters"]

            sign_rec = "+" if r["delta_rec"] >= 0 else ""
            sign_dr = "+" if r["delta_dr"] >= 0 else ""
            print(
                f"| {r['query']}"
                f" | {r['sp']:.2f}"
                f" | {r['rec']:.2f}"
                f" | {sign_rec}{r['delta_rec']:.2f}"
                f" | {r['rec_iters']}"
                f" | {r['dr']:.2f}"
                f" | {sign_dr}{r['delta_dr']:.2f} |"
            )

        # Mean row
        sp_mean = sp_total / n
        rec_mean = rec_total / n
        dr_mean = dr_total / n
        drec_mean = delta_rec_total / n
        ddr_mean = delta_dr_total / n
        rec_iter_mean = rec_iter_total / n
        sign_drec = "+" if drec_mean >= 0 else ""
        sign_ddr = "+" if ddr_mean >= 0 else ""
        print(
            f"| **MEAN**"
            f" | {sp_mean:.2f}"
            f" | {rec_mean:.2f}"
            f" | {sign_drec}{drec_mean:.2f}"
            f" | {rec_iter_mean:.1f}"
            f" | {dr_mean:.2f}"
            f" | {sign_ddr}{ddr_mean:.2f} |"
        )

        # ---- Learning Curve ----
        print()
        print("## Learning Curve (query_with_trace, 20 sequential observations)")
        print()
        print("| Query # | Stability Score | Execution Time (ms) |")
        print("|---|---:|---:|")

        lc_query = TEST_QUERIES[0]
        for i in range(1, 21):
            t0 = time.perf_counter()
            result, trace = engine.query_with_trace(lc_query, temporal_context=TEMPORAL_CTX)
            elapsed_ms = (time.perf_counter() - t0) * 1000
            score = result.stability.score
            print(f"| {i} | {score:.2f} | {elapsed_ms:.0f} |")

        print()
        print("Benchmark complete.")


if __name__ == "__main__":
    main()
