"""
ingest_judis_cartridge.py
One-shot ingestion script: reads Supreme Court of India judgments from an
existing SQLite cartridge and ingests them into a fresh TheHypoKosh
ReasoningEngine cartridge for benchmarking.

Edge strategy (revised):
  STRUCTURALLY_SIMILAR — any two cases sharing ≥1 judge (up to 10 pairs per
                          judge cluster, capped at MAX_SIMILAR_EDGES total)
  CAUSES               — two cases sharing ≥2 judges, chronological order
                          (cap MAX_CAUSES_EDGES total)
  INFERS               — case A's body cites "AIR YYYY SC NNN" where that
                          citation belongs to case B in the corpus
  CONTRADICTS          — petitioner/respondent token flip within same decade

Usage:
    python scripts/ingest_judis_cartridge.py [--force]

    --force   Skip overwrite confirmation and always rebuild from scratch.
"""
from __future__ import annotations

import argparse
import logging
import re
import sqlite3
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, FrozenSet, List, Optional, Set, Tuple

# ---------------------------------------------------------------------------
# sys.path fix so script runs directly
# ---------------------------------------------------------------------------
_SCRIPT_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _SCRIPT_DIR.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

# ---------------------------------------------------------------------------
# Paths & tuning knobs
# ---------------------------------------------------------------------------
SOURCE_DB = Path(r"C:\Users\vrast\OneDrive\Apps\Documents\llm-kosh-cart\indexes\memory.sqlite")
TARGET_DIR = Path(r"C:\Users\vrast\Downloads\llm-kosh-judis-bench")
TARGET_COUNT = 3_000

MAX_SIMILAR_EDGES = 4_000   # STRUCTURALLY_SIMILAR cap
MAX_CAUSES_EDGES  = 600     # CAUSES cap
MAX_INFERS_EDGES  = 500     # INFERS cap
MAX_CONTRADICTS_EDGES = 300 # CONTRADICTS cap
PAIRS_PER_JUDGE   = 15      # consecutive pairs to link per judge cluster

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
# Date parsing helpers
# ---------------------------------------------------------------------------
_DATE_PATTERNS = [
    re.compile(r"DATE OF JUDGMENT\s*(\d{1,2}[/\-\.]\d{1,2}[/\-\.]\d{2,4})", re.IGNORECASE),
    re.compile(r"Date of Judgment[:\s]+(\d{1,2}[/\-\.]\d{1,2}[/\-\.]\d{2,4})", re.IGNORECASE),
    re.compile(r"DECIDED ON[:\s]+(\d{1,2}[/\-\.]\d{1,2}[/\-\.]\d{2,4})", re.IGNORECASE),
    # Newer format: date in title string like "Judgement_09-May-2018"
    re.compile(r"Judgement?_(\d{2}-\w{3}-\d{4})", re.IGNORECASE),
    re.compile(r"Judgment_(\d{2}-\w{3}-\d{4})", re.IGNORECASE),
]
_YEAR_PATTERN = re.compile(r"\b(19[5-9]\d|20[0-2]\d)\b")
_MONTH_ABBR = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}


def _parse_date_string(date_str: str) -> Optional[datetime]:
    """Parse DD/MM/YYYY, DD-MM-YYYY, DD.MM.YYYY, DD-Mon-YYYY."""
    date_str = date_str.strip()
    # Try DD-Mon-YYYY (e.g. "09-May-2018")
    m = re.match(r"(\d{1,2})-([A-Za-z]{3})-(\d{4})", date_str)
    if m:
        day, mon, year = int(m.group(1)), m.group(2).lower(), int(m.group(3))
        month = _MONTH_ABBR.get(mon)
        if month and 1950 <= year <= 2030:
            try:
                return datetime(year, month, day, tzinfo=timezone.utc)
            except ValueError:
                pass
    # Normalise separators to /
    date_str = re.sub(r"[.\-]", "/", date_str)
    parts = date_str.split("/")
    if len(parts) != 3:
        return None
    try:
        day, month, year = int(parts[0]), int(parts[1]), int(parts[2])
    except ValueError:
        return None
    if year < 100:
        year += 1900
    if not (1 <= month <= 12 and 1 <= day <= 31 and 1950 <= year <= 2030):
        return None
    try:
        return datetime(year, month, day, tzinfo=timezone.utc)
    except ValueError:
        return None


