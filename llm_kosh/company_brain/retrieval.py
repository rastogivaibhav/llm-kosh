"""Permission-first hybrid retrieval over canonical company memory."""

from __future__ import annotations

import math
import re
from collections import Counter
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Sequence

from .models import Principal
from .store import CompanyBrainStore


_TOKEN = re.compile(r"[a-z0-9][a-z0-9_\-]+")
_STOP = {
    "the", "a", "an", "and", "or", "of", "to", "in", "for", "on", "with",
    "is", "are", "was", "were", "be", "this", "that", "it", "as", "at",
    "by", "from", "what", "why", "how", "when", "who", "which",
}


def _tokens(text: str) -> List[str]:
    return [token for token in _TOKEN.findall((text or "").lower()) if token not in _STOP]


def _cosine(query: Sequence[str], document: Sequence[str]) -> float:
    if not query or not document:
        return 0.0
    q = Counter(query)
    d = Counter(document)
    common = q.keys() & d.keys()
    dot = sum(q[token] * d[token] for token in common)
    nq = math.sqrt(sum(value * value for value in q.values()))
    nd = math.sqrt(sum(value * value for value in d.values()))
    return dot / (nq * nd) if nq and nd else 0.0


def _parse_time(value: str) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def search_memories(
    store: CompanyBrainStore,
    query: str,
    principal: Principal,
    *,
    project_id: str = "",
    memory_types: Optional[Sequence[str]] = None,
    as_of: str = "",
    limit: int = 10,
    include_candidates: bool = False,
    include_stale: bool = True,
) -> List[Dict[str, Any]]:
    """Search only memories authorized before ranking.

    The local implementation combines FTS5 BM25 and a deterministic token-space
    similarity signal. A dense embedding projection can replace the second
    signal without changing the canonical store or result contract.
    """
    accessible = store.list_accessible_memories(
        principal,
        project_id=project_id,
        memory_types=memory_types,
        as_of=as_of,
        include_candidates=include_candidates,
        include_stale=include_stale,
    )
    if not accessible:
        return []

    # A memory is only retrievable when the caller can also see at least one
    # of its supporting evidence records. This prevents citation metadata (or
    # unsupported claims) crossing a stricter evidence boundary.
    authorized_evidence = store.evidence_for_memories(
        [item["memory_id"] for item in accessible], principal
    )
    availability: Dict[str, str] = {}
    for references in authorized_evidence.values():
        for reference in references:
            evidence_id = reference["evidence_id"]
            if evidence_id not in availability:
                try:
                    availability[evidence_id] = store.inspect_evidence(
                        evidence_id, principal, strong=False
                    )["availability"]["status"]
                except (KeyError, PermissionError, OSError):
                    availability[evidence_id] = "unavailable"
    accessible = [
        item for item in accessible
        if any(
            availability.get(reference["evidence_id"]) == "available"
            for reference in authorized_evidence.get(item["memory_id"], [])
        )
    ]
    if not accessible:
        return []

    allowed_ids = [item["memory_id"] for item in accessible]
    fts = store.fts_ranks(query, allowed_ids)
    query_tokens = _tokens(query)
    now = datetime.now(timezone.utc)
    results: List[Dict[str, Any]] = []

    for item in accessible:
        document = " ".join((item["title"], item["title"], item["statement"], item["rationale"]))
        semantic = _cosine(query_tokens, _tokens(document)) if query_tokens else 0.0
        raw_fts = fts.get(item["memory_id"])
        lexical = 1.0 / (1.0 + abs(raw_fts)) if raw_fts is not None else 0.0
        project_score = 1.0 if project_id and item["project_id"] == project_id else (0.5 if item["project_id"] else 0.0)
        confidence = float(item["confidence"])
        importance = float(item["importance"])
        lifecycle_authority = {
            "active": 1.0,
            "verified": 0.95,
            "reviewed": 0.70,
            "candidate": 0.35,
            "stale": 0.25,
        }.get(item["lifecycle"], 0.0)

        observed = _parse_time(item["observed_at"])
        if observed:
            days = max(0.0, (now - observed.astimezone(timezone.utc)).total_seconds() / 86400.0)
            freshness = math.exp(-days / 365.0)
        else:
            freshness = 0.3

        score = (
            0.30 * semantic
            + 0.20 * lexical
            + 0.12 * project_score
            + 0.12 * confidence
            + 0.10 * importance
            + 0.09 * lifecycle_authority
            + 0.07 * freshness
        )
        if item["lifecycle"] == "stale":
            score -= 0.15
        if query_tokens and not semantic and raw_fts is None:
            score *= 0.25

        enriched = dict(item)
        enriched["score"] = round(max(0.0, score), 6)
        enriched["score_breakdown"] = {
            "semantic": round(semantic, 6),
            "lexical": round(lexical, 6),
            "project": project_score,
            "confidence": confidence,
            "importance": importance,
            "authority": lifecycle_authority,
            "freshness": round(freshness, 6),
        }
        enriched["why_matched"] = [
            name for name, value in (
                ("semantic", semantic), ("lexical", lexical),
                ("project", project_score), ("importance", importance),
            ) if value >= 0.5
        ]
        results.append(enriched)

    results.sort(key=lambda item: (item["score"], item["confidence"], item["updated_at"]), reverse=True)
    return results[:max(1, limit)]


def search_evidence(
    store: CompanyBrainStore,
    query: str,
    principal: Principal,
    *,
    limit: int = 8,
    max_text: int = 8_000,
) -> List[Dict[str, Any]]:
    """Search registered evidence directly without creating a classic copy.

    This is intentionally separate from memory retrieval. Company Brain can
    cite a newly watched source before a reviewer promotes an extracted claim
    into governed memory; the source bytes remain at their original path.
    """
    query_tokens = _tokens(query)
    results: List[Dict[str, Any]] = []
    for row in store.list_accessible_evidence(principal):
        evidence_id = row["evidence_id"]
        try:
            inspection = store.inspect_evidence(
                evidence_id,
                principal,
                strong=True,
                include_preview=True,
                max_text=max_text,
            )
        except (KeyError, PermissionError, OSError):
            continue
        if inspection.get("availability", {}).get("status") != "available":
            continue

        source_label = " ".join((row.get("source_locator", ""), row.get("artifact_type", "")))
        segments = (inspection.get("inspection") or {}).get("segments") or []
        candidates = segments or [{"text": source_label, "native_locator": {}}]
        best = None
        for segment in candidates:
            text = str(segment.get("text", ""))
            document_tokens = _tokens(" ".join((source_label, text)))
            semantic = _cosine(query_tokens, document_tokens) if query_tokens else 0.0
            overlap = (
                len(set(query_tokens) & set(document_tokens)) / len(set(query_tokens))
                if query_tokens else 0.0
            )
            score = 0.70 * semantic + 0.30 * overlap
            candidate = (score, text, segment.get("native_locator") or {})
            if best is None or candidate[0] > best[0]:
                best = candidate
        assert best is not None
        score, quote, native_locator = best
        if query_tokens and score <= 0:
            continue
        results.append({
            "evidence_id": evidence_id,
            "source_locator": row["source_locator"],
            "source_type": row["source_type"],
            "artifact_type": row["artifact_type"],
            "mime_type": row["mime_type"],
            "storage_mode": row["storage_mode"],
            "content_hash": row["content_hash"],
            "native_locator": native_locator,
            "quote": quote[:max_text],
            "availability": inspection["availability"],
            "score": round(score, 6),
            "delivery": "reference",
        })

    results.sort(key=lambda item: (item["score"], item["evidence_id"]), reverse=True)
    return results[:max(1, limit)]
