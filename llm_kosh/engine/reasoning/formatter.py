from __future__ import annotations

from datetime import datetime
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from llm_kosh.engine.reasoning import QueryResult
    from llm_kosh.engine.reasoning.fiber_bundle import Fiber
    from llm_kosh.engine.reasoning.causal_dag import CausalEdge

_WIDE  = "━" * 49   # ━━━━━ (49 chars)
_THIN  = "─" * 49   # ───── (49 chars)


def _extract_title(content: str) -> str:
    """First non-empty line, stripped of leading '#', max 60 chars."""
    for line in content.splitlines():
        stripped = line.strip().lstrip("#").strip()
        if stripped:
            return stripped[:60]
    return ""


def _extract_body(content: str) -> str:
    """First sentence after the title line, max 120 chars."""
    lines = content.splitlines()
    # Skip the title line (first non-empty line) and collect remaining content
    found_title = False
    body_parts = []
    for line in lines:
        stripped = line.strip()
        if not found_title:
            if stripped:
                found_title = True
            continue
        body_parts.append(stripped)

    body_text = " ".join(p for p in body_parts if p)
    if not body_text:
        return ""

    # Extract first sentence
    for sep in (".", "!", "?"):
        idx = body_text.find(sep)
        if idx != -1:
            sentence = body_text[: idx + 1].strip()
            return sentence[:120]

    return body_text[:120]


def _find_connecting_edge(fiber: "Fiber", next_fact_id: str) -> "Optional[CausalEdge]":
    """Find highest-confidence edge in fiber.paths where target_id == next_fact_id."""
    best: Optional[CausalEdge] = None
    best_conf = -1.0

    for path in fiber.paths:
        for edge in path.edges:
            if edge.target_id == next_fact_id and edge.confidence > best_conf:
                best = edge
                best_conf = edge.confidence

    return best


def format_narrative(result: "QueryResult", query: str = "") -> str:
    """
    Convert a QueryResult into a human-readable prose causal timeline.
    Returns a multi-line string.
    """
    # Filter and sort fibers
    fibers = result.bundle.fibers
    valid_fibers = [
        fiber
        for fid, fiber in fibers.items()
        if fiber.fact is not None and fid != "__deep_instability__"
    ]

    if not valid_fibers:
        return "No causal chain found for this query."

    # Sort by valid_from ascending
    valid_fibers.sort(key=lambda f: f.fact.valid_from)

    stability = result.stability
    status_label = stability.status.upper()
    score_str = f"{stability.score:.2f}"
    anchor_count = len(result.anchors)
    fact_count = len(valid_fibers)

    lines = []
    lines.append(_WIDE)
    lines.append(f" CAUSAL TIMELINE  •  stability: {status_label} ({score_str})")
    lines.append(_WIDE)

    if query:
        lines.append(f" Query: \"{query}\"")

    lines.append(f" Chain: {fact_count} facts  •  {anchor_count} anchors")
    lines.append(_THIN)

    for i, fiber in enumerate(valid_fibers):
        fact = fiber.fact
        idx = i + 1

        # Date string
        if fact.valid_from.year <= 1971:
            date_str = "(unknown)"
        else:
            date_str = fact.valid_from.strftime("%Y-%m-%d")

        # Derive a tag from source
        source_upper = (fact.source or "note").upper()
        tag = source_upper if source_upper in ("DECISION", "NOTE", "RECEIPT", "IMPORT", "INFERENCE", "AGENT", "USER") else "NOTE"

        title = _extract_title(fact.content)
        body = _extract_body(fact.content)

        lines.append(f"  {idx}.  {date_str}   [{tag}]  {title}")
        if body:
            lines.append(f"               {body}")

        # Edge arrow to next fact (if not last)
        if i < len(valid_fibers) - 1:
            next_fact_id = valid_fibers[i + 1].fact.id
            edge = _find_connecting_edge(fiber, next_fact_id)
            if edge is not None:
                edge_label = edge.edge_type.value
                edge_conf = f"{edge.confidence:.2f}"
                lines.append(f"      ↓ {edge_label} ({edge_conf})")
            else:
                lines.append(f"      ↓ ──")

    lines.append(_THIN)

    if result.escape_triggered:
        lines.append(" ⚠  Escape mechanism triggered — contradictions surfaced")
        lines.append(_WIDE)

    return "\n".join(lines)
