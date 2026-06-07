from __future__ import annotations

import bisect
import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Set


class EdgeType(str, Enum):
    ENABLES = "ENABLES"
    CAUSES = "CAUSES"
    CONTRADICTS = "CONTRADICTS"
    SUPERSEDES = "SUPERSEDES"
    INFERS = "INFERS"


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


@dataclass
class HyperEdge:
    id: str
    source_ids: Set[str]
    target_id: str
    edge_type: EdgeType
    confidence: float
    valid_from: datetime
    valid_until: Optional[datetime]


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
                }
                for e in edge_list
            ]

        snap = {"nodes": nodes_out, "edges": edges_out}
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
                    )
                    self.edges.setdefault(src_id, []).append(edge)
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

    def _register_fact(self, fact: TemporalFact) -> None:
        self.nodes[fact.id] = fact
        self.interval_tree.add(fact.id, _ts(fact.valid_from), _ts(fact.valid_until))

    # ------------------------------------------------------------------ write API

    def add_fact(
        self,
        content: str,
        ingested_at: datetime,
        documented_at: datetime,
        valid_from: datetime,
        valid_until: Optional[datetime],
        confidence: float,
        source: str,
        resonance_profile: Optional[dict] = None,
    ) -> str:
        fact_id = "fact." + uuid.uuid4().hex[:12]
        fact = TemporalFact(
            id=fact_id,
            content=content,
            ingested_at=ingested_at,
            documented_at=documented_at,
            valid_from=valid_from,
            valid_until=valid_until,
            confidence=confidence,
            resonance_profile=resonance_profile or {},
            source=source,
        )
        self._register_fact(fact)
        self._append_event("fact.added", {
            "id": fact_id,
            "content": content,
            "ingested_at": ingested_at.isoformat(),
            "documented_at": documented_at.isoformat(),
            "valid_from": valid_from.isoformat(),
            "valid_until": valid_until.isoformat() if valid_until else None,
            "confidence": confidence,
            "resonance_profile": resonance_profile or {},
            "source": source,
        })
        return fact_id

    def add_edge(
        self,
        source_id: str,
        target_id: str,
        edge_type: EdgeType,
        confidence: float,
        valid_from: datetime,
        valid_until: Optional[datetime],
        established_by: str,
    ) -> str:
        edge_id = "edge." + uuid.uuid4().hex[:12]
        edge = CausalEdge(
            id=edge_id,
            source_id=source_id,
            target_id=target_id,
            edge_type=edge_type,
            confidence=confidence,
            valid_from=valid_from,
            valid_until=valid_until,
            established_by=established_by,
        )
        self.edges.setdefault(source_id, []).append(edge)
        self._append_event("causal_edge.added", {
            "id": edge_id,
            "source_id": source_id,
            "target_id": target_id,
            "edge_type": edge_type.value,
            "confidence": confidence,
            "valid_from": valid_from.isoformat(),
            "valid_until": valid_until.isoformat() if valid_until else None,
            "established_by": established_by,
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
    ) -> str:
        he_id = "he." + uuid.uuid4().hex[:12]
        he = HyperEdge(
            id=he_id,
            source_ids=source_ids,
            target_id=target_id,
            edge_type=edge_type,
            confidence=confidence,
            valid_from=valid_from,
            valid_until=valid_until,
        )
        self.hyperedges.append(he)
        self._append_event("hyperedge.added", {
            "id": he_id,
            "source_ids": list(source_ids),
            "target_id": target_id,
            "edge_type": edge_type.value,
            "confidence": confidence,
            "valid_from": valid_from.isoformat(),
            "valid_until": valid_until.isoformat() if valid_until else None,
        })
        return he_id

    # ------------------------------------------------------------------ read API

    def get_fact(self, fact_id: str) -> Optional[TemporalFact]:
        return self.nodes.get(fact_id)

    def get_outgoing_edges(self, fact_id: str, query_time: float) -> List[CausalEdge]:
        """Return edges active at query_time from fact_id."""
        result = []
        for edge in self.edges.get(fact_id, []):
            vf = _ts(edge.valid_from) or 0.0
            vu = _ts(edge.valid_until)
            if vf <= query_time and (vu is None or vu > query_time):
                result.append(edge)
        return result

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
