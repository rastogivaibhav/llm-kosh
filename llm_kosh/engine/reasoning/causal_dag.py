from __future__ import annotations

import bisect
import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set


class EdgeType(str, Enum):
    ENABLES = "ENABLES"
    CAUSES = "CAUSES"
    CONTRADICTS = "CONTRADICTS"
    SUPERSEDES = "SUPERSEDES"
    INFERS = "INFERS"
    ANALOGY = "ANALOGY"
    MAPS_TO = "MAPS_TO"
    INVERTS = "INVERTS"
    STRUCTURALLY_SIMILAR = "STRUCTURALLY_SIMILAR"
    CONTRASTS = "CONTRASTS"


class EdgeOrigin(str, Enum):
    OBSERVED = "OBSERVED"
    DISCOVERED = "DISCOVERED"
    INFERRED = "INFERRED"
    REINFORCED = "REINFORCED"
    HYPOTHETICAL = "HYPOTHETICAL"


class EdgeRole(str, Enum):
    MECHANISTIC = "MECHANISTIC"
    COMPRESSED = "COMPRESSED"
    ANALOGICAL = "ANALOGICAL"
    PREDICTIVE = "PREDICTIVE"
    CAUSAL = "CAUSAL"


class ReasoningMode(str, Enum):
    EMPIRICAL = "EMPIRICAL"
    THEORETICAL = "THEORETICAL"
    BALANCED = "BALANCED"