def extract_date(body: str, title: str = "") -> Tuple[Optional[datetime], bool]:
    """
    Try all date patterns in order on body + title.
    Returns (datetime_or_None, is_precise).
    """
    search_text = title + "\n" + body
    for pattern in _DATE_PATTERNS:
        m = pattern.search(search_text)
        if m:
            dt = _parse_date_string(m.group(1))
            if dt:
                return dt, True
    # Year fallback from first 300 chars of body
    ym = _YEAR_PATTERN.search(body[:300])
    if ym:
        year = int(ym.group(1))
        return datetime(year, 1, 1, tzinfo=timezone.utc), False
    return None, False


# ---------------------------------------------------------------------------
# Field extraction helpers
# ---------------------------------------------------------------------------
def extract_all_judges(body: str) -> List[str]:
    """Extract all judge names from BENCH section(s)."""
    bench_section = re.search(
        r"BENCH:(.*?)(?:CITATION:|ACT:|HEADNOTE:|JUDGMENT:|J\s*U\s*D\s*G\s*M\s*E\s*N\s*T)",
        body, re.DOTALL,
    )
    if not bench_section:
        return []
    bench_text = bench_section.group(1)
    judges: List[str] = []
    for line in bench_text.split("\n"):
        line = line.strip()
        if len(line) < 4:
            continue
        if not re.match(r"[A-Z]", line):
            continue
        # Strip judge-role suffixes
        name = re.sub(r"\s*\([JC][J]?\)\s*$", "", line, flags=re.IGNORECASE).strip()
        name = re.sub(r"\s+[JC][J]?\.\s*$", "", name, flags=re.IGNORECASE).strip()
        name = name.strip(",. ")
        if len(name) > 3 and not name.upper().startswith("BENCH"):
            judges.append(name.lower())
    return list(set(judges))


def extract_petitioner(body: str) -> Optional[str]:
    # JUDIS old format
    m = re.search(r"PETITIONERS?[:\s]*\n?\s*([^\n]{5,120})", body)
    if m:
        val = m.group(1).strip()
        if val and not val.upper().startswith("VS") and len(val) >= 3:
            return val
    # Newer format: look for "…Petitioner" or "…Appellant"
    m = re.search(r"([A-Z][^\n]{5,100})\s*[….]+\s*(?:Petitioner|Appellant)", body)
    if m:
        return m.group(1).strip()
    return None


def extract_respondent(body: str) -> Optional[str]:
    m = re.search(r"RESPONDENTS?[:\s]*\n?\s*([^\n]{5,120})", body)
    if m:
        val = m.group(1).strip()
        if val and not val.upper().startswith("VS") and len(val) >= 3:
            return val
    m = re.search(r"([A-Z][^\n]{5,100})\s*[….]+\s*(?:Respondent)", body)
    if m:
        return m.group(1).strip()
    return None


def extract_judis_num(title: str) -> Optional[str]:
    m = re.search(r"judis[_\-\s]*(\d+)", title, re.IGNORECASE)
    return m.group(1) if m else None


def extract_own_air_citation(body: str) -> Optional[Tuple[str, str]]:
    """Extract (year, page) from the CITATION section's AIR entry."""
    cit_match = re.search(
        r"CITATION:(.*?)(?:ACT:|HEADNOTE:|JUDGMENT:|\Z)", body, re.DOTALL
    )
    if not cit_match:
        return None
    cit_text = cit_match.group(1)
    m = re.search(r"(\d{4})\s+AIR\s+(\d+)", cit_text)
    if m:
        return m.group(1), m.group(2)
    return None


def extract_body_air_citations(body: str) -> List[Tuple[str, str]]:
    """Find AIR YYYY SC NNN cross-references in the judgment body text."""
    j_start = body.find("JUDGMENT:")
    if j_start < 0:
        j_start = max(0, len(body) - 40000)  # search last 40k for long new-format docs
    text = body[j_start:]
    return re.findall(r"AIR\s+(\d{4})\s+SC\s+(\d+)", text, re.IGNORECASE)


