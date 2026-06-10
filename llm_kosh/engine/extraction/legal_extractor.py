"""
Legal judgment causal extraction pipeline.

Two-pass algorithm:
  Pass 1: process_document() ingests primary fact (no edges yet)
  Pass 2: edges resolved via build_case_index() + find_or_create_stub()
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Dict, List, Optional

import yaml

from llm_kosh.engine.extraction.patterns import PATTERN_LIST, PATTERN_TO_EDGE_TYPE

UTC = timezone.utc


# ---------------------------------------------------------------------------
# parse_frontmatter
# ---------------------------------------------------------------------------

def parse_frontmatter(filepath: str) -> dict:
    """
    Read a Markdown file and parse its YAML frontmatter.

    Returns a dict with keys: id, title, status, created, body.
    If no frontmatter is found, all metadata fields are None/defaults and
    body is the full file text.
    """
    try:
        with open(filepath, encoding="utf-8", errors="replace") as fh:
            raw = fh.read()
    except OSError:
        return {"id": None, "title": "", "status": "active", "created": None, "body": ""}

    # Frontmatter must start with '---' at the very beginning of the file
    if not raw.startswith("---"):
        return {"id": None, "title": "", "status": "active", "created": None, "body": raw}

    # Find the closing '---'
    end_marker = raw.find("\n---", 3)
    if end_marker == -1:
        return {"id": None, "title": "", "status": "active", "created": None, "body": raw}

    yaml_block = raw[3:end_marker]
    body = raw[end_marker + 4:].lstrip("\n")  # skip the closing --- line

    try:
        meta = yaml.safe_load(yaml_block) or {}
    except yaml.YAMLError:
        meta = {}

    return {
        "id": meta.get("id"),
        "title": meta.get("title", ""),
        "status": meta.get("status", "active"),
        "created": meta.get("created"),
        "body": body,
    }


# ---------------------------------------------------------------------------
# parse_judgment_date
# ---------------------------------------------------------------------------

def parse_judgment_date(filename: str, title: str) -> datetime:
    """
    Extract judgment date from title or filename.

    Priority:
      1. Precise date embedded in title: _DD-Mon-YYYY
      2. Year from filename segment: supremecourt[_-]YYYY
      3. Fallback: 2000-01-01 UTC
    """
    # First try precise date from title: pattern '_DD-Mon-YYYY'
    m = re.search(r'_(\d{1,2})-([A-Z][a-z]{2})-(\d{4})', title)
    if m:
        try:
            dt = datetime.strptime(f"{m.group(1)}-{m.group(2)}-{m.group(3)}", "%d-%b-%Y")
            return dt.replace(tzinfo=UTC)
        except ValueError:
            pass

    # Fall back to year from filename second segment
    m2 = re.search(r'supremecourt[_-](\d{4})', filename)
    if m2:
        return datetime(int(m2.group(1)), 1, 1, tzinfo=UTC)

    # Final fallback
    return datetime(2000, 1, 1, tzinfo=UTC)


# ---------------------------------------------------------------------------
# clean_body
# ---------------------------------------------------------------------------

def clean_body(body: str) -> str:
    """
    Normalize judgment body text for pattern matching.

    Removes:
      - Markdown table rows  (lines matching | ... |)
      - Lone page numbers    (lines that are just 1-3 digits)
    Collapses multiple whitespace/newlines to a single space.
    """
    lines = body.splitlines()
    kept = []
    for line in lines:
        stripped = line.strip()
        # Drop table rows
        if stripped.startswith("|") and stripped.endswith("|"):
            continue
        # Drop lone page numbers (1-3 digits only)
        if re.fullmatch(r'\d{1,3}', stripped):
            continue
        kept.append(stripped)

    text = " ".join(kept)
    # Collapse multiple spaces
    text = re.sub(r'\s{2,}', ' ', text)
    return text.strip()


# ---------------------------------------------------------------------------
# compute_confidence
# ---------------------------------------------------------------------------

def compute_confidence(base: float, sentence: str, citation: str) -> float:
    """
    Adjust base confidence based on sentence and citation quality signals.

    Adjustments (cumulative):
      +0.10  citation contains reporter (SCC/SCR/ELT/AIR) + year + page number
      -0.10  citation has only a year (no reporter)
      -0.15  sentence contains a quoted block (" or ')
      -0.05  sentence contains "NON-REPORTABLE"
      -0.15  sentence contains "(supra)" and no citation

    Final value is clamped to [0.40, 0.95].
    """
    score = base

    if citation:
        # Full reporter citation: reporter keyword + 4-digit year + digits
        if re.search(r'(?:SCC|SCR|ELT|AIR)\s+\d+', citation) and re.search(r'\d{4}', citation):
            score += 0.10
        elif re.fullmatch(r'\s*(?:19|20)\d{2}\s*', citation):
            # Only a bare year
            score -= 0.10

    if '"' in sentence or "'" in sentence:
        score -= 0.15

    if "NON-REPORTABLE" in sentence:
        score -= 0.05

    if "(supra)" in sentence.lower() and not citation:
        score -= 0.15

    return max(0.40, min(0.95, score))


# ---------------------------------------------------------------------------
# extract_facts_and_edges
# ---------------------------------------------------------------------------

def extract_facts_and_edges(
    text: str,
    filepath: str,
    existing_fact_index: dict,
) -> List[dict]:
    """
    Run all pattern groups over text sentences and return a list of extraction dicts.

    Each dict: {
        "content":      str (≤500 chars),
        "pattern_type": str,
        "raw_case_name": str | None,
        "citation":     str | None,
        "confidence":   float,
        "edge_type":    str | None,
    }

    Limits:
      - First 200 sentences considered
      - One match per sentence per pattern group
      - At most 20 results returned
    """
    # Split on sentence boundaries: period followed by whitespace, or double newline
    raw_sentences = re.split(r'(?<=\.)\s+|\n{2,}', text)
    sentences = [s.strip() for s in raw_sentences if s.strip()][:200]

    results: List[dict] = []

    for sent in sentences:
        if len(results) >= 20:
            break

        for pattern_type, patterns, base_conf in PATTERN_LIST:
            if len(results) >= 20:
                break

            for pat in patterns:
                m = re.search(pat, sent, re.IGNORECASE)
                if m:
                    # Extract named groups when available
                    raw_case = None
                    citation = None
                    try:
                        raw_case = m.group("case").strip() if "case" in m.groupdict() else None
                    except IndexError:
                        pass
                    try:
                        citation = m.group("citation").strip() if "citation" in m.groupdict() else None
                    except IndexError:
                        pass

                    confidence = compute_confidence(base_conf, sent, citation or "")
                    edge_type = PATTERN_TO_EDGE_TYPE.get(pattern_type)

                    results.append({
                        "content": sent[:500],
                        "pattern_type": pattern_type,
                        "raw_case_name": raw_case,
                        "citation": citation,
                        "confidence": confidence,
                        "edge_type": edge_type,
                    })
                    break  # one match per sentence per pattern group

    return results


# ---------------------------------------------------------------------------
# find_or_create_stub
# ---------------------------------------------------------------------------

def find_or_create_stub(case_name: str, citation: str, engine) -> Optional[str]:
    """
    Look up or create a stub TemporalFact for a referenced case.

    Normalizes case_name by lowercasing and stripping common legal suffixes,
    then searches engine.dag.nodes for an existing match.

    Returns the matched fact_id, a newly created stub fact_id, or None on error.
    """
    try:
        # Normalize: lowercase, strip common suffixes
        normalized = case_name.lower()
        for suffix in ("& ors", "& anr", "(dead)", "ltd.", "ltd", "pvt.", "pvt"):
            normalized = normalized.replace(suffix, "").strip()
        normalized = re.sub(r'\s+', ' ', normalized).strip()

        if not normalized:
            return None

        matches: List[str] = []
        for fact_id, fact in engine.dag.nodes.items():
            if normalized in fact.content.lower():
                matches.append(fact_id)

        if len(matches) == 1:
            return matches[0]

        if len(matches) == 0:
            # Create stub fact
            stub_content = f"{case_name} {citation}".strip()
            now = datetime.now(UTC)
            epoch = datetime(2000, 1, 1, tzinfo=UTC)
            new_id = engine.dag.add_fact(
                content=stub_content,
                ingested_at=now,
                documented_at=epoch,
                valid_from=epoch,
                valid_until=None,
                confidence=0.50,
                source="stub",
            )
            return new_id

        # Multiple matches: return the one with the earliest valid_from
        best = min(matches, key=lambda fid: engine.dag.nodes[fid].valid_from)
        return best

    except Exception:
        return None


# ---------------------------------------------------------------------------
# build_case_index
# ---------------------------------------------------------------------------

def build_case_index(dag) -> dict:
    """
    Build a normalized-name -> fact_id index from all facts in the DAG.

    Extracts case names from fact content using the v./vs./versus pattern,
    normalizes them, and returns the mapping.
    """
    index: Dict[str, str] = {}
    vs_pattern = re.compile(
        r'([A-Z][^\n]+?(?:v\.|vs\.|versus)[^\n]+?)(?:\s*\(|\s*,|\s*$)',
        re.MULTILINE,
    )

    for fact_id, fact in dag.nodes.items():
        for m in vs_pattern.finditer(fact.content):
            raw = m.group(1).strip()
            normalized = raw.lower()
            for suffix in ("& ors", "& anr", "(dead)", "ltd.", "ltd", "pvt.", "pvt"):
                normalized = normalized.replace(suffix, "").strip()
            normalized = re.sub(r'\s+', ' ', normalized).strip()
            if normalized and normalized not in index:
                index[normalized] = fact_id

    return index


# ---------------------------------------------------------------------------
# process_document
# ---------------------------------------------------------------------------

def process_document(filepath: str, engine) -> Optional[str]:
    """
    Full two-pass extraction pipeline for a single Markdown judgment document.

    Pass 1: Ingest the primary fact (no edges).
    Pass 2: Resolve referenced cases and add causal edges.

    Returns the primary fact_id, or None if the document is skipped.
    """
    import os
    filename = os.path.basename(filepath)

    # Skip vernacular documents
    if "vernacular" in filename.lower():
        return None

    meta = parse_frontmatter(filepath)
    if meta.get("status") != "active":
        return None

    text = clean_body(meta["body"])
    if len(text) < 200:
        return None  # stub/empty document

    is_reportable = "NON-REPORTABLE" not in text[:500]

    # Parse judgment date
    title = meta.get("title", "") or filename
    judgment_date = parse_judgment_date(filename, title)

    # Extract case name for the primary content header
    case_name_match = re.search(r'([A-Z][^\n]+(?:v\.|vs\.|versus)[^\n]+)', title)
    case_header = case_name_match.group(1).strip() if case_name_match else filename

    # Build current DAG index, then run pattern matching
    existing_index = build_case_index(engine.dag)
    extractions = extract_facts_and_edges(text, filepath, existing_index)

    # Build primary fact content from case header + top 3 extracted sentences
    snippet_parts = [r["content"] for r in extractions[:3]]
    primary_content = (case_header + ". " + " ".join(snippet_parts))[:1000]

    # Pass 1: ingest primary fact with no edges
    primary_fact_id = engine.ingest(
        content=primary_content,
        documented_at=judgment_date,
        valid_from=judgment_date,
        valid_until=None,
        confidence=0.85 if is_reportable else 0.70,
        causal_edges=[],
    )

    # Pass 2: add edges from extracted relationships
    from llm_kosh.engine.reasoning.causal_dag import EdgeType
    for result in extractions:
        if not result.get("edge_type") or not result.get("raw_case_name"):
            continue
        target_id = find_or_create_stub(
            result["raw_case_name"],
            result.get("citation", "") or "",
            engine,
        )
        if target_id and target_id != primary_fact_id:
            try:
                engine.dag.add_edge(
                    source_id=primary_fact_id,
                    target_id=target_id,
                    edge_type=EdgeType(result["edge_type"]),
                    confidence=result["confidence"],
                    valid_from=judgment_date,
                    valid_until=None,
                    established_by="legal_extractor",
                )
            except (ValueError, Exception):
                pass

    return primary_fact_id
