from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Iterable, List, Optional, Tuple


class TemporalStatus(str, Enum):
    EXACT = "EXACT"
    APPROXIMATE = "APPROXIMATE"
    RELATIVE = "RELATIVE"
    VERSIONED = "VERSIONED"
    INFERRED = "INFERRED"
    UNKNOWN = "UNKNOWN"


class TemporalPrecision(str, Enum):
    SECOND = "SECOND"
    DAY = "DAY"
    MONTH = "MONTH"
    YEAR = "YEAR"
    VERSION = "VERSION"
    ORDER_ONLY = "ORDER_ONLY"
    UNKNOWN = "UNKNOWN"


class TemporalSource(str, Enum):
    METADATA = "METADATA"
    CONTENT = "CONTENT"
    CAUSAL_INFERENCE = "CAUSAL_INFERENCE"
    VERSION_ORDER = "VERSION_ORDER"
    USER_ASSERTION = "USER_ASSERTION"
    DEFAULT_NOW = "DEFAULT_NOW"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class TemporalConstraint:
    """A partial-order temporal relation usable when exact timestamps are absent."""

    subject_id: str
    relation: str  # BEFORE | AFTER | DURING | SUPERSEDES | SAME_PERIOD_AS
    object_id: str
    confidence: float = 0.5
    source: TemporalSource = TemporalSource.UNKNOWN
    note: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "subject_id": self.subject_id,
            "relation": self.relation,
            "object_id": self.object_id,
            "confidence": self.confidence,
            "source": self.source.value,
            "note": self.note,
        }


@dataclass
class TemporalEvidence:
    """
    Timestamp-generalised temporal evidence.

    TheHypoKosh should not require a perfect timestamp. It should accept exact
    dates, approximate dates, version order, causal/relative order, and unknown
    time while preserving confidence and provenance.
    """

    status: TemporalStatus
    precision: TemporalPrecision = TemporalPrecision.UNKNOWN
    confidence: float = 0.0
    source: TemporalSource = TemporalSource.UNKNOWN
    time_value: Optional[datetime] = None
    start: Optional[datetime] = None
    end: Optional[datetime] = None
    version: Optional[str] = None
    constraints: List[TemporalConstraint] = field(default_factory=list)
    note: str = ""

    def usable_for_ordering(self) -> bool:
        return self.status in {
            TemporalStatus.EXACT,
            TemporalStatus.APPROXIMATE,
            TemporalStatus.RELATIVE,
            TemporalStatus.VERSIONED,
            TemporalStatus.INFERRED,
        } and self.confidence > 0.0

    def exact_timestamp_available(self) -> bool:
        return self.status == TemporalStatus.EXACT and self.time_value is not None

    def should_abstain_for_time_sensitive_query(self) -> bool:
        return self.status == TemporalStatus.UNKNOWN or self.confidence < 0.2

    def to_dict(self) -> Dict[str, Any]:
        def dt(x: Optional[datetime]) -> Optional[str]:
            return x.isoformat() if x else None

        return {
            "status": self.status.value,
            "precision": self.precision.value,
            "confidence": self.confidence,
            "source": self.source.value,
            "time_value": dt(self.time_value),
            "start": dt(self.start),
            "end": dt(self.end),
            "version": self.version,
            "constraints": [c.to_dict() for c in self.constraints],
            "note": self.note,
        }


@dataclass
class TemporalAuditResult:
    total_facts: int
    exact: int
    approximate: int
    relative: int
    versioned: int
    inferred: int
    unknown: int
    time_dependency_score: float
    risk_flags: List[str]
    recommendations: List[str]

    def to_markdown(self) -> str:
        lines = [
            "# Temporal Evidence Audit",
            "",
            f"Total facts inspected: {self.total_facts}",
            "",
            "| Temporal evidence type | Count |",
            "|---|---:|",
            f"| Exact | {self.exact} |",
            f"| Approximate | {self.approximate} |",
            f"| Relative/order-only | {self.relative} |",
            f"| Versioned | {self.versioned} |",
            f"| Inferred | {self.inferred} |",
            f"| Unknown | {self.unknown} |",
            "",
            f"Time dependency score: **{self.time_dependency_score:.3f}**",
            "",
            "## Risk flags",
        ]
        lines.extend([f"- {x}" for x in self.risk_flags] or ["- None"])
        lines.append("")
        lines.append("## Recommendations")
        lines.extend([f"- {x}" for x in self.recommendations] or ["- None"])
        return "\n".join(lines) + "\n"