def normalize_party(name: str) -> str:
    """Lowercase + strip punctuation, take first 30 chars for matching."""
    cleaned = re.sub(r"[^a-z0-9 ]", "", name.lower()).strip()
    # Remove common bracketed qualifiers like "[IN T.C.(C) NO.9/94]"
    cleaned = re.sub(r"\[.*?\]", "", cleaned).strip()
    return cleaned[:30]


# ---------------------------------------------------------------------------
# Data structure
# ---------------------------------------------------------------------------
class JudisDoc:
    __slots__ = (
        "doc_id", "title", "body", "judis_num",
        "judgment_date", "is_precise_date",
        "judges",
        "petitioner", "respondent",
        "own_air_citation",  # (year, page) or None
        "score", "fact_id", "content",
    )

    def __init__(self, doc_id: str, title: str, body: str):
        self.doc_id = doc_id
        self.title = title
        self.body = body
        self.judis_num: Optional[str] = extract_judis_num(title)
        self.judgment_date: Optional[datetime] = None
        self.is_precise_date: bool = False
        self.judges: List[str] = []
        self.petitioner: Optional[str] = None
        self.respondent: Optional[str] = None
        self.own_air_citation: Optional[Tuple[str, str]] = None
        self.score: int = 0
        self.fact_id: Optional[str] = None
        self.content: str = ""

    def parse(self) -> None:
        self.judgment_date, self.is_precise_date = extract_date(self.body, self.title)
        self.judges = extract_all_judges(self.body)
        self.petitioner = extract_petitioner(self.body)
        self.respondent = extract_respondent(self.body)
        self.own_air_citation = extract_own_air_citation(self.body)

        pet = self.petitioner or "Unknown"
        resp = self.respondent or "Unknown"
        bench_str = ", ".join(self.judges[:3]) if self.judges else ""
        year_str = str(self.judgment_date.year) if self.judgment_date else "undated"
        self.content = f"{pet} v {resp} | {bench_str} | {year_str}\n{self.body[:400]}"


# ---------------------------------------------------------------------------
# Step 1: Read all documents from SQLite
# ---------------------------------------------------------------------------
def load_documents() -> List[JudisDoc]:
    log.info("Reading documents from %s", SOURCE_DB)
    conn = sqlite3.connect(SOURCE_DB)
    cur = conn.cursor()
    cur.execute("SELECT id, title, body FROM documents")
    docs: List[JudisDoc] = []
    skipped = 0
    for row in cur:
        try:
            doc = JudisDoc(doc_id=row[0], title=row[1] or "", body=row[2] or "")
            doc.parse()
            if doc.judgment_date is None:
                skipped += 1
                continue
            docs.append(doc)
        except Exception as exc:
            log.warning("Skipping doc %s: %s", row[0], exc)
            skipped += 1
    conn.close()
    log.info("Loaded %d parseable docs (%d skipped — no date)", len(docs), skipped)
    return docs


# ---------------------------------------------------------------------------
# Step 2: Score and select top N
# ---------------------------------------------------------------------------
def select_top(docs: List[JudisDoc], n: int = TARGET_COUNT) -> List[JudisDoc]:
    log.info("Scoring %d docs to select top %d", len(docs), n)
    bench_counter: Counter = Counter()
    petitioner_counter: Counter = Counter()
    for doc in docs:
        for j in doc.judges:
            bench_counter[j] += 1
        if doc.petitioner:
            petitioner_counter[normalize_party(doc.petitioner)] += 1

    for doc in docs:
        score = 0
        if doc.is_precise_date:
            score += 3
        if doc.own_air_citation:
            score += 2  # has a parseable AIR citation — likely old-format with rich data
        if doc.judges and any(bench_counter[j] >= 5 for j in doc.judges):
            score += 1
        if doc.petitioner and petitioner_counter[normalize_party(doc.petitioner)] >= 3:
            score += 1
        # Bonus for having multiple judges (constitutional bench → richer precedent)
        if len(doc.judges) >= 5:
            score += 1
        doc.score = score

    docs.sort(key=lambda d: d.score, reverse=True)
    selected = docs[:n]
    log.info(
        "Selected %d docs. Score: min=%d max=%d",
        len(selected),
        selected[-1].score if selected else 0,
        selected[0].score if selected else 0,
    )
    return selected


