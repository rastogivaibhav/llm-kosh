"""
ingest_support_cartridge.py  (v2 — KoshVerify API)
----------------------------------------------------
Variant B ingestion: IT-support / helpdesk tickets -> TheHypoKosh cartridge.

Uses the **KoshVerify product API** (`add_fact`, `add_edge`, `verify`) instead of
calling internal ReasoningEngine methods directly.  This ensures proper
EdgeProvenance tracking, structured VerifyReport output, and alignment with the
application's canonical data model.

Source:  aa_dataset-tickets-multi-lang-5-2-50-version.csv  (28k rows, EN+DE)
Holdout: 300 tickets drawn from the SAME source file (shared tag vocabulary)
         saved as ground_truth.json for the benchmark.

Edge strategy:
  STRUCTURALLY_SIMILAR — any two tickets sharing >=2 tags
  INFERS               — same queue, Incident -> Request, >=1 shared tag
  CAUSES               — same queue, Problem  -> Incident, >=1 shared tag
  CONTRADICTS          — same queue, >=3 shared tags, different type

Timestamps are synthesised: tickets are sorted by queue -> type -> priority
and spread evenly across 2022-01-01 -> 2024-12-31.

Usage:
    python scripts/ingest_support_cartridge.py [--force]

    --force   Skip overwrite confirmation and always rebuild from scratch.

Outputs:
    TARGET_DIR/reasoning/snapshot.json   -- fast-load DAG snapshot
    TARGET_DIR/reasoning/events.jsonl    -- append-only event log
    TARGET_DIR/ground_truth.json         -- 300 holdout queries (same vocab)
"""
from __future__ import annotations

import argparse
import csv
import json
import logging
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, FrozenSet, List, Optional, Set, Tuple

# ---------------------------------------------------------------------------
# sys.path fix so script runs without `pip install -e .`
# ---------------------------------------------------------------------------
_SCRIPT_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _SCRIPT_DIR.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

# ---------------------------------------------------------------------------
# Paths & tuning knobs
# ---------------------------------------------------------------------------
SOURCE_CSV   = Path(r"C:\Users\vrast\AppData\Local\Temp\aa_dataset-tickets-multi-lang-5-2-50-version.csv")
TARGET_DIR   = Path(r"C:\Users\vrast\Downloads\llm-kosh-support-bench")
TARGET_COUNT = 3_000          # facts to ingest
HOLDOUT_COUNT = 300           # same-vocab holdout (NOT ingested)

MAX_SIMILAR_EDGES      = 6_000   # STRUCTURALLY_SIMILAR cap
MAX_INFERS_EDGES       = 800     # INFERS cap
MAX_CAUSES_EDGES       = 500     # CAUSES cap
MAX_CONTRADICTS_EDGES  = 400     # CONTRADICTS cap
MAX_PAIRS_PER_TICKET   = 12      # max SIMILAR edges per ticket

# Synthetic timeline
_EPOCH_START = datetime(2022, 1, 1, tzinfo=timezone.utc)
_EPOCH_END   = datetime(2024, 12, 31, tzinfo=timezone.utc)

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s: %(message)s",
    stream=sys.stdout,
)
log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------
@dataclass
class SupportTicket:
    row_index: int
    subject: str
    body: str
    answer: str
    ticket_type: str                       # Incident / Request / Problem / Change
    queue: str
    priority: str                          # high / medium / low
    language: str                          # en / de
    tags: FrozenSet[str] = field(default_factory=frozenset)
    timestamp: Optional[datetime] = None   # synthesised
    fact_id: Optional[str] = None          # set after kv.add_fact()

    @property
    def content(self) -> str:
        """Text stored as the fact content."""
        parts = [f"[{self.ticket_type.upper()} | {self.queue} | {self.priority.upper()}]"]
        parts.append(self.subject)
        parts.append("")
        parts.append(self.body)
        if self.answer:
            parts.append(f"\nResolution: {self.answer}")
        tag_str = ", ".join(sorted(self.tags))
        if tag_str:
            parts.append(f"\nTags: {tag_str}")
        return "\n".join(parts)

    @property
    def priority_rank(self) -> int:
        return {"high": 0, "medium": 1, "low": 2}.get(self.priority.lower(), 1)

    @property
    def type_rank(self) -> int:
        # Problem (root cause) -> Incident -> Request -> Change (remediation)
        return {"problem": 0, "incident": 1, "request": 2, "change": 3}.get(
            self.ticket_type.lower(), 2
        )


