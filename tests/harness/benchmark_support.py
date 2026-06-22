"""
benchmark_support.py  (v2 -- KoshVerify API)
---------------------------------------------
Variant B benchmark: support ticket cartridge.

Uses **KoshVerify.verify()** to get structured VerifyReport output instead of
calling internal engine methods directly.  This gives us richer signals:

  1. stability_score    -- Lyapunov convergence score  (same as before)
  2. tag_f1             -- correctness proxy from retrieved facts vs query tags
  3. abstain            -- did the engine abstain (insufficient evidence)?
  4. contradiction_count -- contradictions surfaced per query
  5. inferred_edges     -- inferred-not-discovered edges used in reasoning
  6. convergence_score  -- dialectic converged answer score

Single-pass  uses dialectic=False (base query)
Dialectic    uses dialectic=True  (full dialectic loop)

Usage:
    python scripts/benchmark_support.py [--cartridge PATH] [--n-queries N]
                                        [--ablations] [--seed N]
"""
from __future__ import annotations

import argparse
import json
import os
import random
import re
import sys
import time
from collections import defaultdict
from pathlib import Path
from collections import Counter
from typing import Dict, List, Optional, Set, Tuple

_SCRIPT_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _SCRIPT_DIR.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

DEFAULT_CARTRIDGE = Path(os.environ.get("LLM_KOSH_SUPPORT_BENCH", "test_root/llm-kosh-support-bench"))

# Ablation configs: (id, label, dialectic, depth)
# depth=6 on avg-degree-5 graph is O(5^6)=15k paths — too slow for batch.
# Capped at depth=4.
ABLATIONS = [
    ("A1", "SP d=2",  False, 2),
    ("A2", "SP d=4",  False, 4),
    ("A3", "DR d=2",  True,  2),
    ("A4", "DR d=4",  True,  4),
]

_TAG_RE = re.compile(r"Tags:\s*(.+)$", re.MULTILINE)


# ---------------------------------------------------------------------------
# Tag helpers
# ---------------------------------------------------------------------------

def extract_tags_from_content(content: str) -> Set[str]:
    """Parse the 'Tags: X, Y, Z' line embedded in a fact's content."""
    m = _TAG_RE.search(content)
    if not m:
        return set()
    return {t.strip() for t in m.group(1).split(",") if t.strip()}


TOP_K_FACTS = 10   # top-K by confidence used for tag F1
                   # (depth=4 on avg-degree-5 graph reaches ~all 3k nodes;
                   #  using all facts collapses recall to ~1.0 trivially)


def tag_f1(retrieved_facts: List[dict], query_tags: Set[str]) -> float:
    """
    Macro F1 using tags extracted from the TOP-K retrieved facts by confidence.

    Sorting by confidence before slicing ensures we evaluate the facts the
    engine actually committed to, not the full graph traversal.

    P = avg per-fact fraction of retrieved tags in query_tags
    R = fraction of query_tags covered by top-K retrieved facts
    """
    if not query_tags or not retrieved_facts:
        return 0.0

    # Sort by confidence descending, take top-K
    top_k = sorted(retrieved_facts, key=lambda f: f.get("confidence", 0.0), reverse=True)[:TOP_K_FACTS]

    retrieved_tag_sets = [
        extract_tags_from_content(f.get("content", ""))
        for f in top_k
    ]
    retrieved_tag_sets = [ts for ts in retrieved_tag_sets if ts]
    if not retrieved_tag_sets:
        return 0.0

    precisions = [
        len(rt & query_tags) / len(rt)
        for rt in retrieved_tag_sets
    ]
    avg_p = sum(precisions) / len(precisions)

    union_retrieved = set().union(*retrieved_tag_sets)
    recall = len(union_retrieved & query_tags) / len(query_tags)

    if avg_p + recall == 0:
        return 0.0
    return 2 * avg_p * recall / (avg_p + recall)


def primary_answer_precision(primary_answer: Optional[str], query_tags: Set[str]) -> Optional[float]:
    """Fraction of query_tags present in the primary_answer fact's tags."""
    if not primary_answer or not query_tags:
        return None
    pa_tags = extract_tags_from_content(primary_answer)
    if not pa_tags:
        return None
    return len(pa_tags & query_tags) / len(query_tags)


# ---------------------------------------------------------------------------
# Query sampling (stratified by queue/type/language)
# ---------------------------------------------------------------------------