# ---------------------------------------------------------------------------
# Step 3: Ingest facts
# ---------------------------------------------------------------------------
def ingest_facts(engine, docs: List[JudisDoc]) -> None:
    total = len(docs)
    for i, doc in enumerate(docs, start=1):
        try:
            fact_id = engine.ingest(
                content=doc.content,
                documented_at=doc.judgment_date,
                valid_from=doc.judgment_date,
                valid_until=None,
                confidence=0.9,
                causal_edges=[],
            )
            doc.fact_id = fact_id
        except Exception as exc:
            log.warning("Failed to ingest %s: %s", doc.doc_id, exc)
        if i % 250 == 0:
            log.info("Ingested %d/%d facts...", i, total)
    log.info("Ingested %d facts total.", total)


# ---------------------------------------------------------------------------
# Step 4a: INFERS edges — AIR citation network
# ---------------------------------------------------------------------------
def build_infers_edges(engine, docs: List[JudisDoc]) -> int:
    """
    Build INFERS edges when case A's body cites 'AIR YYYY SC NNN' and that
    citation's (year, page) matches another case B's own_air_citation.
    """
    # Index: (year, page) -> doc
    air_index: Dict[Tuple[str, str], JudisDoc] = {}
    for doc in docs:
        if doc.own_air_citation and doc.fact_id:
            air_index[doc.own_air_citation] = doc

    log.info("AIR citation index: %d entries", len(air_index))

    count = 0
    seen: Set[Tuple[str, str]] = set()

    for doc in docs:
        if not doc.fact_id or count >= MAX_INFERS_EDGES:
            break
        cross_refs = extract_body_air_citations(doc.body)
        for year, page in cross_refs:
            cited_doc = air_index.get((year, page))
            if not cited_doc or not cited_doc.fact_id:
                continue
            if cited_doc.fact_id == doc.fact_id:
                continue
            pair = (doc.fact_id, cited_doc.fact_id)
            if pair in seen:
                continue
            seen.add(pair)
            try:
                engine.add_edge_at(
                    source_id=doc.fact_id,
                    target_id=cited_doc.fact_id,
                    edge_type="INFERS",
                    confidence=0.75,
                    valid_from=doc.judgment_date,
                    origin="OBSERVED",
                    role="MECHANISTIC",
                )
                count += 1
            except Exception as exc:
                log.debug("INFERS edge failed: %s", exc)

    log.info("Built %d INFERS edges", count)
    return count


# ---------------------------------------------------------------------------
# Step 4b: CAUSES + STRUCTURALLY_SIMILAR edges — shared judge bench network
# ---------------------------------------------------------------------------
def build_bench_edges(engine, docs: List[JudisDoc]) -> Tuple[int, int]:
    """
    For each judge that appears in 2+ cases:
      - Cases sharing ≥2 judges, chronological order → CAUSES
      - Cases sharing 1 judge, chronological order  → STRUCTURALLY_SIMILAR

    Returns (causes_count, similar_count).
    """
    # Build judge → docs index (only docs with at least 1 judge and a date)
    judge_to_docs: Dict[str, List[JudisDoc]] = defaultdict(list)
    for doc in docs:
        if doc.fact_id and doc.judgment_date and doc.judges:
            for j in doc.judges:
                judge_to_docs[j].append(doc)

    seen_pairs: Set[Tuple[str, str]] = set()
    causes_count = 0
    similar_count = 0

    # Process judges sorted by cluster size (largest first — richest signal)
    for judge, cluster in sorted(judge_to_docs.items(), key=lambda x: -len(x[1])):
        if causes_count >= MAX_CAUSES_EDGES and similar_count >= MAX_SIMILAR_EDGES:
            break
        # Sort cluster by date
        cluster_sorted = sorted(cluster, key=lambda d: d.judgment_date)
        pairs_this_judge = 0
        for i in range(len(cluster_sorted) - 1):
            if pairs_this_judge >= PAIRS_PER_JUDGE:
                break
            if causes_count >= MAX_CAUSES_EDGES and similar_count >= MAX_SIMILAR_EDGES:
                break
            a = cluster_sorted[i]
            b = cluster_sorted[i + 1]
            pair_key = (
                min(a.fact_id, b.fact_id),
                max(a.fact_id, b.fact_id),
            )
            if pair_key in seen_pairs:
                continue
            seen_pairs.add(pair_key)

            shared_judges = set(a.judges) & set(b.judges)
            if len(shared_judges) >= 2 and causes_count < MAX_CAUSES_EDGES:
                edge_type = "CAUSES"
            elif similar_count < MAX_SIMILAR_EDGES:
                edge_type = "STRUCTURALLY_SIMILAR"
            else:
                continue

            try:
                engine.add_edge_at(
                    source_id=a.fact_id,
                    target_id=b.fact_id,
                    edge_type=edge_type,
                    confidence=0.65 if edge_type == "CAUSES" else 0.55,
                    valid_from=a.judgment_date,
                    origin="INFERRED",
                    role="CAUSAL" if edge_type == "CAUSES" else "ANALOGICAL",
                )
                if edge_type == "CAUSES":
                    causes_count += 1
                else:
                    similar_count += 1
                pairs_this_judge += 1
            except Exception as exc:
                log.debug("%s edge failed: %s", edge_type, exc)

    log.info("Built %d CAUSES edges (bench chains)", causes_count)
    log.info("Built %d STRUCTURALLY_SIMILAR edges (shared judge)", similar_count)
    return causes_count, similar_count