# ---------------------------------------------------------------------------
# Step 1: Load CSV
# ---------------------------------------------------------------------------
_TAG_COLS = [f"tag_{i}" for i in range(1, 10)]


def _parse_tags(row: dict) -> FrozenSet[str]:
    return frozenset(
        row[c].strip()
        for c in _TAG_COLS
        if c in row and row[c].strip()
    )


def load_source(path: Path) -> List[SupportTicket]:
    log.info("Reading %s", path)
    tickets: List[SupportTicket] = []
    with open(path, encoding="utf-8") as f:
        for idx, row in enumerate(csv.DictReader(f)):
            body    = row.get("body", "").strip()
            subject = row.get("subject", "").strip()
            answer  = row.get("answer", "").strip()
            queue   = row.get("queue", "").strip()
            ttype   = row.get("type", "Request").strip()
            priority = row.get("priority", "medium").strip()
            lang    = row.get("language", "en").strip()
            if not body or not subject:
                continue
            tickets.append(SupportTicket(
                row_index=idx,
                subject=subject,
                body=body,
                answer=answer,
                ticket_type=ttype,
                queue=queue,
                priority=priority,
                language=lang,
                tags=_parse_tags(row),
            ))
    log.info("Loaded %d tickets from %s", len(tickets), path.name)
    return tickets


# ---------------------------------------------------------------------------
# Step 2: Select & assign timestamps
# ---------------------------------------------------------------------------
def select_tickets(
    all_tickets: List[SupportTicket],
) -> Tuple[List[SupportTicket], List[SupportTicket]]:
    """
    Stratified selection: balance queue, type, language.
    Returns (ingested_3000, holdout_300) — both from the SAME source file so
    they share the same tag vocabulary.
    """
    buckets: Dict[Tuple, List[SupportTicket]] = defaultdict(list)
    for t in all_tickets:
        key = (t.queue, t.ticket_type, t.language)
        buckets[key].append(t)

    for key in buckets:
        buckets[key].sort(key=lambda t: len(t.tags), reverse=True)

    total_needed = TARGET_COUNT + HOLDOUT_COUNT
    selected: List[SupportTicket] = []
    seen_ids: Set[int] = set()
    bucket_keys = list(buckets.keys())
    idx = 0
    while len(selected) < total_needed and any(buckets[k] for k in bucket_keys):
        key = bucket_keys[idx % len(bucket_keys)]
        if buckets[key]:
            t = buckets[key].pop(0)
            if t.row_index not in seen_ids:
                selected.append(t)
                seen_ids.add(t.row_index)
        idx += 1

    ingested = selected[:TARGET_COUNT]
    holdout  = selected[TARGET_COUNT:]

    log.info("Selected %d to ingest + %d holdout (same tag vocab)", len(ingested), len(holdout))
    log.info("  Types:     %s", dict(Counter(t.ticket_type for t in ingested)))
    log.info("  Languages: %s", dict(Counter(t.language for t in ingested)))
    log.info("  Top queues: %s", dict(Counter(t.queue for t in ingested).most_common(5)))
    return ingested, holdout


def assign_timestamps(tickets: List[SupportTicket]) -> None:
    """Assign synthetic timestamps spread evenly across 2022-2024."""
    ordered = sorted(
        tickets,
        key=lambda t: (t.queue, t.type_rank, t.priority_rank, t.row_index),
    )
    span = (_EPOCH_END - _EPOCH_START).total_seconds()
    step = span / max(len(ordered) - 1, 1)
    for i, t in enumerate(ordered):
        t.timestamp = _EPOCH_START + timedelta(seconds=i * step)