def sample_queries(holdout: List[dict], n: int, seed: int) -> List[dict]:
    rng = random.Random(seed)
    rich = [
        q for q in holdout
        if len(q.get("tags", [])) >= 3 and len(q.get("body", "")) >= 80
    ]
    buckets: Dict[Tuple, List[dict]] = defaultdict(list)
    for q in rich:
        key = (q.get("queue", ""), q.get("type", ""), q.get("language", ""))
        buckets[key].append(q)
    selected: List[dict] = []
    bucket_keys = list(buckets.keys())
    rng.shuffle(bucket_keys)
    idx = 0
    while len(selected) < n and any(buckets[k] for k in bucket_keys):
        key = bucket_keys[idx % len(bucket_keys)]
        if buckets[key]:
            selected.append(buckets[key].pop(rng.randint(0, len(buckets[key]) - 1)))
        idx += 1
    return selected[:n]


# ---------------------------------------------------------------------------
# Single query via kv.verify() -> VerifyReport
# ---------------------------------------------------------------------------

def run_one(kv, question: str, dialectic: bool, depth: int) -> dict:
    """
    Run a single verify call.  Returns a flat metrics dict.
    """
    t0 = time.time()
    report = kv.verify(question, dialectic=dialectic, depth=depth)
    elapsed_ms = int((time.time() - t0) * 1000)

    conv_score = 0.0
    if report.convergent_summary:
        conv_score = float(report.convergent_summary.get("score", 0.0) or 0.0)

    return {
        "stability": report.stability_score,
        "abstain": report.abstain,
        "contradiction_count": len(report.contradictions),
        "inferred_edges": len(report.inferred_not_discovered),
        "conv_score": conv_score,
        "facts": report.facts,          # list[dict] with 'content' and 'confidence'
        "primary_answer": report.primary_answer,
        "elapsed_ms": elapsed_ms,
        "status": report.status,
    }


def score_query(kv, query: dict, dialectic: bool, depth: int) -> dict:
    """Run one query and compute tag F1 (top-K) + primary answer precision."""
    result = run_one(kv, query["body"], dialectic=dialectic, depth=depth)
    query_tags = set(query.get("tags", []))
    f1 = tag_f1(result["facts"], query_tags) if query_tags else None
    pa_prec = primary_answer_precision(result.get("primary_answer"), query_tags)
    result["tag_f1"] = f1
    result["pa_prec"] = pa_prec
    result["n_facts"] = len(result["facts"])
    result.pop("facts")       # don't carry raw fact content through aggregation
    result.pop("primary_answer", None)
    return result