# ---------------------------------------------------------------------------
# Step 4c: CONTRADICTS edges — petitioner / respondent token flip
# ---------------------------------------------------------------------------
def build_contradicts_edges(engine, docs: List[JudisDoc]) -> int:
    """
    CONTRADICTS: if case A has petitioner P and respondent R, and case B has
    petitioner ~R and respondent ~P (same decade), the judgments may be in
    tension (appeal / retrial / reversal).

    Uses 30-char normalized key for fuzzy matching.
    """
    # Build two-way indexes
    pet_index: Dict[str, List[JudisDoc]] = defaultdict(list)
    resp_index: Dict[str, List[JudisDoc]] = defaultdict(list)

    for doc in docs:
        if not doc.fact_id or not doc.judgment_date:
            continue
        if doc.petitioner:
            key = normalize_party(doc.petitioner)
            if len(key) >= 5:
                pet_index[key].append(doc)
        if doc.respondent:
            key = normalize_party(doc.respondent)
            if len(key) >= 5:
                resp_index[key].append(doc)

    seen: Set[Tuple[str, str]] = set()
    count = 0

    for pet_key, pet_docs in pet_index.items():
        if count >= MAX_CONTRADICTS_EDGES:
            break
        # Look for cases where this petitioner name appears as respondent
        flipped = resp_index.get(pet_key, [])
        if not flipped:
            continue
        for doc_a in pet_docs:
            if count >= MAX_CONTRADICTS_EDGES:
                break
            decade_a = (doc_a.judgment_date.year // 10) * 10
            # doc_b has pet_key as respondent; confirm doc_b's petitioner ≈ doc_a's respondent
            for doc_b in flipped:
                if doc_b.fact_id == doc_a.fact_id:
                    continue
                decade_b = (doc_b.judgment_date.year // 10) * 10
                if abs(decade_a - decade_b) > 10:
                    continue
                pair_key = (
                    min(doc_a.fact_id, doc_b.fact_id),
                    max(doc_a.fact_id, doc_b.fact_id),
                )
                if pair_key in seen:
                    continue
                seen.add(pair_key)
                try:
                    engine.add_edge_at(
                        source_id=doc_a.fact_id,
                        target_id=doc_b.fact_id,
                        edge_type="CONTRADICTS",
                        confidence=0.5,
                        valid_from=min(doc_a.judgment_date, doc_b.judgment_date),
                        origin="INFERRED",
                        role="MECHANISTIC",
                    )
                    count += 1
                except Exception as exc:
                    log.debug("CONTRADICTS edge failed: %s", exc)
                break  # one CONTRADICTS per pair

    log.info("Built %d CONTRADICTS edges (party flip)", count)
    return count


# ---------------------------------------------------------------------------
# Step 5: Stats and smoke test
# ---------------------------------------------------------------------------
def print_stats(
    docs: List[JudisDoc],
    infers: int,
    causes: int,
    similar: int,
    contradicts: int,
    engine,
) -> None:
    precise = sum(1 for d in docs if d.is_precise_date)
    dates = [d.judgment_date.year for d in docs if d.judgment_date]
    date_range = f"{min(dates)} → {max(dates)}" if dates else "unknown"

    judge_counter: Counter = Counter()
    for doc in docs:
        for j in doc.judges:
            judge_counter[j] += 1
    top_judges = judge_counter.most_common(5)

    total_edges = infers + causes + similar + contradicts

    print()
    print("=== JUDIS Benchmark Cartridge Built ===")
    print(f"Facts ingested:         {len(docs):>6,}")
    print(f"  - precise date:       {precise:>6,}")
    print(f"  - year-only date:     {len(docs)-precise:>6,}")
    print(f"INFERS edges:           {infers:>6,}")
    print(f"CAUSES edges:           {causes:>6,}")
    print(f"STRUCTURALLY_SIMILAR:   {similar:>6,}")
    print(f"CONTRADICTS edges:      {contradicts:>6,}")
    print(f"Total edges:            {total_edges:>6,}")
    print(f"Date range:             {date_range}")
    print(f"Top 5 judges: {[(j, n) for j, n in top_judges]}")
    print()

    avg_degree = (2 * total_edges / len(docs)) if docs else 0
    print(f"Avg node degree:        {avg_degree:.1f}")
    print()

    # Smoke test
    print('Smoke test: query "constitutional rights judgment"')
    try:
        result = engine.query("constitutional rights judgment")
        print(f"  Stability: {result.stability.score:.2f} ({result.stability.status})")
        print(f"  Anchors retrieved: {len(result.anchors)}")
        print(f"  Escape triggered: {result.escape_triggered}")
    except Exception as exc:
        print(f"  Smoke test error: {exc}")
    print()
    print(f"=== Done. Cartridge at {TARGET_DIR} ===")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest JUDIS judgments into a HypoKosh cartridge.")
    parser.add_argument("--force", action="store_true", help="Skip overwrite confirmation.")
    args = parser.parse_args()

    if not SOURCE_DB.exists():
        log.error("Source SQLite not found: %s", SOURCE_DB)
        sys.exit(1)

    TARGET_DIR.mkdir(parents=True, exist_ok=True)

    # Handle existing cartridge
    dag_file = TARGET_DIR / "dag.json"
    if dag_file.exists():
        import json
        try:
            existing = json.load(open(dag_file))
            node_count = len(existing.get("nodes", {}))
        except Exception:
            node_count = -1

        if node_count > 0 and not args.force:
            ans = input(
                f"Target has {node_count} nodes. Overwrite? [y/N] "
            ).strip().lower()
            if ans not in ("y", "yes"):
                print("Aborted.")
                sys.exit(0)

        # Clear existing files for a clean rebuild
        for fname in ("dag.json", "edges.json"):
            f = TARGET_DIR / fname
            if f.exists():
                f.unlink()
        # Also clear the event log and self-model so the engine starts truly fresh
        events_file = TARGET_DIR / "reasoning" / "events.jsonl"
        if events_file.exists():
            events_file.unlink()
        self_model_file = TARGET_DIR / ".self_model.json"
        if self_model_file.exists():
            self_model_file.unlink()
        log.info("Cleared existing cartridge files (dag.json, events.jsonl, .self_model.json).")

    log.info("Initializing ReasoningEngine at %s", TARGET_DIR)
    from llm_kosh.engine.reasoning import ReasoningEngine
    engine = ReasoningEngine(TARGET_DIR)

    # Steps
    all_docs = load_documents()
    selected = select_top(all_docs)

    log.info("Ingesting %d facts...", len(selected))
    ingest_facts(engine, selected)

    log.info("Building INFERS edges (AIR citation network)...")
    infers = build_infers_edges(engine, selected)

    log.info("Building CAUSES + STRUCTURALLY_SIMILAR edges (bench network)...")
    causes, similar = build_bench_edges(engine, selected)

    log.info("Building CONTRADICTS edges (party flip)...")
    contradicts = build_contradicts_edges(engine, selected)

    print_stats(selected, infers, causes, similar, contradicts, engine)


if __name__ == "__main__":
    main()