# ---------------------------------------------------------------------------
# Step 3: Ingest facts via KoshVerify.add_fact()
# ---------------------------------------------------------------------------
def ingest_facts(kv, tickets: List[SupportTicket]) -> None:
    """
    Add each ticket as a TemporalFact via KoshVerify.add_fact().
    Source tag encodes ticket type for downstream filtering.
    """
    for i, t in enumerate(tickets, 1):
        fid = kv.add_fact(
            content=t.content,
            valid_from=t.timestamp,
            documented_at=t.timestamp,
            confidence=0.85,
            source=f"ticket_{t.ticket_type.lower()}",
        )
        t.fact_id = fid
        if i % 250 == 0:
            log.info("Ingested %d/%d facts...", i, len(tickets))
    log.info("Ingested %d facts total.", len(tickets))


# ---------------------------------------------------------------------------
# Step 4a: STRUCTURALLY_SIMILAR edges via KoshVerify.add_edge()
# ---------------------------------------------------------------------------
def build_similar_edges(kv, tickets: List[SupportTicket]) -> int:
    """
    For each ticket, find up to MAX_PAIRS_PER_TICKET partners sharing >=2 tags.
    EdgeType=STRUCTURALLY_SIMILAR, origin=INFERRED, role=ANALOGICAL.
    """
    tag_index: Dict[str, List[int]] = defaultdict(list)
    for i, t in enumerate(tickets):
        for tag in t.tags:
            tag_index[tag].append(i)

    seen_pairs: Set[Tuple[int, int]] = set()
    count = 0

    for i, t_a in enumerate(tickets):
        if count >= MAX_SIMILAR_EDGES:
            break
        if not t_a.fact_id:
            continue

        candidate_counts: Counter = Counter()
        for tag in t_a.tags:
            for j in tag_index.get(tag, []):
                if j != i:
                    candidate_counts[j] += 1

        partners = [
            (j, cnt) for j, cnt in candidate_counts.most_common(MAX_PAIRS_PER_TICKET * 2)
            if cnt >= 2
        ][:MAX_PAIRS_PER_TICKET]

        for j, shared_count in partners:
            if count >= MAX_SIMILAR_EDGES:
                break
            t_b = tickets[j]
            if not t_b.fact_id:
                continue
            pair = (min(i, j), max(i, j))
            if pair in seen_pairs:
                continue
            seen_pairs.add(pair)

            confidence = min(0.5 + shared_count * 0.08, 0.9)
            try:
                kv.add_edge(
                    source_id=t_a.fact_id,
                    target_id=t_b.fact_id,
                    edge_type="STRUCTURALLY_SIMILAR",
                    valid_from=min(t_a.timestamp, t_b.timestamp),
                    confidence=confidence,
                    origin="INFERRED",
                    role="ANALOGICAL",
                )
                count += 1
            except Exception as exc:
                log.debug("SIMILAR edge failed: %s", exc)

    log.info("Built %d STRUCTURALLY_SIMILAR edges (tag overlap >=2)", count)
    return count


# ---------------------------------------------------------------------------
# Step 4b: INFERS edges — same queue, Incident -> Request
# ---------------------------------------------------------------------------
def build_infers_edges(kv, tickets: List[SupportTicket]) -> int:
    """
    Incident ticket 'infers' resolution pattern for same-queue Request tickets.
    EdgeType=INFERS, origin=INFERRED, role=PREDICTIVE.
    """
    incidents = [t for t in tickets if t.ticket_type.lower() == "incident" and t.fact_id]
    requests  = [t for t in tickets if t.ticket_type.lower() == "request"  and t.fact_id]

    req_by_queue: Dict[str, List[SupportTicket]] = defaultdict(list)
    for t in requests:
        req_by_queue[t.queue].append(t)

    count = 0
    seen_pairs: Set[Tuple[str, str]] = set()

    for inc in incidents:
        if count >= MAX_INFERS_EDGES:
            break
        candidates = req_by_queue.get(inc.queue, [])
        matches = [
            r for r in candidates
            if inc.tags & r.tags
            and r.timestamp >= inc.timestamp
        ]
        matches.sort(key=lambda r: len(inc.tags & r.tags), reverse=True)

        for req in matches[:5]:
            if count >= MAX_INFERS_EDGES:
                break
            pair = (inc.fact_id, req.fact_id)
            if pair in seen_pairs:
                continue
            seen_pairs.add(pair)
            shared = len(inc.tags & req.tags)
            try:
                kv.add_edge(
                    source_id=inc.fact_id,
                    target_id=req.fact_id,
                    edge_type="INFERS",
                    valid_from=inc.timestamp,
                    confidence=min(0.55 + shared * 0.07, 0.85),
                    origin="INFERRED",
                    role="PREDICTIVE",
                )
                count += 1
            except Exception as exc:
                log.debug("INFERS edge failed: %s", exc)

    log.info("Built %d INFERS edges (Incident -> Request, same queue)", count)
    return count