# ---------------------------------------------------------------------------
# Main benchmark
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Support ticket benchmark (Variant B, KoshVerify API)")
    parser.add_argument("--cartridge", type=Path, default=DEFAULT_CARTRIDGE)
    parser.add_argument("--n-queries", type=int, default=20)
    parser.add_argument("--ablations", action="store_true")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    cartridge_dir = args.cartridge
    gt_path = cartridge_dir / "ground_truth.json"

    if not gt_path.exists():
        print(f"ERROR: ground_truth.json not found at {gt_path}")
        sys.exit(1)

    # Load via KoshVerify -- the correct product API
    print(f"Loading KoshVerify from {cartridge_dir} ...")
    from llm_kosh.verify import KoshVerify
    kv = KoshVerify(cartridge_dir)
    n_facts = len(kv.engine.dag.nodes)
    n_edges = sum(len(v) for v in kv.engine.dag.edges.values())
    print(f"  Loaded: {n_facts:,} facts, {n_edges:,} edges, "
          f"avg degree {2*n_edges/max(n_facts,1):.1f}")

    with open(gt_path, encoding="utf-8") as f:
        holdout = json.load(f)
    print(f"  Holdout queries available: {len(holdout):,}")

    queries = sample_queries(holdout, args.n_queries, args.seed)
    print(f"  Sampled {len(queries)} queries (stratified by queue/type/language)")

    print()
    print("=" * 68)
    print(" TheHypoKosh Support Benchmark (Variant B) -- KoshVerify API")
    print(f" Cartridge:  IT Support Tickets (EN + DE)")
    print(f" Queries:    {len(queries)}")
    print(f" Ablations:  {'Yes' if args.ablations else 'No'}")
    print("=" * 68)

    # ------------------------------------------------------------------
    # Table 1 -- Single-Pass vs Dialectic (kv.verify)
    # ------------------------------------------------------------------
    print(f"\nTable 1: running {len(queries)} queries x 2 modes...")

    rows = []
    for q in queries:
        label = q["body"][:45].replace("\n", " ")
        sp  = score_query(kv, q, dialectic=False, depth=4)
        dr  = score_query(kv, q, dialectic=True,  depth=4)
        rows.append({"query": q, "sp": sp, "dr": dr})
        f1_str = f"F1={sp['tag_f1']:.2f}" if sp["tag_f1"] is not None else "F1=n/a"
        d_conv = dr["conv_score"] - sp["stability"]
        conv_str = f"+{d_conv:.2f}" if d_conv > 0 else f"{d_conv:.2f}"
        print(f"  [{label}] stab={sp['stability']:.2f} {f1_str} "
              f"conv={dr['conv_score']:.2f} d(conv-stab)={conv_str} [{dr['status']}]")

    print()
    print("## Table 1 -- Stability vs Dialectic Convergence (KoshVerify.verify)")
    print(f"   stab    = Lyapunov score from initial query (same for SP and DR)")
    print(f"   conv    = dialectic convergence quality score (DR only)")
    print(f"   d(c-s)  = conv - stab  <-- the actual dialectic lift signal")
    print(f"   tag F1  = top-{TOP_K_FACTS} facts by confidence; pa_prec = primary answer tag precision")
    print()
    print("| Queue | Type | Lang | Stab | Tag F1 | Conv | d(conv-stab) | PA prec | Status | Contrads | n_facts |")
    print("|---|---|---|---:|---:|---:|---:|---:|---|---:|---:|")

    sp_stabs     = []
    dr_conv_scores = []
    dr_pa_precs  = []
    sp_f1s       = []
    abstain_count = 0
    total_contrads = 0
    total_inferred = 0
    status_counts: Dict[str, int] = defaultdict(int)

    f1_fmt = lambda v: f"{v:.2f}" if v is not None else "n/a"
    sign   = lambda v: (f"+{v:.3f}" if v > 0 else f"{v:.3f}") if v is not None else "n/a"

    for r in rows:
        q  = r["query"]
        sp = r["sp"]
        dr = r["dr"]

        d_conv = dr["conv_score"] - sp["stability"]

        abstain_mark = "YES" if dr["abstain"] else "no"
        if dr["abstain"]:
            abstain_count += 1

        total_contrads += dr["contradiction_count"]
        total_inferred += dr["inferred_edges"]
        status_counts[dr["status"]] += 1

        pa_str = f"{dr['pa_prec']:.2f}" if dr["pa_prec"] is not None else "n/a"
        # Abbreviate status
        short_status = {
            "convergent_stable": "converged",
            "reopened_for_non_convergent_review": "reopened",
            "abstained": "abstained",
        }.get(dr["status"], dr["status"][:12])

        print(f"| {q.get('queue','')[:18]} | {q.get('type','')} | {q.get('language','')} "
              f"| {sp['stability']:.2f} | {f1_fmt(sp['tag_f1'])} "
              f"| {dr['conv_score']:.2f} | {sign(d_conv)} "
              f"| {pa_str} | {short_status} | {dr['contradiction_count']} | {dr['n_facts']} |")

        sp_stabs.append(sp["stability"])
        dr_conv_scores.append(dr["conv_score"])
        if sp["tag_f1"] is not None:
            sp_f1s.append(sp["tag_f1"])
        if dr["pa_prec"] is not None:
            dr_pa_precs.append(dr["pa_prec"])

    mean = lambda lst: sum(lst) / len(lst) if lst else 0.0
    n = len(rows)
    avg_d_conv = mean(dr_conv_scores) - mean(sp_stabs)
    sign_v = lambda v: f"+{v:.3f}" if v > 0 else f"{v:.3f}"

    print(f"| **MEAN** | | "
          f"| **{mean(sp_stabs):.2f}** | **{mean(sp_f1s):.2f}** "
          f"| **{mean(dr_conv_scores):.2f}** | **{sign_v(avg_d_conv)}** "
          f"| **{mean(dr_pa_precs):.2f}** | - | **{total_contrads/n:.1f}** | - |")

    # Summary box
    print()
    print("### Summary")
    print(f"  Avg Lyapunov stability (all queries):  {mean(sp_stabs):.3f}")
    print(f"  Avg dialectic conv score:              {mean(dr_conv_scores):.3f}")
    print(f"  Avg d(conv - stab):                    {sign_v(avg_d_conv)}  <-- dialectic lift")
    print(f"  Avg tag F1 (top-{TOP_K_FACTS}):                  {mean(sp_f1s):.3f}")
    print(f"  Avg primary-answer precision:          {mean(dr_pa_precs):.3f}")
    print(f"  Abstain rate:                          {abstain_count}/{n} ({100*abstain_count/n:.0f}%)")
    print(f"  Avg contradictions/query:              {total_contrads/n:.2f}")
    print(f"  Avg inferred edges/query:              {total_inferred/n:.2f}")
    print(f"  Status distribution:")
    for status, cnt in sorted(status_counts.items(), key=lambda x: -x[1]):
        short = {"convergent_stable": "converged", "reopened_for_non_convergent_review": "reopened"}.get(status, status)
        print(f"    {short:<30} {cnt:>3} / {n}")

    # ------------------------------------------------------------------
    # Table 2 -- Ablation study (kv.verify with varying dialectic/depth)
    # ------------------------------------------------------------------
    if args.ablations:
        ablation_queries = queries[:min(5, len(queries))]
        print(f"\nTable 2: ablation study ({len(ablation_queries)} queries x {len(ABLATIONS)} configs)...")

        abl_rows = []
        for q in ablation_queries:
            label = q["body"][:30].replace("\n", " ")
            results = []
            for abl_id, abl_label, dialectic, depth in ABLATIONS:
                r = score_query(kv, q, dialectic=dialectic, depth=depth)
                results.append(r)
                f1_v = f"{r['tag_f1']:.2f}" if r["tag_f1"] is not None else "n/a"
                d_conv = r["conv_score"] - r["stability"]
                print(f"  [{label}] {abl_id} stab={r['stability']:.2f} conv={r['conv_score']:.2f} "
                      f"d={d_conv:+.3f} F1={f1_v} contrads={r['contradiction_count']} [{r['status'][:12]}]")
            abl_rows.append({"query": q, "results": results})

        print()
        print("## Table 2 -- Ablation Study (stab | conv | d(conv-stab) | F1 | contrads)")
        print()
        header = "| Query |" + "".join(
            f" {label} stab | {label} conv | {label} d(c-s) | {label} F1 | {label} contrads |"
            for _, label, _, _ in ABLATIONS
        )
        sep = "|---|" + "---:|---:|---:|---:|---:|" * len(ABLATIONS)
        print(header)
        print(sep)

        col_stabs  = [[] for _ in ABLATIONS]
        col_convs  = [[] for _ in ABLATIONS]
        col_f1s    = [[] for _ in ABLATIONS]

        for r in abl_rows:
            qlabel = r["query"]["body"][:35].replace("\n", " ")
            cells = f"| {qlabel} |"
            for i, res in enumerate(r["results"]):
                f1_str = f"{res['tag_f1']:.2f}" if res["tag_f1"] is not None else "n/a"
                d_conv = res["conv_score"] - res["stability"]
                d_str = f"+{d_conv:.3f}" if d_conv > 0 else f"{d_conv:.3f}"
                cells += (f" {res['stability']:.2f} | {res['conv_score']:.2f} |"
                          f" {d_str} | {f1_str} | {res['contradiction_count']} |")
                col_stabs[i].append(res["stability"])
                col_convs[i].append(res["conv_score"])
                if res["tag_f1"] is not None:
                    col_f1s[i].append(res["tag_f1"])
            print(cells)

        mean_cells = "| **MEAN** |"
        for i in range(len(ABLATIONS)):
            ms  = mean(col_stabs[i])
            mc  = mean(col_convs[i])
            mf  = mean(col_f1s[i])
            md  = mc - ms
            ds  = f"+{md:.3f}" if md > 0 else f"{md:.3f}"
            mean_cells += f" **{ms:.2f}** | **{mc:.2f}** | **{ds}** | **{mf:.2f}** | - |"
        print(mean_cells)

        delta_cells = "| **delta vs A1** |"
        base_stab = mean(col_stabs[0]) if col_stabs[0] else 0
        base_conv = mean(col_convs[0]) if col_convs[0] else 0
        base_f1   = mean(col_f1s[0])   if col_f1s[0]   else 0
        for i in range(len(ABLATIONS)):
            ds = mean(col_stabs[i]) - base_stab
            dc = mean(col_convs[i]) - base_conv
            df = mean(col_f1s[i])   - base_f1
            s = lambda v: f"+{v:.3f}" if v > 0 else f"{v:.3f}"
            delta_cells += f" {s(ds)} | {s(dc)} | - | {s(df)} | - |"
        print(delta_cells)

    print("\nBenchmark complete.")


if __name__ == "__main__":
    main()