class TemporalEvidenceEngine:
    """Infer temporal evidence quality from content, metadata, versions, and edges."""

    # deliberately conservative. This is not a full NLP temporal parser.
    _date_patterns = [
        re.compile(r"\b(20\d{2})-(\d{2})-(\d{2})(?:[T\s](\d{2}:\d{2}(?::\d{2})?)Z?)?\b"),
        re.compile(r"\b(\d{1,2})\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)[a-z]*\s+(20\d{2})\b", re.I),
        re.compile(r"\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)[a-z]*\s+(20\d{2})\b", re.I),
        re.compile(r"\b(20\d{2})\b"),
    ]
    _relative_markers = re.compile(r"\b(after|before|during|then|later|earlier|subsequently|prior to|following|rollback|superseded|deprecated)\b", re.I)
    _version_marker = re.compile(r"\b(?:v|version)\s?(\d+(?:\.\d+){0,3})\b|\b(RFC|draft|approved|deprecated|superseded)\b", re.I)

    def infer(
        self,
        content: str,
        *,
        fact_id: str = "",
        metadata: Optional[Dict[str, Any]] = None,
        version: Optional[str] = None,
        constraints: Optional[List[TemporalConstraint]] = None,
    ) -> TemporalEvidence:
        metadata = metadata or {}
        constraints = constraints or []
        content = content or ""

        meta_dt = self._metadata_datetime(metadata)
        if meta_dt is not None:
            return TemporalEvidence(
                status=TemporalStatus.EXACT,
                precision=TemporalPrecision.SECOND,
                confidence=0.75,
                source=TemporalSource.METADATA,
                time_value=meta_dt,
                start=meta_dt,
                end=None,
                version=version,
                constraints=constraints,
                note="Exact metadata timestamp found. Treat as metadata time, not automatically truth time.",
            )

        content_dt, precision = self._content_datetime(content)
        if content_dt is not None:
            return TemporalEvidence(
                status=TemporalStatus.EXACT if precision in {TemporalPrecision.SECOND, TemporalPrecision.DAY} else TemporalStatus.APPROXIMATE,
                precision=precision,
                confidence=0.7 if precision in {TemporalPrecision.SECOND, TemporalPrecision.DAY} else 0.55,
                source=TemporalSource.CONTENT,
                time_value=content_dt,
                start=content_dt,
                end=None,
                version=version,
                constraints=constraints,
                note="Date-like expression found in content.",
            )

        version_match = version or self._content_version(content)
        if version_match:
            return TemporalEvidence(
                status=TemporalStatus.VERSIONED,
                precision=TemporalPrecision.VERSION,
                confidence=0.6,
                source=TemporalSource.VERSION_ORDER,
                version=version_match,
                constraints=constraints,
                note="Version/order evidence found without exact date.",
            )

        if constraints or self._relative_markers.search(content):
            rel_constraints = list(constraints)
            if not rel_constraints and fact_id:
                rel_constraints.append(TemporalConstraint(
                    subject_id=fact_id,
                    relation="ORDER_ONLY",
                    object_id="unknown_reference",
                    confidence=0.35,
                    source=TemporalSource.CONTENT,
                    note="Relative temporal language detected but reference is unresolved.",
                ))
            return TemporalEvidence(
                status=TemporalStatus.RELATIVE,
                precision=TemporalPrecision.ORDER_ONLY,
                confidence=0.45 if rel_constraints else 0.3,
                source=TemporalSource.CONTENT,
                constraints=rel_constraints,
                note="Relative/order-only temporal evidence found.",
            )

        return TemporalEvidence(
            status=TemporalStatus.UNKNOWN,
            precision=TemporalPrecision.UNKNOWN,
            confidence=0.0,
            source=TemporalSource.UNKNOWN,
            note="No usable temporal evidence detected.",
        )

    def infer_constraints_from_edges(self, dag: Any) -> List[TemporalConstraint]:
        constraints: List[TemporalConstraint] = []
        for edge in getattr(dag, "iter_edges", lambda: [])():
            if str(getattr(edge, "edge_type", "")).endswith("CAUSES") or str(getattr(edge, "edge_type", "")).endswith("ENABLES"):
                constraints.append(TemporalConstraint(
                    subject_id=edge.source_id,
                    relation="BEFORE",
                    object_id=edge.target_id,
                    confidence=min(0.9, float(getattr(edge, "confidence", 0.5))),
                    source=TemporalSource.CAUSAL_INFERENCE,
                    note=f"Causal/enabling edge implies partial temporal order via {edge.id}.",
                ))
            if str(getattr(edge, "edge_type", "")).endswith("SUPERSEDES"):
                constraints.append(TemporalConstraint(
                    subject_id=edge.source_id,
                    relation="SUPERSEDES",
                    object_id=edge.target_id,
                    confidence=min(0.95, float(getattr(edge, "confidence", 0.5))),
                    source=TemporalSource.CAUSAL_INFERENCE,
                    note=f"Supersession edge implies newer truth overrides older truth via {edge.id}.",
                ))
        return constraints

    def audit_dag(self, dag: Any) -> TemporalAuditResult:
        counts = {status: 0 for status in TemporalStatus}
        total = 0
        # Use existing exact datetime fields as evidence, but lower confidence if all fields collapse to same instant.
        for fact in getattr(dag, "nodes", {}).values():
            total += 1
            if getattr(fact, "valid_from", None) is not None:
                if fact.valid_from == getattr(fact, "ingested_at", None) == getattr(fact, "documented_at", None):
                    # This is a common fallback smell: everything is set to ingestion time.
                    ev = self.infer(fact.content, fact_id=fact.id, metadata={})
                    if ev.status == TemporalStatus.UNKNOWN:
                        counts[TemporalStatus.UNKNOWN] += 1
                    else:
                        counts[ev.status] += 1
                else:
                    counts[TemporalStatus.EXACT] += 1
            else:
                counts[self.infer(fact.content, fact_id=fact.id).status] += 1

        exact = counts[TemporalStatus.EXACT]
        approximate = counts[TemporalStatus.APPROXIMATE]
        relative = counts[TemporalStatus.RELATIVE]
        versioned = counts[TemporalStatus.VERSIONED]
        inferred = counts[TemporalStatus.INFERRED]
        unknown = counts[TemporalStatus.UNKNOWN]
        usable = exact + approximate * 0.75 + relative * 0.5 + versioned * 0.5 + inferred * 0.4
        score = usable / total if total else 0.0
        risk_flags: List[str] = []
        recommendations: List[str] = []
        if total and unknown / total > 0.3:
            risk_flags.append("More than 30% of facts lack usable temporal evidence.")
            recommendations.append("Extract metadata timestamps, version order, or relative constraints before time-sensitive reasoning.")
        if exact and exact == total:
            recommendations.append("Check whether exact timestamps are real truth-time values or fallback ingestion times.")
        if relative or versioned:
            recommendations.append("Use temporal-constraint reasoning; do not force relative/versioned facts into fake exact timestamps.")
        if not total:
            risk_flags.append("No facts available for temporal audit.")
        return TemporalAuditResult(
            total_facts=total,
            exact=exact,
            approximate=approximate,
            relative=relative,
            versioned=versioned,
            inferred=inferred,
            unknown=unknown,
            time_dependency_score=score,
            risk_flags=risk_flags,
            recommendations=recommendations,
        )

    def _metadata_datetime(self, metadata: Dict[str, Any]) -> Optional[datetime]:
        for key in ("observed_at", "created_at", "modified_at", "published_at", "sent_at", "commit_at"):
            value = metadata.get(key)
            if not value:
                continue
            parsed = self._parse_datetime(value)
            if parsed is not None:
                return parsed
        return None

    def _content_datetime(self, content: str) -> Tuple[Optional[datetime], TemporalPrecision]:
        # ISO/day precision
        m = self._date_patterns[0].search(content)
        if m:
            date_part = f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
            time_part = m.group(4) or "00:00:00"
            if len(time_part.split(":")) == 2:
                time_part += ":00"
            return self._parse_datetime(f"{date_part}T{time_part}+00:00"), TemporalPrecision.SECOND if m.group(4) else TemporalPrecision.DAY
        # 12 May 2026
        m = self._date_patterns[1].search(content)
        if m:
            month = self._month(m.group(2))
            if month:
                return datetime(int(m.group(3)), month, int(m.group(1)), tzinfo=timezone.utc), TemporalPrecision.DAY
        # May 2026
        m = self._date_patterns[2].search(content)
        if m:
            month = self._month(m.group(1))
            if month:
                return datetime(int(m.group(2)), month, 1, tzinfo=timezone.utc), TemporalPrecision.MONTH
        # year only, low precision
        m = self._date_patterns[3].search(content)
        if m:
            return datetime(int(m.group(1)), 1, 1, tzinfo=timezone.utc), TemporalPrecision.YEAR
        return None, TemporalPrecision.UNKNOWN

    def _content_version(self, content: str) -> Optional[str]:
        m = self._version_marker.search(content or "")
        if not m:
            return None
        if m.group(1):
            return f"v{m.group(1)}"
        return m.group(2).lower() if m.group(2) else None

    def _parse_datetime(self, value: Any) -> Optional[datetime]:
        if isinstance(value, datetime):
            return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
        if isinstance(value, (int, float)):
            return datetime.fromtimestamp(float(value), tz=timezone.utc)
        if not isinstance(value, str):
            return None
        try:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
            return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        except Exception:
            return None

    def _month(self, month: str) -> Optional[int]:
        key = month[:3].lower()
        months = {"jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6, "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12}
        return months.get(key)