# ---------------------------------------------------------------------------
# Step 4c: CAUSES edges — same queue, Problem -> Incident
# ---------------------------------------------------------------------------
def build_causes_edges(kv, tickets: List[SupportTicket]) -> int:
    """
    Problem ticket 'causes' downstream Incident tickets in the same queue.
    EdgeType=CAUSES, origin=OBSERVED, role=MECHANISTIC.
    """
    problems  = [t for t in tickets if t.ticket_type.lower() == "problem"  and t.fact_id]
    incidents = [t for t in tickets if t.ticket_type.lower() == "incident" and t.fact_id]

    inc_by_queue: Dict[str, List[SupportTicket]] = defaultdict(list)
    for t in incidents:
        inc_by_queue[t.queue].append(t)

    count = 0
    seen_pairs: Set[Tuple[str, str]] = set()

    for prob in problems:
        if count >= MAX_CAUSES_EDGES:
            break
        candidates = inc_by_queue.get(prob.queue, [])
        matches = [
            inc for inc in candidates
            if prob.tags & inc.tags
            and inc.timestamp >= prob.timestamp
        ]
        matches.sort(key=lambda inc: len(prob.tags & inc.tags), reverse=True)

        for inc in matches[:4]:
            if count >= MAX_CAUSES_EDGES:
                break
            pair = (prob.fact_id, inc.fact_id)
            if pair in seen_pairs:
                continue
            seen_pairs.add(pair)
            shared = len(prob.tags & inc.tags)
            try:
                kv.add_edge(
                    source_id=prob.fact_id,
                    target_id=inc.fact_id,
                    edge_type="CAUSES",
                    valid_from=prob.timestamp,
                    confidence=min(0.6 + shared * 0.06, 0.88),
                    origin="OBSERVED",
                    role="MECHANISTIC",
                )
                count += 1
            except Exception as exc:
                log.debug("CAUSES edge failed: %s", exc)

    log.info("Built %d CAUSES edges (Problem -> Incident, same queue)", count)
    return count


# ---------------------------------------------------------------------------
# Step 4d: CONTRADICTS edges — same queue, >=3 shared tags, different type
# ---------------------------------------------------------------------------
def build_contradicts_edges(kv, tickets: List[SupportTicket]) -> int:
    """
    Two tickets in the same queue with >=3 shared tags but different types
    contradict each other's framing (Incident vs Problem = reactive vs systemic).
    EdgeType=CONTRADICTS, origin=OBSERVED, role=MECHANISTIC.
    """
    by_queue: Dict[str, List[SupportTicket]] = defaultdict(list)
    for t in tickets:
        if t.fact_id:
            by_queue[t.queue].append(t)

    count = 0
    seen_pairs: Set[Tuple[str, str]] = set()

    for queue, group in by_queue.items():
        if count >= MAX_CONTRADICTS_EDGES:
            break
        group_sorted = sorted(group, key=lambda t: t.priority_rank)
        for i, t_a in enumerate(group_sorted):
            if count >= MAX_CONTRADICTS_EDGES:
                break
            for t_b in group_sorted[i + 1: i + 30]:
                if count >= MAX_CONTRADICTS_EDGES:
                    break
                if t_a.ticket_type == t_b.ticket_type:
                    continue
                shared = t_a.tags & t_b.tags
                if len(shared) < 3:
                    continue
                pair = (min(t_a.fact_id, t_b.fact_id), max(t_a.fact_id, t_b.fact_id))
                if pair in seen_pairs:
                    continue
                seen_pairs.add(pair)
                try:
                    kv.add_edge(
                        source_id=t_a.fact_id,
                        target_id=t_b.fact_id,
                        edge_type="CONTRADICTS",
                        valid_from=min(t_a.timestamp, t_b.timestamp),
                        confidence=0.55,
                        origin="OBSERVED",
                        role="MECHANISTIC",
                    )
                    count += 1
                except Exception as exc:
                    log.debug("CONTRADICTS edge failed: %s", exc)

    log.info("Built %d CONTRADICTS edges (same queue, >=3 shared tags, diff type)", count)
    return count