@dataclass
class EvidenceRef:
    source_id: str
    span: Optional[str] = None
    observed_at: Optional[datetime] = None

    def to_dict(self) -> dict:
        return {
            "source_id": self.source_id,
            "span": self.span,
            "observed_at": self.observed_at.isoformat() if self.observed_at else None,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "EvidenceRef":
        observed_at = data.get("observed_at")
        return cls(
            source_id=str(data.get("source_id", "")),
            span=data.get("span"),
            observed_at=_parse_dt(observed_at) if observed_at else None,
        )


@dataclass
class ReinforcementState:
    count: int = 0
    last_used_at: Optional[datetime] = None
    salience_boost: float = 0.0

    def to_dict(self) -> dict:
        return {
            "count": self.count,
            "last_used_at": self.last_used_at.isoformat() if self.last_used_at else None,
            "salience_boost": self.salience_boost,
        }

    @classmethod
    def from_dict(cls, data: Optional[dict]) -> Optional["ReinforcementState"]:
        if not data:
            return None
        last = data.get("last_used_at")
        return cls(
            count=int(data.get("count", 0)),
            last_used_at=_parse_dt(last) if last else None,
            salience_boost=float(data.get("salience_boost", 0.0)),
        )


@dataclass
class EdgeProvenance:
    origin: EdgeOrigin = EdgeOrigin.OBSERVED
    role: EdgeRole = EdgeRole.MECHANISTIC
    evidence_refs: List[EvidenceRef] = field(default_factory=list)
    derived_from: List[str] = field(default_factory=list)
    reinforcement: Optional[ReinforcementState] = None
    promotion_status: str = "unpromoted"

    @staticmethod
    def default() -> "EdgeProvenance":
        return EdgeProvenance()

    def to_dict(self) -> dict:
        return {
            "origin": self.origin.value,
            "role": self.role.value,
            "evidence_refs": [e.to_dict() for e in self.evidence_refs],
            "derived_from": list(self.derived_from),
            "reinforcement": self.reinforcement.to_dict() if self.reinforcement else None,
            "promotion_status": self.promotion_status,
        }

    @classmethod
    def from_dict(cls, data: Optional[dict]) -> "EdgeProvenance":
        if not data:
            return cls.default()
        return cls(
            origin=EdgeOrigin(data.get("origin", EdgeOrigin.OBSERVED.value)),
            role=EdgeRole(data.get("role", EdgeRole.MECHANISTIC.value)),
            evidence_refs=[EvidenceRef.from_dict(e) for e in data.get("evidence_refs", [])],
            derived_from=[str(x) for x in data.get("derived_from", [])],
            reinforcement=ReinforcementState.from_dict(data.get("reinforcement")),
            promotion_status=str(data.get("promotion_status", "unpromoted")),
        )


@dataclass
class TemporalFact:
    id: str
    content: str
    ingested_at: datetime
    documented_at: datetime
    valid_from: datetime
    valid_until: Optional[datetime]
    confidence: float
    resonance_profile: dict
    source: str  # "receipt" | "agent" | "user" | "inference"


@dataclass
class CausalEdge:
    id: str
    source_id: str
    target_id: str
    edge_type: EdgeType
    confidence: float
    valid_from: datetime
    valid_until: Optional[datetime]
    established_by: str
    provenance: EdgeProvenance = field(default_factory=EdgeProvenance.default)


@dataclass
class HyperEdge:
    id: str
    source_ids: Set[str]
    target_id: str
    edge_type: EdgeType
    confidence: float
    valid_from: datetime
    valid_until: Optional[datetime]
    provenance: EdgeProvenance = field(default_factory=EdgeProvenance.default)


@dataclass
class TrajectoryState:
    session_id: str
    steps: List[dict] = field(default_factory=list)
    stability: float = 1.0
    escape_count: int = 0


class IntervalTree:
    """Pure-Python bisect-based interval index for fast valid-at-T queries."""

    def __init__(self) -> None:
        self._starts: List[tuple] = []          # sorted (valid_from_ts, fact_id)
        self._entries: Dict[str, tuple] = {}    # fact_id -> (valid_from_ts, valid_until_ts|None)

    def add(self, fact_id: str, valid_from: float, valid_until: Optional[float]) -> None:
        self._entries[fact_id] = (valid_from, valid_until)
        bisect.insort(self._starts, (valid_from, fact_id))

    def remove(self, fact_id: str) -> None:
        if fact_id not in self._entries:
            return
        vf, _ = self._entries.pop(fact_id)
        idx = bisect.bisect_left(self._starts, (vf, fact_id))
        if idx < len(self._starts) and self._starts[idx] == (vf, fact_id):
            self._starts.pop(idx)

    def query_valid_at(self, t: float) -> List[str]:
        """Return all fact IDs whose validity window contains t."""
        idx = bisect.bisect_right(self._starts, (t, "\xff"))
        result = []
        for _, fid in self._starts[:idx]:
            _, valid_until = self._entries[fid]
            if valid_until is None or valid_until > t:
                result.append(fid)
        return result


def _ts(dt_obj: Optional[datetime]) -> Optional[float]:
    """Convert datetime to Unix timestamp, or None."""
    return dt_obj.timestamp() if dt_obj is not None else None


def _parse_dt(s: str) -> datetime:
    return datetime.fromisoformat(s)


class CausalDAG:
    """
    Temporal Causal Hypergraph manager.
    Owns the reasoning event log. All other components read through this.
    """

    LOG_DIR = "reasoning"
    LOG_FILE = "reasoning/events.jsonl"
    SNAPSHOT_FILE = "reasoning/snapshot.json"

    def __init__(self, root: Path) -> None:
        self.root = root
        self.nodes: Dict[str, TemporalFact] = {}
        self.edges: Dict[str, List[CausalEdge]] = {}   # source_id -> edges
        self.hyperedges: List[HyperEdge] = []
        self.interval_tree = IntervalTree()
        self._ensure_dirs()
        if not self._try_load_snapshot():
            self._load_from_log()

    # ------------------------------------------------------------------ dirs

    def _ensure_dirs(self) -> None:
        (self.root / self.LOG_DIR).mkdir(parents=True, exist_ok=True)

    @property
    def _log_path(self) -> Path:
        return self.root / self.LOG_FILE

    # ------------------------------------------------------------------ log

    def _append_event(self, event: str, payload: dict) -> None:
        entry = json.dumps({"event": event, "payload": payload}, default=str)
        with self._log_path.open("a", encoding="utf-8") as f:
            f.write(entry + "\n")

    # ------------------------------------------------------------------ load

    def _load_from_log(self) -> None:
        if not self._log_path.exists():
            return
        for line in self._log_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
                self._apply_event(entry["event"], entry["payload"])
            except Exception:
                pass

    def save_snapshot(self) -> None:
        """Serialize hot layer to snapshot.json for faster startup."""
        import json as _json

        def _dt_str(dt):
            return dt.isoformat() if dt is not None else None

        nodes_out = {}
        for fid, fact in self.nodes.items():
            nodes_out[fid] = {
                "id": fact.id, "content": fact.content,
                "ingested_at": _dt_str(fact.ingested_at),
                "documented_at": _dt_str(fact.documented_at),
                "valid_from": _dt_str(fact.valid_from),
                "valid_until": _dt_str(fact.valid_until),
                "confidence": fact.confidence,
                "resonance_profile": fact.resonance_profile,
                "source": fact.source,
            }

        edges_out = {}
        for src_id, edge_list in self.edges.items():
            edges_out[src_id] = [
                {
                    "id": e.id, "source_id": e.source_id, "target_id": e.target_id,
                    "edge_type": e.edge_type.value, "confidence": e.confidence,
                    "valid_from": _dt_str(e.valid_from),
                    "valid_until": _dt_str(e.valid_until),
                    "established_by": e.established_by,
                    "provenance": e.provenance.to_dict(),
                }
                for e in edge_list
            ]

        hyperedges_out = [
            {
                "id": he.id, "source_ids": list(he.source_ids), "target_id": he.target_id,
                "edge_type": he.edge_type.value, "confidence": he.confidence,
                "valid_from": _dt_str(he.valid_from),
                "valid_until": _dt_str(he.valid_until),
                "provenance": he.provenance.to_dict(),
            }
            for he in self.hyperedges
        ]

        snap = {"nodes": nodes_out, "edges": edges_out, "hyperedges": hyperedges_out}
        snap_path = self.root / self.SNAPSHOT_FILE
        snap_path.write_text(
            _json.dumps(snap, ensure_ascii=False), encoding="utf-8"
        )

    def _try_load_snapshot(self) -> bool:
        """Attempt to load hot layer from snapshot. Returns True on success."""
        snap_path = self.root / self.SNAPSHOT_FILE
        if not snap_path.exists():
            return False
        try:
            import json as _json
            snap = _json.loads(snap_path.read_text(encoding="utf-8"))
            for fid, payload in snap.get("nodes", {}).items():
                fact = TemporalFact(
                    id=payload["id"], content=payload["content"],
                    ingested_at=_parse_dt(payload["ingested_at"]),
                    documented_at=_parse_dt(payload["documented_at"]),
                    valid_from=_parse_dt(payload["valid_from"]),
                    valid_until=_parse_dt(payload["valid_until"]) if payload.get("valid_until") else None,
                    confidence=float(payload["confidence"]),
                    resonance_profile=payload.get("resonance_profile", {}),
                    source=payload.get("source", "user"),
                )
                self._register_fact(fact)
            for src_id, edge_list in snap.get("edges", {}).items():
                for ep in edge_list:
                    edge = CausalEdge(
                        id=ep["id"], source_id=ep["source_id"], target_id=ep["target_id"],
                        edge_type=EdgeType(ep["edge_type"]), confidence=float(ep["confidence"]),
                        valid_from=_parse_dt(ep["valid_from"]),
                        valid_until=_parse_dt(ep["valid_until"]) if ep.get("valid_until") else None,
                        established_by=ep.get("established_by", ""),
                        provenance=EdgeProvenance.from_dict(ep.get("provenance")),
                    )
                    self.edges.setdefault(src_id, []).append(edge)
            for hp in snap.get("hyperedges", []):
                he = HyperEdge(
                    id=hp["id"], source_ids=set(hp.get("source_ids", [])), target_id=hp["target_id"],
                    edge_type=EdgeType(hp["edge_type"]), confidence=float(hp["confidence"]),
                    valid_from=_parse_dt(hp["valid_from"]),
                    valid_until=_parse_dt(hp["valid_until"]) if hp.get("valid_until") else None,
                    provenance=EdgeProvenance.from_dict(hp.get("provenance")),
                )
                self.hyperedges.append(he)
            return True
        except Exception:
            # Corrupt snapshot — fall through to log replay
            self.nodes.clear()
            self.edges.clear()
            self.hyperedges.clear()
            self.interval_tree = IntervalTree()
            return False

    def _apply_event(self, event: str, payload: dict) -> None:
        if event == "fact.added":
            fact = TemporalFact(
                id=payload["id"],
                content=payload["content"],
                ingested_at=_parse_dt(payload["ingested_at"]),
                documented_at=_parse_dt(payload["documented_at"]),
                valid_from=_parse_dt(payload["valid_from"]),
                valid_until=_parse_dt(payload["valid_until"]) if payload.get("valid_until") else None,
                confidence=float(payload["confidence"]),
                resonance_profile=payload.get("resonance_profile", {}),
                source=payload.get("source", "user"),
            )
            self._register_fact(fact)
        elif event == "causal_edge.added":
            edge = CausalEdge(
                id=payload["id"],
                source_id=payload["source_id"],
                target_id=payload["target_id"],
                edge_type=EdgeType(payload["edge_type"]),
                confidence=float(payload["confidence"]),
                valid_from=_parse_dt(payload["valid_from"]),
                valid_until=_parse_dt(payload["valid_until"]) if payload.get("valid_until") else None,
                established_by=payload.get("established_by", ""),
                provenance=EdgeProvenance.from_dict(payload.get("provenance")),
            )
            self.edges.setdefault(edge.source_id, []).append(edge)
        elif event == "hyperedge.added":
            he = HyperEdge(
                id=payload["id"],
                source_ids=set(payload["source_ids"]),
                target_id=payload["target_id"],
                edge_type=EdgeType(payload["edge_type"]),
                confidence=float(payload["confidence"]),
                valid_from=_parse_dt(payload["valid_from"]),
                valid_until=_parse_dt(payload["valid_until"]) if payload.get("valid_until") else None,
                provenance=EdgeProvenance.from_dict(payload.get("provenance")),
            )
            self.hyperedges.append(he)
        elif event == "validity.updated":
            fid = payload["fact_id"]
            if fid in self.nodes:
                new_until = _parse_dt(payload["new_valid_until"]) if payload.get("new_valid_until") else None
                old_fact = self.nodes[fid]
                self.interval_tree.remove(fid)
                self.nodes[fid] = TemporalFact(
                    **{**old_fact.__dict__, "valid_until": new_until}
                )
                self.interval_tree.add(fid, _ts(self.nodes[fid].valid_from), _ts(new_until))
        elif event == "edge.provenance.updated":
            edge = self.get_edge(payload.get("edge_id", ""))
            if edge is not None:
                edge.provenance = EdgeProvenance.from_dict(payload.get("provenance"))
                edge.confidence = float(payload.get("confidence", edge.confidence))

    def _register_fact(self, fact: TemporalFact) -> None:
        if fact.id in self.nodes:
            raise ValueError(f"duplicate fact id: {fact.id}")
        self._validate_confidence(fact.confidence)
        self._validate_window(fact.valid_from, fact.valid_until)
        self.nodes[fact.id] = fact
        self.interval_tree.add(fact.id, _ts(fact.valid_from), _ts(fact.valid_until))

    # ------------------------------------------------------------------ validation / provenance helpers

    def _validate_confidence(self, confidence: float) -> None:
        if not 0.0 <= float(confidence) <= 1.0:
            raise ValueError(f"confidence must be in [0, 1], got {confidence}")

    def _validate_window(self, valid_from: datetime, valid_until: Optional[datetime]) -> None:
        if valid_until is not None and valid_until <= valid_from:
            raise ValueError("valid_until must be after valid_from")

    def _validate_fact_exists(self, fact_id: str, label: str = "fact") -> None:
        if fact_id not in self.nodes:
            raise ValueError(f"{label} does not exist: {fact_id}")

    def _edge_provenance_or_default(
        self,
        provenance: Optional[EdgeProvenance],
        edge_type: EdgeType,
        established_by: str,
    ) -> EdgeProvenance:
        if provenance is not None:
            return provenance
        if edge_type in {EdgeType.ANALOGY, EdgeType.MAPS_TO, EdgeType.INVERTS, EdgeType.STRUCTURALLY_SIMILAR, EdgeType.CONTRASTS}:
            return EdgeProvenance(origin=EdgeOrigin.HYPOTHETICAL, role=EdgeRole.ANALOGICAL, promotion_status="speculative")
        if edge_type == EdgeType.INFERS or established_by in {"discourse", "inference", "self_heal"}:
            return EdgeProvenance(origin=EdgeOrigin.INFERRED, role=EdgeRole.COMPRESSED, promotion_status="unpromoted")
        return EdgeProvenance.default()

    def _edge_active(self, edge: CausalEdge, query_time: float) -> bool:
        vf = _ts(edge.valid_from) or 0.0
        vu = _ts(edge.valid_until)
        return vf <= query_time and (vu is None or vu > query_time)

    def _hyperedge_active(self, he: HyperEdge, query_time: float) -> bool:
        vf = _ts(he.valid_from) or 0.0
        vu = _ts(he.valid_until)
        return vf <= query_time and (vu is None or vu > query_time)

    # ------------------------------------------------------------------ write API

    def add_fact(
        self,
        content_or_fact=None,
        ingested_at: Optional[datetime] = None,
        documented_at: Optional[datetime] = None,
        valid_from: Optional[datetime] = None,
        valid_until: Optional[datetime] = None,
        confidence: Optional[float] = None,
        source: Optional[str] = None,
        resonance_profile: Optional[dict] = None,
        **kwargs,
    ) -> str:
        """
        Add a temporal fact to the causal DAG.

        Accepts either:
        1. A TemporalFact object: add_fact(temporal_fact_obj)
        2. Unpacked arguments: add_fact(content, ingested_at, documented_at, ...)

        Args:
            content_or_fact: Either a TemporalFact object or the fact content string
            ingested_at: When the fact was ingested (required if content_or_fact is str)
            documented_at: When the fact was documented (required if content_or_fact is str)
            valid_from: Start of validity window (required if content_or_fact is str)
            valid_until: End of validity window (optional)
            confidence: Confidence score 0-1 (required if content_or_fact is str)
            source: Source of the fact (required if content_or_fact is str)
            resonance_profile: Optional metadata dict

        Returns:
            Fact ID (auto-generated)
        """
        # Compatibility shim: older product/verify code calls
        # add_fact(content=..., ingested_at=..., ...).  The hardened API keeps
        # the positional TemporalFact/string forms but also accepts this clearer
        # keyword style so Kosh Verify, recursive loop, and dataset evaluators
        # share one stable write path.
        if content_or_fact is None and "content" in kwargs:
            content_or_fact = kwargs.pop("content")
        if kwargs:
            raise TypeError(f"unexpected add_fact keyword(s): {sorted(kwargs)}")

        # Handle TemporalFact object form
        if isinstance(content_or_fact, TemporalFact):
            fact = content_or_fact
            fact_id = fact.id if fact.id else "fact." + uuid.uuid4().hex[:12]
            content = fact.content
            ingested_at_val = fact.ingested_at
            documented_at_val = fact.documented_at
            valid_from_val = fact.valid_from
            valid_until_val = fact.valid_until
            confidence_val = fact.confidence
            source_val = fact.source
            resonance_profile_val = fact.resonance_profile or {}
        else:
            # Handle unpacked arguments form
            if any(x is None for x in [ingested_at, documented_at, valid_from, confidence, source]):
                raise ValueError(
                    "When not using TemporalFact object, all arguments "
                    "(content, ingested_at, documented_at, valid_from, confidence, source) are required"
                )
            fact_id = "fact." + uuid.uuid4().hex[:12]
            content = content_or_fact
            ingested_at_val = ingested_at
            documented_at_val = documented_at
            valid_from_val = valid_from
            valid_until_val = valid_until
            confidence_val = confidence
            source_val = source
            resonance_profile_val = resonance_profile or {}

        self._validate_confidence(confidence_val)
        self._validate_window(valid_from_val, valid_until_val)

        fact = TemporalFact(
            id=fact_id,
            content=content,
            ingested_at=ingested_at_val,
            documented_at=documented_at_val,
            valid_from=valid_from_val,
            valid_until=valid_until_val,
            confidence=confidence_val,
            resonance_profile=resonance_profile_val,
            source=source_val,
        )
        self._register_fact(fact)
        self._append_event("fact.added", {
            "id": fact_id,
            "content": content,
            "ingested_at": ingested_at_val.isoformat(),
            "documented_at": documented_at_val.isoformat(),
            "valid_from": valid_from_val.isoformat(),
            "valid_until": valid_until_val.isoformat() if valid_until_val else None,
            "confidence": confidence_val,
            "resonance_profile": resonance_profile_val,
            "source": source_val,
        })

        # Auto-detect causal edges from discourse markers in recent facts
        self._auto_edges_from_discourse(fact_id, content)

        return fact_id

    def _auto_edges_from_discourse(self, new_fact_id: str, new_content: str) -> None:
        """
        Examine the last 10 facts added before new_fact_id and auto-create
        causal edges when discourse markers in new_content suggest ordering.
        Only operates within the last 10 additions to avoid spurious links.
        """
        from llm_kosh.engine.reasoning.discourse import should_auto_create_edge

        # Build ordered list of fact IDs (insertion order preserved in Python 3.7+)
        all_ids = list(self.nodes.keys())
        new_idx = all_ids.index(new_fact_id)
        # Look at up to 10 preceding facts
        preceding = all_ids[max(0, new_idx - 10): new_idx]

        for prev_id in preceding:
            prev_fact = self.nodes.get(prev_id)
            if prev_fact is None:
                continue
            create, edge_type_str, confidence = should_auto_create_edge(
                prev_fact.content, new_content
            )
            if not create:
                continue
            try:
                self.add_edge(
                    source_id=prev_id,
                    target_id=new_fact_id,
                    edge_type=EdgeType(edge_type_str),
                    confidence=confidence,
                    valid_from=prev_fact.valid_from,
                    valid_until=None,
                    established_by="discourse",
                )
            except Exception:
                pass  # silently skip duplicate or invalid edges

    def add_edge(
        self,
        source_id: str,
        target_id: str,
        edge_type: EdgeType,
        confidence: float,
        valid_from: datetime,
        valid_until: Optional[datetime],
        established_by: str,
        provenance: Optional[EdgeProvenance] = None,
    ) -> str:
        self._validate_fact_exists(source_id, "edge source")
        self._validate_fact_exists(target_id, "edge target")
        self._validate_confidence(confidence)
        self._validate_window(valid_from, valid_until)
        edge_id = "edge." + uuid.uuid4().hex[:12]
        prov = self._edge_provenance_or_default(provenance, edge_type, established_by)
        edge = CausalEdge(
            id=edge_id,
            source_id=source_id,
            target_id=target_id,
            edge_type=edge_type,
            confidence=float(confidence),
            valid_from=valid_from,
            valid_until=valid_until,
            established_by=established_by,
            provenance=prov,
        )
        self.edges.setdefault(source_id, []).append(edge)
        self._append_event("causal_edge.added", {
            "id": edge_id,
            "source_id": source_id,
            "target_id": target_id,
            "edge_type": edge_type.value,
            "confidence": float(confidence),
            "valid_from": valid_from.isoformat(),
            "valid_until": valid_until.isoformat() if valid_until else None,
            "established_by": established_by,
            "provenance": prov.to_dict(),
        })
        return edge_id

    def add_hyperedge(
        self,
        source_ids: Set[str],
        target_id: str,
        edge_type: EdgeType,
        confidence: float,
        valid_from: datetime,
        valid_until: Optional[datetime],
        provenance: Optional[EdgeProvenance] = None,
    ) -> str:
        if not source_ids:
            raise ValueError("hyperedge requires at least one source fact")
        for sid in source_ids:
            self._validate_fact_exists(sid, "hyperedge source")
        self._validate_fact_exists(target_id, "hyperedge target")
        self._validate_confidence(confidence)
        self._validate_window(valid_from, valid_until)
        he_id = "he." + uuid.uuid4().hex[:12]
        prov = self._edge_provenance_or_default(provenance, edge_type, "hyperedge")
        he = HyperEdge(
            id=he_id,
            source_ids=set(source_ids),
            target_id=target_id,
            edge_type=edge_type,
            confidence=float(confidence),
            valid_from=valid_from,
            valid_until=valid_until,
            provenance=prov,
        )
        self.hyperedges.append(he)
        self._append_event("hyperedge.added", {
            "id": he_id,
            "source_ids": list(source_ids),
            "target_id": target_id,
            "edge_type": edge_type.value,
            "confidence": float(confidence),
            "valid_from": valid_from.isoformat(),
            "valid_until": valid_until.isoformat() if valid_until else None,
            "provenance": prov.to_dict(),
        })
        return he_id

    # ------------------------------------------------------------------ read API

    def get_fact(self, fact_id: str) -> Optional[TemporalFact]:
        return self.nodes.get(fact_id)

    def get_outgoing_edges(self, fact_id: str, query_time: float) -> List[CausalEdge]:
        """Return binary edges active at query_time from fact_id."""
        return [edge for edge in self.edges.get(fact_id, []) if self._edge_active(edge, query_time)]

    def get_incoming_edges(self, fact_id: str, query_time: float) -> List[CausalEdge]:
        """Get active binary edges pointing TO fact_id."""
        result = []
        for edges in self.edges.values():
            for edge in edges:
                if edge.target_id == fact_id and self._edge_active(edge, query_time):
                    result.append(edge)
        return result

    def get_hyperedge_expansions(
        self, fact_id: str, active_fact_ids: Set[str], query_time: float
    ) -> List[CausalEdge]:
        """
        Return synthetic expansion edges for active hyperedges.

        A hyperedge A ∧ B -> C may only fire when all source facts are
        already active in the current traversal context. The synthetic edge
        lets existing path code preserve the transition while the provenance
        records that this was a joint-causality transition, not a binary claim.
        """
        result: List[CausalEdge] = []
        for he in self.hyperedges:
            if fact_id not in he.source_ids:
                continue
            if he.target_id in active_fact_ids:
                continue
            if not he.source_ids.issubset(active_fact_ids):
                continue
            if not self._hyperedge_active(he, query_time):
                continue
            if he.target_id not in self.nodes:
                continue
            result.append(CausalEdge(
                id=f"{he.id}:joint:{fact_id}",
                source_id=fact_id,
                target_id=he.target_id,
                edge_type=he.edge_type,
                confidence=he.confidence,
                valid_from=he.valid_from,
                valid_until=he.valid_until,
                established_by="hyperedge",
                provenance=EdgeProvenance(
                    origin=he.provenance.origin,
                    role=EdgeRole.CAUSAL if he.edge_type == EdgeType.CAUSES else he.provenance.role,
                    evidence_refs=list(he.provenance.evidence_refs),
                    derived_from=list(he.provenance.derived_from) + [he.id],
                    reinforcement=he.provenance.reinforcement,
                    promotion_status=he.provenance.promotion_status,
                ),
            ))
        return result

    def get_edge(self, edge_id: str) -> Optional[CausalEdge]:
        for edge_list in self.edges.values():
            for edge in edge_list:
                if edge.id == edge_id:
                    return edge
        return None

    def iter_edges(self) -> Iterable[CausalEdge]:
        for edge_list in self.edges.values():
            yield from edge_list

    def reinforce_edge(self, edge_id: str, used_at: Optional[datetime] = None, salience_step: float = 0.05) -> None:
        """Increase salience/reinforcement without silently increasing truth confidence."""
        edge = self.get_edge(edge_id)
        if edge is None:
            raise ValueError(f"edge not found: {edge_id}")
        now = used_at or datetime.now(timezone.utc)
        state = edge.provenance.reinforcement or ReinforcementState()
        state.count += 1
        state.last_used_at = now
        state.salience_boost = min(1.0, state.salience_boost + salience_step)
        edge.provenance.reinforcement = state
        if edge.provenance.origin == EdgeOrigin.INFERRED:
            edge.provenance.promotion_status = "reinforced_not_discovered"
        self._append_event("edge.provenance.updated", {
            "edge_id": edge.id,
            "confidence": edge.confidence,
            "provenance": edge.provenance.to_dict(),
        })

    def promote_edge_to_discovered(self, edge_id: str, evidence_refs: List[EvidenceRef]) -> None:
        """Promote an edge only when external/new evidence references exist."""
        if not evidence_refs:
            raise ValueError("promotion requires at least one evidence reference")
        edge = self.get_edge(edge_id)
        if edge is None:
            raise ValueError(f"edge not found: {edge_id}")
        edge.provenance.origin = EdgeOrigin.DISCOVERED
        edge.provenance.evidence_refs.extend(evidence_refs)
        edge.provenance.promotion_status = "promoted_by_evidence"
        edge.confidence = min(1.0, max(edge.confidence, 0.75))
        self._append_event("edge.provenance.updated", {
            "edge_id": edge.id,
            "confidence": edge.confidence,
            "provenance": edge.provenance.to_dict(),
        })

    def demote_edge(self, edge_id: str, reason: str = "contradicted") -> None:
        edge = self.get_edge(edge_id)
        if edge is None:
            raise ValueError(f"edge not found: {edge_id}")
        edge.provenance.promotion_status = f"demoted:{reason}"
        edge.confidence = max(0.0, edge.confidence * 0.5)
        self._append_event("edge.provenance.updated", {
            "edge_id": edge.id,
            "confidence": edge.confidence,
            "provenance": edge.provenance.to_dict(),
        })

    def get_valid_facts_at(self, t: float) -> List[TemporalFact]:
        """Return all facts valid at Unix timestamp t."""
        return [self.nodes[fid] for fid in self.interval_tree.query_valid_at(t) if fid in self.nodes]

    def has_contradiction(self, fact_id_a: str, fact_id_b: str) -> bool:
        """True if there is an active CONTRADICTS edge between a and b (either direction)."""
        for edge in self.edges.get(fact_id_a, []):
            if edge.target_id == fact_id_b and edge.edge_type == EdgeType.CONTRADICTS:
                return True
        for edge in self.edges.get(fact_id_b, []):
            if edge.target_id == fact_id_a and edge.edge_type == EdgeType.CONTRADICTS:
                return True
        return False

    def import_existing_memories(self) -> int:
        """
        One-time import of existing llm-kosh SQLite memories as TemporalFacts.
        Skips facts already present (by checking if their 'lkosh:<id>' synthetic ID exists).
        Returns count of newly imported facts.
        """
        try:
            from llm_kosh.engine.search import get_db, rebuild_index
        except ImportError:
            return 0

        rebuild_index(self.root)
        conn = get_db(self.root)
        rows = conn.execute(
            "SELECT id, title, body, created, status, superseded_by FROM documents"
        ).fetchall()
        conn.close()

        imported = 0
        for row in rows:
            mem_id, title, body, created_str, status, superseded_by = row
            synthetic_id = f"lkosh:{mem_id}"
            if synthetic_id in self.nodes:
                continue

            content = f"{title or ''}\n{body or ''}".strip()
            try:
                if created_str:
                    created_dt = datetime.fromisoformat(
                        created_str.replace("Z", "+00:00")
                    )
                else:
                    created_dt = datetime.now(timezone.utc)
            except Exception:
                created_dt = datetime.now(timezone.utc)

            fact = TemporalFact(
                id=synthetic_id,
                content=content,
                ingested_at=created_dt,
                documented_at=created_dt,
                valid_from=created_dt,
                valid_until=None,
                confidence=1.0 if status == "active" else 0.5,
                resonance_profile={},
                source="import",
            )
            self._register_fact(fact)

            if superseded_by:
                target_synthetic = f"lkosh:{superseded_by}"
                edge_id = "edge." + uuid.uuid4().hex[:12]
                edge = CausalEdge(
                    id=edge_id,
                    source_id=synthetic_id,
                    target_id=target_synthetic,
                    edge_type=EdgeType.SUPERSEDES,
                    confidence=1.0,
                    valid_from=created_dt,
                    valid_until=None,
                    established_by="import",
                )
                self.edges.setdefault(synthetic_id, []).append(edge)

            imported += 1
        return imported
