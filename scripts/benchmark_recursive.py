#!/usr/bin/env python3
"""
benchmark_recursive.py
Single-pass vs Recursive vs Dialectic-Recursive benchmark.

Usage:
    # Synthetic cartridge (backward-compat, fast):
    python scripts/benchmark_recursive.py

    # Real JUDIS cartridge (paper-quality results):
    python scripts/benchmark_recursive.py --cartridge C:\\path\\to\\judis-bench

    # All ablations + learning curve:
    python scripts/benchmark_recursive.py --cartridge ... --ablations --learning-curve
"""
from __future__ import annotations

import argparse
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).parent.parent))

from llm_kosh.core.memory import init_cartridge
from llm_kosh.engine.reasoning import ReasoningEngine
from llm_kosh.engine.reasoning.causal_dag import EdgeType

# ---------------------------------------------------------------------------
# Query sets
# ---------------------------------------------------------------------------

SYNTHETIC_QUERIES = [
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

# Designed for Supreme Court of India JUDIS corpus.
# Covers constitutional, criminal, civil and administrative law.
JUDIS_QUERIES = [
    "What is the constitutional basis for national awards like Bharat Ratna?",
    "How has the Supreme Court ruled on land reform and property rights?",
    "What are the rights of parties in electoral petition proceedings?",
    "How is legislative competency determined for items on the concurrent list?",
    "How does Article 14 equality apply in public service termination cases?",
    "How are conflicts between state and central legislation resolved?",
    "What compensation is awarded in dowry harassment and domestic violence cases?",
    "How has criminal appeal procedure evolved under the Code of Criminal Procedure?",
    "What is the court position on environmental protection under Article 21?",
    "How are government servants protected from arbitrary dismissal or demotion?",
]

# ---------------------------------------------------------------------------
# Ablation configurations
# -------------------------------------------------------------------------
# Five ablations from weakest to strongest:
#   A1  Baseline         — single-pass only (no recursion)
#   A2  1-iter           — recursive, max 1 iteration
#   A3  3-iter shallow   — recursive, 3 iters, depth=1
#   A4  3-iter full      — recursive, 3 iters, depth=3
#   A5  Dialectic        — dialectic-recursive, 5 iters, depth=3
ABLATIONS = [
    {"id": "A1", "label": "Single-pass", "mode": "single"},
    {"id": "A2", "label": "Recursive (1 iter)", "mode": "recursive",
     "max_iterations": 1, "depth": 3},
    {"id": "A3", "label": "Recursive (3 iter, depth=1)", "mode": "recursive",
     "max_iterations": 3, "depth": 1},
    {"id": "A4", "label": "Recursive (3 iter, depth=3)", "mode": "recursive",
     "max_iterations": 3, "depth": 3},
    {"id": "A5", "label": "Dialectic-Recursive (5 iter)", "mode": "dialectic",
     "max_iterations": 5, "depth": 3},
]

TEMPORAL_CTX = "2023-10-01T00:00:00+00:00"
LEARNING_CURVE_REPS = 20


# ---------------------------------------------------------------------------
# Cartridge builder (synthetic fallback)
# ---------------------------------------------------------------------------

def build_synthetic_cartridge(root: Path) -> ReasoningEngine:
    """15-fact system-incident cartridge for smoke-testing without real data."""
    init_cartridge(root, "benchmark-synthetic")
    engine = ReasoningEngine(root, enable_recursive=True)

    def dt(year: int, month: int, day: int) -> datetime:
        return datetime(year, month, day, tzinfo=timezone.utc)

    f0 = engine.ingest(content="System deployed with config v1.0. Initial monitoring green.",
                       documented_at=dt(2022, 1, 1), valid_from=dt(2022, 1, 1),
                       valid_until=dt(2022, 3, 1), confidence=0.95, causal_edges=[])
    f1 = engine.ingest(content="Memory leak in config v1.0: unbounded connection pool.",
                       documented_at=dt(2022, 1, 15), valid_from=dt(2022, 1, 15),
                       valid_until=dt(2022, 3, 1), confidence=0.88,
                       causal_edges=[{"target_id": f0, "edge_type": "CAUSES", "confidence": 0.85}])
    f2 = engine.ingest(content="Memory pressure causes slowdowns. Latency increased 3x.",
                       documented_at=dt(2022, 2, 1), valid_from=dt(2022, 2, 1),
                       valid_until=dt(2022, 3, 1), confidence=0.90,
                       causal_edges=[{"target_id": f1, "edge_type": "CAUSES", "confidence": 0.87}])
    f3 = engine.ingest(content="Slowdowns cause request timeouts. Error rate reached 15%.",
                       documented_at=dt(2022, 2, 10), valid_from=dt(2022, 2, 10),
                       valid_until=dt(2022, 3, 5), confidence=0.85,
                       causal_edges=[{"target_id": f2, "edge_type": "CAUSES", "confidence": 0.80}])
    f4 = engine.ingest(content="P0 incident: system instability. On-call paged.",
                       documented_at=dt(2022, 2, 15), valid_from=dt(2022, 2, 15),
                       valid_until=dt(2022, 3, 5), confidence=0.92,
                       causal_edges=[{"target_id": f3, "edge_type": "CAUSES", "confidence": 0.90}])
    f5 = engine.ingest(content="Hotfix v1.1: connection pool bounded, memory reclaim added.",
                       documented_at=dt(2022, 2, 25), valid_from=dt(2022, 2, 25),
                       valid_until=None, confidence=0.93,
                       causal_edges=[{"target_id": f4, "edge_type": "ENABLES", "confidence": 0.88}])
    f6 = engine.ingest(content="Hotfix v1.1 deployed 2022-03-01. Config v1.0 retired.",
                       documented_at=dt(2022, 3, 1), valid_from=dt(2022, 3, 1),
                       valid_until=None, confidence=0.97,
                       causal_edges=[{"target_id": f0, "edge_type": "SUPERSEDES", "confidence": 0.95}])
    f7 = engine.ingest(content="Post-hotfix: intermittent memory spikes. Not fully stable.",
                       documented_at=dt(2022, 3, 10), valid_from=dt(2022, 3, 10),
                       valid_until=dt(2022, 4, 1), confidence=0.70,
                       causal_edges=[{"target_id": f6, "edge_type": "CONTRADICTS", "confidence": 0.65}])
    f8 = engine.ingest(content="Patch v1.1.1 released 2022-03-20. Memory spikes eliminated. System stable.",
                       documented_at=dt(2022, 3, 20), valid_from=dt(2022, 3, 20),
                       valid_until=None, confidence=0.94,
                       causal_edges=[{"target_id": f7, "edge_type": "SUPERSEDES", "confidence": 0.90}])
    f9 = engine.ingest(content="v1.1.1 CPU regression under sustained write load. Throughput dropped 20%.",
                       documented_at=dt(2022, 9, 1), valid_from=dt(2022, 9, 1),
                       valid_until=dt(2022, 12, 1), confidence=0.80,
                       causal_edges=[{"target_id": f8, "edge_type": "CAUSES", "confidence": 0.75}])
    f10 = engine.ingest(content="v2.0 deployed Dec 2022: rewrote I/O scheduler. CPU regression resolved.",
                        documented_at=dt(2022, 12, 1), valid_from=dt(2022, 12, 1),
                        valid_until=None, confidence=0.96,
                        causal_edges=[{"target_id": f9, "edge_type": "SUPERSEDES", "confidence": 0.92}])
    f11 = engine.ingest(content="v2.0 enables horizontal scale-out with auto-scaling policies.",
                        documented_at=dt(2023, 1, 15), valid_from=dt(2023, 1, 15),
                        valid_until=None, confidence=0.88,
                        causal_edges=[{"target_id": f10, "edge_type": "ENABLES", "confidence": 0.85}])
    f12 = engine.ingest(content="System operating normally. Stability confirmed by SLO dashboards.",
                        documented_at=dt(2023, 6, 1), valid_from=dt(2023, 6, 1),
                        valid_until=None, confidence=0.82, causal_edges=[])
    f13 = engine.ingest(content="Projected: storage layer may need sharding if dataset doubles by 2024.",
                        documented_at=dt(2023, 8, 1), valid_from=dt(2023, 8, 1),
                        valid_until=None, confidence=0.60, causal_edges=[])
    f14 = engine.ingest(content="Post-incident: alerting thresholds lowered, runbooks updated.",
                        documented_at=dt(2022, 4, 1), valid_from=dt(2022, 4, 1),
                        valid_until=None, confidence=0.91,
                        causal_edges=[{"target_id": f4, "edge_type": "ENABLES", "confidence": 0.88}])
    engine.add_edge_at(source_id=f1, target_id=f4, edge_type="INFERS", confidence=0.72,
                       valid_from=dt(2022, 2, 15), origin="INFERRED", role="CAUSAL")
    engine.add_edge_at(source_id=f10, target_id=f13, edge_type="ENABLES", confidence=0.55,
                       valid_from=dt(2023, 1, 1), origin="INFERRED", role="PREDICTIVE")
    engine.dag.save_snapshot()
    return engine


# ---------------------------------------------------------------------------
# Query runners
# ---------------------------------------------------------------------------

def run_single(engine: ReasoningEngine, query: str, depth: int = 3) -> Tuple[float, int]:
    """Single-pass query. Returns (score, anchors)."""
    result = engine.query(query, temporal_context=TEMPORAL_CTX, depth=depth)
    return result.stability.score, len(result.anchors)


def run_recursive(
    engine: ReasoningEngine,
    query: str,
    max_iterations: int = 3,
    depth: int = 3,
) -> Tuple[float, int, str]:
    """Recursive query. Returns (score, iters, termination_reason)."""
    result, state = engine.query_recursive(
        query,
        temporal_context=TEMPORAL_CTX,
        max_iterations=max_iterations,
        stability_threshold=0.75,
        depth=depth,
    )
    score = result.stability.score if result is not None else 0.0
    return score, state.iteration_count, state.termination_reason or "unknown"


def run_dialectic(
    engine: ReasoningEngine,
    query: str,
    max_iterations: int = 5,
    depth: int = 3,
) -> Tuple[float, int, str]:
    """Dialectic-recursive query. Returns (score, iters, termination_reason)."""
    result, state = engine.query_dialectic_recursive(
        query,
        temporal_context=TEMPORAL_CTX,
        max_iterations=max_iterations,
        stability_threshold=0.75,
        depth=depth,
    )
    if result is None:
        score = 0.0
    elif hasattr(result, "stability"):
        score = result.stability.score
    elif hasattr(result, "initial_result"):
        score = result.initial_result.stability.score
    else:
        score = 0.0
    return score, state.iteration_count, state.termination_reason or "unknown"


def run_ablation(
    engine: ReasoningEngine,
    query: str,
    ablation: dict,
) -> Tuple[float, int, str]:
    """Dispatch to the right mode based on ablation config."""
    mode = ablation["mode"]
    if mode == "single":
        score, anchors = run_single(engine, query, depth=3)
        return score, 1, "single_pass"
    if mode == "recursive":
        return run_recursive(
            engine, query,
            max_iterations=ablation.get("max_iterations", 3),
            depth=ablation.get("depth", 3),
        )
    if mode == "dialectic":
        return run_dialectic(
            engine, query,
            max_iterations=ablation.get("max_iterations", 5),
            depth=ablation.get("depth", 3),
        )
    raise ValueError(f"Unknown ablation mode: {mode!r}")


# ---------------------------------------------------------------------------
# Table printers
# ---------------------------------------------------------------------------

def _pct(val: float) -> str:
    sign = "+" if val >= 0 else ""
    return f"{sign}{val:.2f}"


def print_main_table(rows: List[dict]) -> None:
    """
    Table 1: 10 queries × (Single-pass | Recursive | Dialectic-Recursive).
    """
    print("\n## Table 1 — Single-Pass vs Recursive vs Dialectic-Recursive\n")
    print("| Query | SP | REC | Δ REC | REC iters | DR | Δ DR | DR iters |")
    print("|---|---:|---:|---:|---:|---:|---:|---:|")

    sp_total = rec_total = dr_total = 0.0
    drec = ddr = 0.0
    rec_it = dr_it = 0.0
    n = len(rows)

    for r in rows:
        print(
            f"| {r['query']}"
            f" | {r['sp']:.2f}"
            f" | {r['rec']:.2f}"
            f" | {_pct(r['rec'] - r['sp'])}"
            f" | {r['rec_iters']}"
            f" | {r['dr']:.2f}"
            f" | {_pct(r['dr'] - r['sp'])}"
            f" | {r['dr_iters']} |"
        )
        sp_total += r["sp"]
        rec_total += r["rec"]
        dr_total += r["dr"]
        drec += r["rec"] - r["sp"]
        ddr += r["dr"] - r["sp"]
        rec_it += r["rec_iters"]
        dr_it += r["dr_iters"]

    print(
        f"| **MEAN**"
        f" | {sp_total/n:.2f}"
        f" | {rec_total/n:.2f}"
        f" | {_pct(drec/n)}"
        f" | {rec_it/n:.1f}"
        f" | {dr_total/n:.2f}"
        f" | {_pct(ddr/n)}"
        f" | {dr_it/n:.1f} |"
    )


def print_ablation_table(abl_rows: List[dict]) -> None:
    """
    Table 2: Ablation study — queries × 5 configurations.
    Rows = queries, columns = ablation configs.
    """
    print("\n## Table 2 — Ablation Study\n")
    labels = [a["label"] for a in ABLATIONS]
    ids = [a["id"] for a in ABLATIONS]
    header = "| Query | " + " | ".join(labels) + " |"
    sep = "|---|" + "---:|" * len(ABLATIONS)
    print(header)
    print(sep)

    col_totals = {a["id"]: 0.0 for a in ABLATIONS}
    n = 0
    for r in abl_rows:
        cells = [f"{r[aid]:.2f}" for aid in ids]
        print(f"| {r['query']} | " + " | ".join(cells) + " |")
        for aid in ids:
            col_totals[aid] += r[aid]
        n += 1

    means = [f"{col_totals[aid]/n:.2f}" if n else "0.00" for aid in ids]
    print("| **MEAN** | " + " | ".join(means) + " |")

    # Improvement row (relative to A1 baseline)
    if n:
        a1_mean = col_totals["A1"] / n
        imps = []
        for aid in ids:
            delta = col_totals[aid] / n - a1_mean
            imps.append(f"{_pct(delta)}")
        print("| **Δ vs A1** | " + " | ".join(imps) + " |")


def print_learning_curve(lc_rows: List[dict]) -> None:
    """Table 3 — Learning curve (20 sequential observations)."""
    print("\n## Table 3 — Learning Curve (20 × repeated query)\n")
    print("| Repetition | Stability Score | Exec Time (ms) | Accumulated Δ |")
    print("|---|---:|---:|---:|")
    baseline = lc_rows[0]["score"] if lc_rows else 0.0
    for r in lc_rows:
        delta = r["score"] - baseline
        print(
            f"| {r['i']}"
            f" | {r['score']:.2f}"
            f" | {r['ms']:.0f}"
            f" | {_pct(delta)} |"
        )


# ---------------------------------------------------------------------------
# Benchmark orchestrator
# ---------------------------------------------------------------------------

def benchmark_main_table(engine: ReasoningEngine, queries: List[str]) -> List[dict]:
    print(f"\nRunning main table ({len(queries)} queries × 3 modes)...", flush=True)
    rows = []
    for q in queries:
        short = q[:45]
        sp, _ = run_single(engine, q)
        rec, rec_iters, _ = run_recursive(engine, q)
        dr, dr_iters, _ = run_dialectic(engine, q)
        rows.append({"query": q[:55], "sp": sp, "rec": rec, "dr": dr,
                     "rec_iters": rec_iters, "dr_iters": dr_iters})
        print(f"  [{short:<45}] SP={sp:.2f} REC={rec:.2f} DR={dr:.2f}", flush=True)
    return rows


def benchmark_ablations(engine: ReasoningEngine, queries: List[str]) -> List[dict]:
    """Run all 5 ablations on each query (uses first 5 queries if list >5 for speed)."""
    abl_queries = queries[:5]
    print(f"\nRunning ablation study ({len(abl_queries)} queries × 5 configs)...", flush=True)
    abl_rows = []
    for q in abl_queries:
        row: dict = {"query": q[:50]}
        for abl in ABLATIONS:
            score, iters, reason = run_ablation(engine, q, abl)
            row[abl["id"]] = score
            print(f"  [{q[:30]:<30}] {abl['id']} = {score:.2f} ({iters} iters, {reason})",
                  flush=True)
        abl_rows.append(row)
    return abl_rows


def benchmark_learning_curve(engine: ReasoningEngine, query: str) -> List[dict]:
    print(f"\nRunning learning curve ({LEARNING_CURVE_REPS} reps)...", flush=True)
    rows = []
    for i in range(1, LEARNING_CURVE_REPS + 1):
        t0 = time.perf_counter()
        result, trace = engine.query_with_trace(query, temporal_context=TEMPORAL_CTX)
        ms = (time.perf_counter() - t0) * 1000
        score = result.stability.score
        rows.append({"i": i, "score": score, "ms": ms})
        print(f"  [{i:2d}] score={score:.2f}  {ms:.0f}ms", flush=True)
    return rows


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Recursive reasoning benchmark")
    parser.add_argument(
        "--cartridge", type=Path, default=None,
        help="Path to a pre-built HypoKosh cartridge (JUDIS or custom). "
             "Omit to use the built-in synthetic cartridge.",
    )
    parser.add_argument(
        "--ablations", action="store_true", default=False,
        help="Run the 5-config ablation study (Table 2). Adds ~5min on real cartridge.",
    )
    parser.add_argument(
        "--learning-curve", action="store_true", default=False,
        help="Run 20-repetition learning curve (Table 3).",
    )
    parser.add_argument(
        "--queries", choices=["synthetic", "judis", "both"], default=None,
        help="Which query set to use. Auto-detected from cartridge if omitted.",
    )
    args = parser.parse_args()

    # ---- Load or build cartridge ----
    if args.cartridge is not None:
        if not args.cartridge.exists():
            print(f"ERROR: cartridge path does not exist: {args.cartridge}")
            sys.exit(1)
        print(f"Loading cartridge from {args.cartridge} ...", flush=True)
        engine = ReasoningEngine(args.cartridge, enable_recursive=True)
        queries = JUDIS_QUERIES
        mode_label = "JUDIS (Supreme Court of India)"
    else:
        print("Building synthetic test cartridge...", flush=True)
        _tmpdir = tempfile.mkdtemp()
        root = Path(_tmpdir)
        engine = build_synthetic_cartridge(root)
        queries = SYNTHETIC_QUERIES
        mode_label = "Synthetic (system-incident)"

    # Override query set if explicitly specified
    if args.queries == "synthetic":
        queries = SYNTHETIC_QUERIES
    elif args.queries == "judis":
        queries = JUDIS_QUERIES

    print(f"\n{'='*60}")
    print(f" TheHypoKosh Recursive Reasoning Benchmark")
    print(f" Cartridge: {mode_label}")
    print(f" Queries:   {len(queries)}")
    print(f" Ablations: {'Yes' if args.ablations else 'No'}")
    print(f" Lrn curve: {'Yes' if args.learning_curve else 'No'}")
    print(f"{'='*60}")

    # ---- Table 1: Main 3-mode comparison ----
    main_rows = benchmark_main_table(engine, queries)
    print_main_table(main_rows)

    # ---- Table 2: Ablation study (optional) ----
    if args.ablations:
        abl_rows = benchmark_ablations(engine, queries)
        print_ablation_table(abl_rows)

    # ---- Table 3: Learning curve (optional) ----
    if args.learning_curve:
        lc_query = queries[0]
        print(f"\nLearning curve query: \"{lc_query}\"")
        lc_rows = benchmark_learning_curve(engine, lc_query)
        print_learning_curve(lc_rows)

    print("\n\nBenchmark complete.")


if __name__ == "__main__":
    main()