# ---------------------------------------------------------------------------
# Step 5: Save ground-truth holdout
# ---------------------------------------------------------------------------
def save_ground_truth(holdout: List[SupportTicket]) -> None:
    gt_rows = [
        {
            "subject": t.subject,
            "body": t.body,
            "answer": t.answer,
            "type": t.ticket_type,
            "queue": t.queue,
            "priority": t.priority,
            "language": t.language,
            "tags": sorted(t.tags),
        }
        for t in holdout
    ]
    gt_path = TARGET_DIR / "ground_truth.json"
    with open(gt_path, "w", encoding="utf-8") as f:
        json.dump(gt_rows, f, ensure_ascii=False, indent=2)
    log.info("Saved %d ground-truth queries to %s", len(gt_rows), gt_path)


# ---------------------------------------------------------------------------
# Step 6: Stats + smoke test via kv.verify()
# ---------------------------------------------------------------------------
def print_stats(
    selected: List[SupportTicket],
    similar: int,
    infers: int,
    causes: int,
    contradicts: int,
    kv,                       # fresh KoshVerify loaded from snapshot
) -> None:
    total_edges = similar + infers + causes + contradicts
    avg_degree = (2 * total_edges / len(selected)) if selected else 0

    type_dist  = Counter(t.ticket_type for t in selected)
    lang_dist  = Counter(t.language for t in selected)
    queue_dist = Counter(t.queue for t in selected)
    prio_dist  = Counter(t.priority for t in selected)
    tag_counts = [len(t.tags) for t in selected]
    avg_tags   = sum(tag_counts) / len(tag_counts) if tag_counts else 0

    ts_min = min(t.timestamp for t in selected if t.timestamp)
    ts_max = max(t.timestamp for t in selected if t.timestamp)

    print()
    print("=== Support Ticket Benchmark Cartridge Built ===")
    print(f"Facts ingested:         {len(selected):>6,}")
    print(f"  - EN tickets:         {lang_dist.get('en', 0):>6,}")
    print(f"  - DE tickets:         {lang_dist.get('de', 0):>6,}")
    print(f"Ticket types:           {dict(type_dist)}")
    print(f"Priorities:             {dict(prio_dist)}")
    print(f"Avg tags/ticket:        {avg_tags:.2f}")
    print()
    print(f"STRUCTURALLY_SIMILAR:   {similar:>6,}")
    print(f"INFERS edges:           {infers:>6,}")
    print(f"CAUSES edges:           {causes:>6,}")
    print(f"CONTRADICTS edges:      {contradicts:>6,}")
    print(f"Total edges:            {total_edges:>6,}")
    print(f"Avg node degree:        {avg_degree:.1f}")
    print()
    print(f"Top queues: {dict(queue_dist.most_common(4))}")
    print(f"Synthetic date range:   {ts_min.date()} -> {ts_max.date()}")
    print()

    # Smoke test via KoshVerify.verify() -> VerifyReport
    smoke_query = "server crash data loss recovery"
    print(f"Smoke test: kv.verify(\"{smoke_query}\")")
    try:
        report = kv.verify(smoke_query, dialectic=True, depth=4)
        print(f"  Status:              {report.status}")
        print(f"  Stability:           {report.stability_score:.2f} ({report.stability_status})")
        print(f"  Abstain:             {report.abstain}")
        print(f"  Facts retrieved:     {len(report.facts)}")
        print(f"  Contradictions:      {len(report.contradictions)}")
        print(f"  Inferred edges:      {len(report.inferred_not_discovered)}")
        if report.primary_answer:
            preview = report.primary_answer[:120].replace("\n", " ")
            print(f"  Primary answer:      {preview}...")
        print()
        print("  Provenance:")
        print("   ", kv.explain_provenance(report).replace("\n", "\n    "))
    except Exception as exc:
        print(f"  Smoke test error: {exc}")

    print()
    print(f"=== Done. Cartridge at {TARGET_DIR} ===")
    print(f"    Ground truth: {TARGET_DIR / 'ground_truth.json'}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> None:
    parser = argparse.ArgumentParser(
        description="Ingest support tickets into a HypoKosh Variant B cartridge (KoshVerify API)."
    )
    parser.add_argument("--force", action="store_true", help="Skip overwrite confirmation.")
    args = parser.parse_args()

    if not SOURCE_CSV.exists():
        log.error("Source CSV not found: %s", SOURCE_CSV)
        sys.exit(1)

    TARGET_DIR.mkdir(parents=True, exist_ok=True)

    # Clear existing cartridge on --force or user confirmation
    snapshot_file = TARGET_DIR / "reasoning" / "snapshot.json"
    events_file   = TARGET_DIR / "reasoning" / "events.jsonl"

    if snapshot_file.exists() and not args.force:
        ans = input(
            f"Target cartridge already exists at {TARGET_DIR}. Overwrite? [y/N] "
        ).strip().lower()
        if ans not in ("y", "yes"):
            print("Aborted.")
            sys.exit(0)

    for f in [snapshot_file, events_file, TARGET_DIR / ".self_model.json"]:
        if f.exists():
            f.unlink()
    log.info("Cleared existing cartridge files.")

    # Load data
    all_tickets = load_source(SOURCE_CSV)
    selected, holdout_tickets = select_tickets(all_tickets)
    assign_timestamps(selected)
    assign_timestamps(holdout_tickets)

    # -----------------------------------------------------------------------
    # Initialize KoshVerify — the correct product API
    # -----------------------------------------------------------------------
    log.info("Initializing KoshVerify at %s", TARGET_DIR)
    from llm_kosh.verify import KoshVerify
    kv = KoshVerify(TARGET_DIR)

    # -----------------------------------------------------------------------
    # Ingest facts via kv.add_fact()
    # -----------------------------------------------------------------------
    log.info("Ingesting %d facts via kv.add_fact()...", len(selected))
    ingest_facts(kv, selected)

    # -----------------------------------------------------------------------
    # Build edges via kv.add_edge() — proper EdgeProvenance included
    # -----------------------------------------------------------------------
    log.info("Building STRUCTURALLY_SIMILAR edges (tag overlap)...")
    similar = build_similar_edges(kv, selected)

    log.info("Building INFERS edges (Incident -> Request)...")
    infers = build_infers_edges(kv, selected)

    log.info("Building CAUSES edges (Problem -> Incident)...")
    causes = build_causes_edges(kv, selected)

    log.info("Building CONTRADICTS edges (same queue, diff type, >=3 tags)...")
    contradicts = build_contradicts_edges(kv, selected)

    # -----------------------------------------------------------------------
    # Save snapshot, then reload for smoke test
    # kv.add_fact() bypasses engine.ingest() so the TF-IDF retrieval index
    # was never marked dirty.  Saving the snapshot and creating a fresh
    # KoshVerify forces a clean rebuild of CausalRetrieval from all 3k facts.
    # -----------------------------------------------------------------------
    log.info("Saving DAG snapshot...")
    kv.engine.dag.save_snapshot()
    log.info("Snapshot saved.")

    # Save ground truth
    save_ground_truth(holdout_tickets)

    # Reload for smoke test (fresh CausalRetrieval from snapshot)
    log.info("Reloading KoshVerify for smoke test...")
    kv_fresh = KoshVerify(TARGET_DIR)

    # Stats + smoke test
    print_stats(selected, similar, infers, causes, contradicts, kv_fresh)


if __name__ == "__main__":
    main()
