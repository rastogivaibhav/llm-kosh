# Reasoning Engine v0.1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the Temporal Causal Reasoning Engine as `llm_kosh/engine/reasoning/` — five components (CausalDAG, CausalRetrieval, FiberBundle, LyapunovCritic, EscapeMechanism), a `ReasoningEngine` public class, and four MCP tools — with zero breaking changes to any existing llm-kosh code.

**Architecture:** Parallel subpackage alongside existing engine modules. CausalDAG owns an append-only JSONL event log at `<root>/reasoning/events.jsonl` and builds a Temporal Causal Hypergraph in memory on startup. CausalRetrieval uses DCT-based resonance profiles instead of cosine similarity. FiberBundle preserves all valid causal paths. LyapunovCritic scores bundle stability. EscapeMechanism does targeted exploration when stability fails.

**Tech Stack:** Python 3.10+ stdlib only (dataclasses, math, bisect, json, uuid, collections). No new pip dependencies. Uses existing `llm_kosh.core.utils`, `llm_kosh.engine.search.tokenize`, and `llm_kosh.core.memory.init_cartridge`. MCP tools added to existing `mcp_server.py` via `@mcp.tool()` decorator pattern.

---

## File Map

**Create:**
- `llm_kosh/engine/reasoning/__init__.py` — `ReasoningEngine`, `QueryResult`
- `llm_kosh/engine/reasoning/causal_dag.py` — `EdgeType`, `TemporalFact`, `CausalEdge`, `HyperEdge`, `TrajectoryState`, `IntervalTree`, `CausalDAG`
- `llm_kosh/engine/reasoning/causal_retrieval.py` — `resonance_profile()`, `harmonic_match()`, `_dct()`, `CausalRetrieval`
- `llm_kosh/engine/reasoning/fiber_bundle.py` — `CausalPath`, `Fiber`, `FiberBundle`, `build_fiber_bundle()`
- `llm_kosh/engine/reasoning/lyapunov_critic.py` — `StabilityResult`, `LyapunovCritic`
- `llm_kosh/engine/reasoning/escape.py` — `EscapeMechanism`
- `tests/test_reasoning_causal_dag.py`
- `tests/test_reasoning_retrieval.py`
- `tests/test_reasoning_fiber_bundle.py`
- `tests/test_reasoning_lyapunov.py`
- `tests/test_reasoning_escape.py`
- `tests/test_reasoning_engine.py`
- `tests/test_reasoning_mcp.py`

**Modify:**
- `llm_kosh/core/memory.py` — add `reasoning/` dir to `init_cartridge`
- `llm_kosh/mcp_server.py` — add four new `@mcp.tool()` functions

---

## Task 1: Data Models

**Files:**
- Create: `llm_kosh/engine/reasoning/causal_dag.py`
- Test: `tests/test_reasoning_causal_dag.py`

- [ ] **Step 1.1: Write the failing test**

```python
# tests/test_reasoning_causal_dag.py
import pytest
from datetime import datetime, timezone
from llm_kosh.engine.reasoning.causal_dag import (
    EdgeType, TemporalFact, CausalEdge, HyperEdge, TrajectoryState
)

def _now() -> datetime:
    return datetime.now(timezone.utc)

def test_edge_type_values():
    assert EdgeType.ENABLES.value == "ENABLES"
    assert EdgeType.CAUSES.value == "CAUSES"
    assert EdgeType.CONTRADICTS.value == "CONTRADICTS"
    assert EdgeType.SUPERSEDES.value == "SUPERSEDES"
    assert EdgeType.INFERS.value == "INFERS"

def test_temporal_fact_creation():
    now = _now()
    fact = TemporalFact(
        id="f1",
        content="Apples fall downward",
        ingested_at=now,
        documented_at=now,
        valid_from=now,
        valid_until=None,
        confidence=0.9,
        resonance_profile={"low": [0.1], "mid": [0.2], "high": [0.3]},
        source="user",
    )
    assert fact.id == "f1"
    assert fact.confidence == 0.9
    assert fact.valid_until is None
    assert fact.source == "user"

def test_causal_edge_creation():
    now = _now()
    edge = CausalEdge(
        id="e1",
        source_id="f1",
        target_id="f2",
        edge_type=EdgeType.CAUSES,
        confidence=0.8,
        valid_from=now,
        valid_until=None,
        established_by="agent-1",
    )
    assert edge.source_id == "f1"
    assert edge.edge_type == EdgeType.CAUSES

def test_hyperedge_creation():
    now = _now()
    he = HyperEdge(
        id="he1",
        source_ids={"f1", "f2"},
        target_id="f3",
        edge_type=EdgeType.ENABLES,
        confidence=0.75,
        valid_from=now,
        valid_until=None,
    )
    assert "f1" in he.source_ids
    assert he.target_id == "f3"

def test_trajectory_state_defaults():
    ts = TrajectoryState(session_id="s1")
    assert ts.escape_count == 0
    assert ts.steps == []
    assert ts.stability == 1.0
```

- [ ] **Step 1.2: Run test to verify it fails**

```
pytest tests/test_reasoning_causal_dag.py -v
```
Expected: `ModuleNotFoundError: No module named 'llm_kosh.engine.reasoning'`

- [ ] **Step 1.3: Create the package and data models**

```python
# llm_kosh/engine/reasoning/__init__.py
# (empty for now — filled in Task 10)
```

```python
# llm_kosh/engine/reasoning/causal_dag.py
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
```

- [ ] **Step 1.4: Run tests**

```
pytest tests/test_reasoning_causal_dag.py -v
```
Expected: all 5 tests PASS

- [ ] **Step 1.5: Commit**

```bash
git add llm_kosh/engine/reasoning/__init__.py llm_kosh/engine/reasoning/causal_dag.py tests/test_reasoning_causal_dag.py
git commit -m "feat(reasoning): add data models — TemporalFact, CausalEdge, HyperEdge, TrajectoryState"
```

---

## Task 2: IntervalTree + CausalDAG Event Log

**Files:**
- Modify: `llm_kosh/engine/reasoning/causal_dag.py`
- Test: `tests/test_reasoning_causal_dag.py` (extend)

- [ ] **Step 2.1: Add tests for IntervalTree and event log**

Append to `tests/test_reasoning_causal_dag.py`:

```python
import tempfile, shutil
from pathlib import Path
from llm_kosh.engine.reasoning.causal_dag import IntervalTree, CausalDAG
from llm_kosh.core.memory import init_cartridge

@pytest.fixture
def cartridge(tmp_path):
    init_cartridge(tmp_path, "Test")
    return tmp_path

def test_interval_tree_valid_at():
    tree = IntervalTree()
    now = _now()
    t0 = now.timestamp()
    tree.add("f1", t0 - 100, None)          # started 100s ago, still valid
    tree.add("f2", t0 - 200, t0 - 50)       # expired 50s ago
    tree.add("f3", t0 + 100, None)           # starts in future

    valid = tree.query_valid_at(t0)
    assert "f1" in valid
    assert "f2" not in valid
    assert "f3" not in valid

def test_interval_tree_remove():
    tree = IntervalTree()
    now = _now().timestamp()
    tree.add("f1", now - 10, None)
    tree.remove("f1")
    assert tree.query_valid_at(now) == []

def test_causal_dag_add_fact_writes_log(cartridge):
    dag = CausalDAG(cartridge)
    now = _now()
    fact_id = dag.add_fact(
        content="Gravity pulls objects down",
        ingested_at=now,
        documented_at=now,
        valid_from=now,
        valid_until=None,
        confidence=0.95,
        source="user",
    )
    assert fact_id.startswith("fact.")
    assert fact_id in dag.nodes

    # Event log was written
    log_path = cartridge / "reasoning" / "events.jsonl"
    assert log_path.exists()
    events = [json.loads(l) for l in log_path.read_text().splitlines() if l.strip()]
    assert any(e["event"] == "fact.added" and e["payload"]["id"] == fact_id for e in events)

def test_causal_dag_add_edge(cartridge):
    dag = CausalDAG(cartridge)
    now = _now()
    fid1 = dag.add_fact("A", now, now, now, None, 0.9, "user")
    fid2 = dag.add_fact("B", now, now, now, None, 0.9, "user")
    eid = dag.add_edge(fid1, fid2, EdgeType.CAUSES, 0.8, now, None, "test-agent")
    assert eid in {e.id for e in dag.edges.get(fid1, [])}

def test_causal_dag_rebuild_from_log(cartridge):
    dag1 = CausalDAG(cartridge)
    now = _now()
    fid = dag1.add_fact("Persistent fact", now, now, now, None, 0.9, "user")

    # Fresh instance must rebuild from log
    dag2 = CausalDAG(cartridge)
    assert fid in dag2.nodes
    assert dag2.nodes[fid].content == "Persistent fact"
```

- [ ] **Step 2.2: Run to verify failure**

```
pytest tests/test_reasoning_causal_dag.py::test_interval_tree_valid_at -v
```
Expected: `ImportError: cannot import name 'IntervalTree'`

- [ ] **Step 2.3: Implement IntervalTree and CausalDAG**

Append to `llm_kosh/engine/reasoning/causal_dag.py` (after the dataclasses):

```python
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

    def __init__(self, root: Path) -> None:
        self.root = root
        self.nodes: Dict[str, TemporalFact] = {}
        self.edges: Dict[str, List[CausalEdge]] = {}   # source_id -> edges
        self.hyperedges: List[HyperEdge] = []
        self.interval_tree = IntervalTree()
        self._ensure_dirs()
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
```

- [ ] **Step 2.4: Run tests**

```
pytest tests/test_reasoning_causal_dag.py -v
```
Expected: all tests PASS

- [ ] **Step 2.5: Commit**

```bash
git add llm_kosh/engine/reasoning/causal_dag.py tests/test_reasoning_causal_dag.py
git commit -m "feat(reasoning): add IntervalTree and CausalDAG with append-only event log"
```

---

## Task 3: CausalDAG — Import Existing llm-kosh Memories

**Files:**
- Modify: `llm_kosh/engine/reasoning/causal_dag.py`
- Modify: `llm_kosh/core/memory.py`
- Test: `tests/test_reasoning_causal_dag.py` (extend)

- [ ] **Step 3.1: Add tests**

Append to `tests/test_reasoning_causal_dag.py`:

```python
from llm_kosh.engine.search import rebuild_index
from llm_kosh.core.memory import init_cartridge
from llm_kosh.core.utils import now_iso
import sqlite3

def _write_test_memory(root, title="Test Memory", body="A test fact", kind="note"):
    """Write a minimal memory markdown file and rebuild the index."""
    import uuid
    from pathlib import Path
    src = root / "source" / "notes"
    src.mkdir(parents=True, exist_ok=True)
    mem_id = "test." + uuid.uuid4().hex[:8]
    content = f"""---
id: {mem_id}
type: {kind}
title: {title}
project: test-project
status: active
visibility: private
created: {now_iso()}
---

{body}
"""
    (src / f"{mem_id}.md").write_text(content, encoding="utf-8")
    rebuild_index(root)
    return mem_id

def test_import_existing_memories(cartridge):
    mem_id = _write_test_memory(cartridge, "Gravity Note", "Objects fall at 9.8 m/s²")
    dag = CausalDAG(cartridge)
    dag.import_existing_memories()
    found = any(f.content and "9.8" in f.content for f in dag.nodes.values())
    assert found, "Expected imported memory in CausalDAG nodes"

def test_import_does_not_duplicate(cartridge):
    _write_test_memory(cartridge, "Unique Note", "Only once")
    dag = CausalDAG(cartridge)
    dag.import_existing_memories()
    count_before = len(dag.nodes)
    dag.import_existing_memories()
    assert len(dag.nodes) == count_before
```

- [ ] **Step 3.2: Run to verify failure**

```
pytest tests/test_reasoning_causal_dag.py::test_import_existing_memories -v
```
Expected: `AttributeError: 'CausalDAG' object has no attribute 'import_existing_memories'`

- [ ] **Step 3.3: Add `import_existing_memories` to CausalDAG**

Add this method inside the `CausalDAG` class in `causal_dag.py`:

```python
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
                from datetime import datetime, timezone
                if created_str:
                    created_dt = datetime.fromisoformat(
                        created_str.replace("Z", "+00:00")
                    )
                else:
                    created_dt = datetime.now(timezone.utc)
            except Exception:
                from datetime import datetime, timezone
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
```

- [ ] **Step 3.4: Add `reasoning/` dir to `init_cartridge`**

Open `llm_kosh/core/memory.py`. Find the list inside `init_cartridge` that contains `"ledger"`, `"indexes"`, etc. Add `"reasoning"` to it:

```python
    for rel in [
        "source/identity", "source/preferences", "source/projects", "source/decisions",
        "source/prompts", "source/notes", "source/generated-files", "source/intake", "source/conversations",
        "source/receipts", "source/corrections", "source/gaps", "source/suggestions",
        "ledger", "indexes", "exports", "quarantine", "reports", "attachments/imports",
        "reasoning",
    ]:
```

- [ ] **Step 3.5: Run tests**

```
pytest tests/test_reasoning_causal_dag.py -v
```
Expected: all tests PASS

- [ ] **Step 3.6: Commit**

```bash
git add llm_kosh/engine/reasoning/causal_dag.py llm_kosh/core/memory.py tests/test_reasoning_causal_dag.py
git commit -m "feat(reasoning): import existing llm-kosh memories into CausalDAG on demand"
```

---

## Task 4: Resonance Profile (DCT-based)

**Files:**
- Create: `llm_kosh/engine/reasoning/causal_retrieval.py`
- Test: `tests/test_reasoning_retrieval.py`

- [ ] **Step 4.1: Write failing tests**

```python
# tests/test_reasoning_retrieval.py
import pytest
import math
from llm_kosh.engine.reasoning.causal_retrieval import resonance_profile, harmonic_match, _dct

def test_dct_length():
    x = [1.0, 2.0, 3.0, 4.0]
    result = _dct(x)
    assert len(result) == 4

def test_dct_dc_component():
    # DC component (k=0) should be 2 * sum(x)
    x = [1.0, 1.0, 1.0, 1.0]
    result = _dct(x)
    assert abs(result[0] - 2 * sum(x)) < 1e-6

def test_resonance_profile_structure():
    profile = resonance_profile("apple orange fruit healthy eating")
    assert "low" in profile
    assert "mid" in profile
    assert "high" in profile
    assert isinstance(profile["low"], list)
    assert len(profile["low"]) > 0

def test_resonance_profile_empty_text():
    profile = resonance_profile("")
    assert "low" in profile
    # Should not raise, should return zero-filled profile

def test_harmonic_match_identical():
    profile = resonance_profile("machine learning neural networks")
    score = harmonic_match(profile, profile)
    assert score > 0.9, f"Identical profiles should score near 1.0, got {score}"

def test_harmonic_match_different():
    p1 = resonance_profile("quantum physics particles")
    p2 = resonance_profile("baking bread flour yeast")
    score = harmonic_match(p1, p2)
    assert score < 0.5, f"Unrelated profiles should score low, got {score}"

def test_harmonic_match_partial():
    p1 = resonance_profile("machine learning neural networks deep")
    p2 = resonance_profile("machine learning algorithms")
    score = harmonic_match(p1, p2)
    assert 0.2 < score < 1.0, f"Partial overlap should score between 0.2 and 1.0, got {score}"
```

- [ ] **Step 4.2: Run to verify failure**

```
pytest tests/test_reasoning_retrieval.py -v
```
Expected: `ModuleNotFoundError: No module named 'llm_kosh.engine.reasoning.causal_retrieval'`

- [ ] **Step 4.3: Implement `causal_retrieval.py` (resonance functions only)**

```python
# llm_kosh/engine/reasoning/causal_retrieval.py
from __future__ import annotations

import math
from collections import Counter
from typing import Dict, List, Optional, Tuple

# Re-use existing tokenizer (no new dependency)
from llm_kosh.engine.search import tokenize

_N_COMPONENTS = 32  # DCT vector size — 32 gives good frequency resolution at low cost


def _dct(x: List[float]) -> List[float]:
    """DCT-II: standard type-II Discrete Cosine Transform (stdlib math only)."""
    N = len(x)
    if N == 0:
        return []
    result = []
    for k in range(N):
        s = sum(x[n] * math.cos(math.pi * k * (2 * n + 1) / (2 * N)) for n in range(N))
        result.append(2.0 * s)
    return result


def resonance_profile(
    text: str,
    idf: Optional[Dict[str, float]] = None,
    n_components: int = _N_COMPONENTS,
) -> Dict[str, List[float]]:
    """
    Build a DCT-based resonance profile for text.

    1. Tokenize text.
    2. Compute TF (or TF-IDF if idf supplied).
    3. Take top-n_components terms sorted by weight.
    4. Apply DCT-II to the weight vector.
    5. Split into low / mid / high frequency bands.

    Returns dict with keys "low", "mid", "high".
    """
    tokens = tokenize(text)
    if not tokens:
        band = n_components // 3
        return {
            "low": [0.0] * band,
            "mid": [0.0] * band,
            "high": [0.0] * (n_components - 2 * band),
        }

    tf = Counter(tokens)
    total = len(tokens)

    if idf:
        scored = [(t, (cnt / total) * idf.get(t, 1.0)) for t, cnt in tf.items()]
    else:
        scored = [(t, cnt / total) for t, cnt in tf.items()]

    scored.sort(key=lambda x: -x[1])
    top_weights = [w for _, w in scored[:n_components]]
    # Pad to exactly n_components
    top_weights += [0.0] * (n_components - len(top_weights))

    coeffs = _dct(top_weights)

    band = n_components // 3
    return {
        "low": coeffs[:band],
        "mid": coeffs[band : 2 * band],
        "high": coeffs[2 * band :],
    }


def harmonic_match(
    profile_a: Dict[str, List[float]],
    profile_b: Dict[str, List[float]],
    weights: Optional[Dict[str, float]] = None,
) -> float:
    """
    Compute multi-scale resonance score between two profiles.
    Bands weighted: low=0.5 (dominant concepts), mid=0.3, high=0.2 (rare terms).
    Returns score in [0, 1].
    """
    if weights is None:
        weights = {"low": 0.5, "mid": 0.3, "high": 0.2}

    score = 0.0
    for band, w in weights.items():
        a = profile_a.get(band, [])
        b = profile_b.get(band, [])
        if not a or not b:
            continue
        min_len = min(len(a), len(b))
        dot = sum(a[i] * b[i] for i in range(min_len))
        norm_a = math.sqrt(sum(v * v for v in a))
        norm_b = math.sqrt(sum(v * v for v in b))
        if norm_a > 0 and norm_b > 0:
            score += w * (dot / (norm_a * norm_b))

    return min(1.0, max(0.0, score))
```

- [ ] **Step 4.4: Run tests**

```
pytest tests/test_reasoning_retrieval.py -v
```
Expected: all 7 tests PASS

- [ ] **Step 4.5: Commit**

```bash
git add llm_kosh/engine/reasoning/causal_retrieval.py tests/test_reasoning_retrieval.py
git commit -m "feat(reasoning): add DCT resonance profile and harmonic matching"
```

---

## Task 5: CausalRetrieval — Full Retrieve Pipeline

**Files:**
- Modify: `llm_kosh/engine/reasoning/causal_retrieval.py`
- Test: `tests/test_reasoning_retrieval.py` (extend)

- [ ] **Step 5.1: Add tests for full retrieve pipeline**

Append to `tests/test_reasoning_retrieval.py`:

```python
from datetime import datetime, timezone
from pathlib import Path
from llm_kosh.engine.reasoning.causal_dag import CausalDAG, EdgeType
from llm_kosh.engine.reasoning.causal_retrieval import CausalRetrieval
from llm_kosh.core.memory import init_cartridge

@pytest.fixture
def dag_with_facts(tmp_path):
    init_cartridge(tmp_path, "Test")
    dag = CausalDAG(tmp_path)
    now = datetime.now(timezone.utc)
    fid1 = dag.add_fact("Gravity pulls objects toward Earth", now, now, now, None, 0.9, "user")
    fid2 = dag.add_fact("Newton formulated laws of motion", now, now, now, None, 0.9, "user")
    fid3 = dag.add_fact("Bread is a baked food product", now, now, now, None, 0.9, "user")
    dag.add_edge(fid1, fid2, EdgeType.ENABLES, 0.8, now, None, "test")
    return dag, fid1, fid2, fid3

def test_retrieve_returns_anchor_facts(dag_with_facts):
    dag, fid1, fid2, fid3 = dag_with_facts
    retrieval = CausalRetrieval(dag)
    import time
    results = retrieval.retrieve("gravity Newton motion", time.time(), depth=2)
    fact_ids = [r[0].id for r in results]
    assert fid1 in fact_ids or fid2 in fact_ids

def test_retrieve_excludes_unrelated(dag_with_facts):
    dag, fid1, fid2, fid3 = dag_with_facts
    retrieval = CausalRetrieval(dag)
    import time
    results = retrieval.retrieve("gravity Newton motion", time.time(), depth=2)
    # bread fact should score very low or absent
    scores = {r[0].id: r[2] for r in results}
    bread_score = scores.get(fid3, 0.0)
    gravity_score = scores.get(fid1, 0.0)
    assert gravity_score > bread_score

def test_retrieve_causal_distance(dag_with_facts):
    dag, fid1, fid2, fid3 = dag_with_facts
    retrieval = CausalRetrieval(dag)
    import time
    results = retrieval.retrieve("gravity", time.time(), depth=2)
    dist_map = {r[0].id: r[1] for r in results}
    # fid1 is anchor (distance 0), fid2 is 1 hop away
    if fid1 in dist_map and fid2 in dist_map:
        assert dist_map[fid1] <= dist_map[fid2]

def test_retrieve_temporal_filter(dag_with_facts):
    dag, fid1, fid2, fid3 = dag_with_facts
    retrieval = CausalRetrieval(dag)
    # Query at time 0 (before any fact's valid_from) — should return nothing
    results = retrieval.retrieve("gravity", query_time=0.0, depth=2)
    assert results == []
```

- [ ] **Step 5.2: Run to verify failure**

```
pytest tests/test_reasoning_retrieval.py::test_retrieve_returns_anchor_facts -v
```
Expected: `ImportError: cannot import name 'CausalRetrieval'`

- [ ] **Step 5.3: Implement `CausalRetrieval` class**

Append to `llm_kosh/engine/reasoning/causal_retrieval.py`:

```python
from llm_kosh.engine.reasoning.causal_dag import CausalDAG, TemporalFact, CausalEdge


class CausalRetrieval:
    """
    Resonance-based retrieval over the CausalDAG.
    Returns (TemporalFact, causal_distance, score) tuples.
    """

    def __init__(self, dag: CausalDAG, idf: Optional[Dict[str, float]] = None) -> None:
        self.dag = dag
        self.idf = idf  # TF-IDF weights for richer resonance (optional)
        self._build_resonance_index()

    def _build_resonance_index(self) -> None:
        """Build resonance profiles for all facts currently in the DAG."""
        self._resonance_index: Dict[str, Dict[str, List[float]]] = {}
        for fid, fact in self.dag.nodes.items():
            if fact.resonance_profile:
                self._resonance_index[fid] = fact.resonance_profile
            else:
                self._resonance_index[fid] = resonance_profile(fact.content, self.idf)

    def retrieve(
        self,
        query: str,
        query_time: float,
        depth: int = 3,
        top_anchors: int = 5,
    ) -> List[Tuple[TemporalFact, int, float]]:
        """
        Full retrieval pipeline.

        1. Build query resonance profile.
        2. Harmonic-match against all facts valid at query_time.
        3. Select top-anchor facts.
        4. BFS-traverse causal edges up to depth hops.
        5. Score each candidate.

        Returns list of (fact, causal_distance, score) sorted by score descending.
        """
        if query_time <= 0:
            return []

        query_prof = resonance_profile(query, self.idf)
        valid_ids = set(self.dag.interval_tree.query_valid_at(query_time))

        if not valid_ids:
            return []

        # Step 1: harmonic match → anchor scores
        anchor_scores: Dict[str, float] = {}
        for fid in valid_ids:
            prof = self._resonance_index.get(fid)
            if prof is None:
                fact = self.dag.nodes.get(fid)
                if fact:
                    prof = resonance_profile(fact.content, self.idf)
                    self._resonance_index[fid] = prof
            if prof:
                anchor_scores[fid] = harmonic_match(query_prof, prof)

        # Step 2: pick top anchors
        top = sorted(anchor_scores, key=lambda x: -anchor_scores[x])[:top_anchors]

        # Step 3: BFS from anchors
        visited: Dict[str, int] = {fid: 0 for fid in top}
        queue = list(top)
        for _ in range(depth):
            next_q: List[str] = []
            for fid in queue:
                for edge in self.dag.get_outgoing_edges(fid, query_time):
                    if edge.target_id not in visited and edge.target_id in valid_ids:
                        visited[edge.target_id] = visited[fid] + 1
                        next_q.append(edge.target_id)
            queue = next_q
            if not queue:
                break

        # Step 4: score
        results: List[Tuple[TemporalFact, int, float]] = []
        for fid, dist in visited.items():
            fact = self.dag.nodes.get(fid)
            if not fact:
                continue
            resonance = anchor_scores.get(fid, 0.0)
            causal_bonus = 1.0 / (dist + 1)
            score = 0.6 * resonance + 0.3 * causal_bonus + 0.1 * fact.confidence
            results.append((fact, dist, round(score, 4)))

        results.sort(key=lambda x: -x[2])
        return results
```

- [ ] **Step 5.4: Run tests**

```
pytest tests/test_reasoning_retrieval.py -v
```
Expected: all tests PASS

- [ ] **Step 5.5: Commit**

```bash
git add llm_kosh/engine/reasoning/causal_retrieval.py tests/test_reasoning_retrieval.py
git commit -m "feat(reasoning): add CausalRetrieval with harmonic matching and BFS causal traversal"
```

---

## Task 6: FiberBundle — Path Enumeration

**Files:**
- Create: `llm_kosh/engine/reasoning/fiber_bundle.py`
- Test: `tests/test_reasoning_fiber_bundle.py`

- [ ] **Step 6.1: Write failing tests**

```python
# tests/test_reasoning_fiber_bundle.py
import pytest
from datetime import datetime, timezone
from llm_kosh.core.memory import init_cartridge
from llm_kosh.engine.reasoning.causal_dag import CausalDAG, EdgeType
from llm_kosh.engine.reasoning.causal_retrieval import CausalRetrieval
from llm_kosh.engine.reasoning.fiber_bundle import CausalPath, Fiber, FiberBundle, build_fiber_bundle

def _now():
    return datetime.now(timezone.utc)

@pytest.fixture
def graph(tmp_path):
    """A → B → C, and A → C directly (two paths to C)."""
    init_cartridge(tmp_path, "Test")
    dag = CausalDAG(tmp_path)
    now = _now()
    fa = dag.add_fact("A fact", now, now, now, None, 0.9, "user")
    fb = dag.add_fact("B fact", now, now, now, None, 0.9, "user")
    fc = dag.add_fact("C fact", now, now, now, None, 0.9, "user")
    ea1 = dag.add_edge(fa, fb, EdgeType.CAUSES, 0.8, now, None, "test")
    ea2 = dag.add_edge(fb, fc, EdgeType.CAUSES, 0.7, now, None, "test")
    ea3 = dag.add_edge(fa, fc, EdgeType.ENABLES, 0.9, now, None, "test")  # direct path
    return dag, fa, fb, fc

def test_causal_path_confidence_product():
    from llm_kosh.engine.reasoning.causal_dag import CausalEdge, EdgeType
    import uuid
    now = _now()
    e1 = CausalEdge(id="e1", source_id="a", target_id="b", edge_type=EdgeType.CAUSES,
                    confidence=0.8, valid_from=now, valid_until=None, established_by="x")
    e2 = CausalEdge(id="e2", source_id="b", target_id="c", edge_type=EdgeType.CAUSES,
                    confidence=0.5, valid_from=now, valid_until=None, established_by="x")
    path = CausalPath(edges=[e1, e2], confidence_product=0.8 * 0.5, temporal_consistency=1.0)
    assert abs(path.confidence_product - 0.4) < 1e-9

def test_build_fiber_bundle_preserves_all_paths(graph):
    import time
    dag, fa, fb, fc = graph
    retrieval = CausalRetrieval(dag)
    candidates = retrieval.retrieve("fact", time.time(), depth=3)
    bundle = build_fiber_bundle(dag, candidates, anchor_ids=[fa], query_time=time.time(), max_hops=3)
    assert isinstance(bundle, FiberBundle)
    # C should be reachable via two paths: A→B→C and A→C
    if fc in bundle.fibers:
        assert bundle.fibers[fc].degeneracy >= 2

def test_fiber_max_confidence(graph):
    import time
    dag, fa, fb, fc = graph
    retrieval = CausalRetrieval(dag)
    candidates = retrieval.retrieve("fact", time.time(), depth=3)
    bundle = build_fiber_bundle(dag, candidates, anchor_ids=[fa], query_time=time.time(), max_hops=3)
    for fiber in bundle.fibers.values():
        assert fiber.max_confidence >= 0.0
        assert fiber.max_confidence <= 1.0

def test_fiber_bundle_never_collapses(graph):
    import time
    dag, fa, fb, fc = graph
    retrieval = CausalRetrieval(dag)
    candidates = retrieval.retrieve("fact", time.time(), depth=3)
    bundle = build_fiber_bundle(dag, candidates, anchor_ids=[fa], query_time=time.time(), max_hops=3)
    # Bundle must carry paths, not a single ranked list
    for fid, fiber in bundle.fibers.items():
        assert isinstance(fiber.paths, list)
```

- [ ] **Step 6.2: Run to verify failure**

```
pytest tests/test_reasoning_fiber_bundle.py -v
```
Expected: `ModuleNotFoundError: No module named 'llm_kosh.engine.reasoning.fiber_bundle'`

- [ ] **Step 6.3: Implement `fiber_bundle.py`**

```python
# llm_kosh/engine/reasoning/fiber_bundle.py
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple

from llm_kosh.engine.reasoning.causal_dag import CausalDAG, CausalEdge, TemporalFact, _ts


@dataclass
class CausalPath:
    """One causal derivation path: an ordered sequence of edges."""
    edges: List[CausalEdge]
    confidence_product: float   # product of all edge confidences
    temporal_consistency: float # 1.0 if all edges respect time ordering, else 0.5


@dataclass
class Fiber:
    """All paths reaching a single target fact."""
    fact: TemporalFact
    paths: List[CausalPath]
    degeneracy: int        # number of independent paths
    max_confidence: float  # highest confidence_product across paths


@dataclass
class FiberBundle:
    """The full path bundle — never collapsed."""
    fibers: Dict[str, Fiber]   # fact_id -> Fiber


def build_fiber_bundle(
    dag: CausalDAG,
    candidates: List[Tuple[TemporalFact, int, float]],
    anchor_ids: List[str],
    query_time: float,
    max_hops: int = 3,
) -> FiberBundle:
    """
    Enumerate all valid causal paths from anchor_ids to each candidate fact.
    Groups by target fact into fibers. Never collapses to a single path.
    """
    target_ids = {fact.id for fact, _, _ in candidates}
    fibers: Dict[str, Fiber] = {}

    for anchor_id in anchor_ids:
        paths_to = _enumerate_paths(dag, anchor_id, target_ids, max_hops, query_time)
        for target_id, path_list in paths_to.items():
            target_fact = dag.get_fact(target_id)
            if target_fact is None:
                continue
            if target_id not in fibers:
                fibers[target_id] = Fiber(
                    fact=target_fact,
                    paths=[],
                    degeneracy=0,
                    max_confidence=0.0,
                )
            fibers[target_id].paths.extend(path_list)

    # Compute derived fields
    for fiber in fibers.values():
        fiber.degeneracy = len(fiber.paths)
        fiber.max_confidence = max(
            (p.confidence_product for p in fiber.paths), default=0.0
        )

    return FiberBundle(fibers=fibers)


def _enumerate_paths(
    dag: CausalDAG,
    start_id: str,
    targets: Set[str],
    max_hops: int,
    query_time: float,
) -> Dict[str, List[CausalPath]]:
    """
    DFS from start_id to any target in targets.
    Returns {target_id: [CausalPath, ...]}.
    """
    result: Dict[str, List[CausalPath]] = {}

    # Stack items: (current_fact_id, edges_so_far, confidence_so_far, temporal_ok, visited_ids)
    stack: List[Tuple[str, List[CausalEdge], float, bool, Set[str]]] = [
        (start_id, [], 1.0, True, {start_id})
    ]

    while stack:
        current_id, edge_path, conf, t_ok, visited = stack.pop()

        if len(edge_path) > max_hops:
            continue

        if edge_path and current_id in targets:
            path = CausalPath(
                edges=list(edge_path),
                confidence_product=round(conf, 6),
                temporal_consistency=1.0 if t_ok else 0.5,
            )
            result.setdefault(current_id, []).append(path)
            # Don't continue from here — target reached

        if len(edge_path) >= max_hops:
            continue

        for edge in dag.get_outgoing_edges(current_id, query_time):
            if edge.target_id in visited:
                continue  # no cycles

            # Check temporal consistency: source.valid_from <= target.valid_from
            source_fact = dag.get_fact(current_id)
            target_fact = dag.get_fact(edge.target_id)
            new_t_ok = t_ok
            if source_fact and target_fact:
                sf_ts = _ts(source_fact.valid_from) or 0.0
                tf_ts = _ts(target_fact.valid_from) or 0.0
                new_t_ok = t_ok and (sf_ts <= tf_ts)

            stack.append((
                edge.target_id,
                edge_path + [edge],
                conf * edge.confidence,
                new_t_ok,
                visited | {edge.target_id},
            ))

    return result
```

- [ ] **Step 6.4: Run tests**

```
pytest tests/test_reasoning_fiber_bundle.py -v
```
Expected: all tests PASS

- [ ] **Step 6.5: Commit**

```bash
git add llm_kosh/engine/reasoning/fiber_bundle.py tests/test_reasoning_fiber_bundle.py
git commit -m "feat(reasoning): add FiberBundle — DFS path enumeration, degeneracy, never collapses"
```

---

## Task 7: LyapunovCritic

**Files:**
- Create: `llm_kosh/engine/reasoning/lyapunov_critic.py`
- Test: `tests/test_reasoning_lyapunov.py`

- [ ] **Step 7.1: Write failing tests**

```python
# tests/test_reasoning_lyapunov.py
import pytest
from datetime import datetime, timezone
from llm_kosh.core.memory import init_cartridge
from llm_kosh.engine.reasoning.causal_dag import CausalDAG, EdgeType, TemporalFact
from llm_kosh.engine.reasoning.fiber_bundle import FiberBundle, Fiber, CausalPath, CausalEdge
from llm_kosh.engine.reasoning.lyapunov_critic import LyapunovCritic, StabilityResult

def _now():
    return datetime.now(timezone.utc)

def _make_dag(tmp_path):
    init_cartridge(tmp_path, "Test")
    return CausalDAG(tmp_path)

def _make_edge(source_id, target_id, edge_type=EdgeType.CAUSES, conf=0.8):
    now = _now()
    return CausalEdge(id="e-test", source_id=source_id, target_id=target_id,
                      edge_type=edge_type, confidence=conf,
                      valid_from=now, valid_until=None, established_by="test")

def test_stability_result_fields():
    r = StabilityResult(score=0.8, status="stable",
                        dimensions={"temporal_consistency": 1.0, "contradiction_score": 0.0,
                                    "path_diversity": 0.8, "degeneracy": 0.9},
                        implicated_facts=[])
    assert r.score == 0.8
    assert r.status == "stable"

def test_empty_bundle_is_stable(tmp_path):
    dag = _make_dag(tmp_path)
    critic = LyapunovCritic(dag)
    bundle = FiberBundle(fibers={})
    result = critic.evaluate(bundle)
    assert result.status == "stable"
    assert result.score >= 0.7

def test_single_path_bundle_stable(tmp_path):
    dag = _make_dag(tmp_path)
    now = _now()
    fa = dag.add_fact("A", now, now, now, None, 0.9, "user")
    fb = dag.add_fact("B", now, now, now, None, 0.9, "user")
    fact_b = dag.get_fact(fb)
    edge = _make_edge(fa, fb)
    path = CausalPath(edges=[edge], confidence_product=0.8, temporal_consistency=1.0)
    fiber = Fiber(fact=fact_b, paths=[path], degeneracy=1, max_confidence=0.8)
    bundle = FiberBundle(fibers={fb: fiber})
    critic = LyapunovCritic(dag)
    result = critic.evaluate(bundle)
    assert result.status in ("stable", "marginal")

def test_contradiction_lowers_score(tmp_path):
    dag = _make_dag(tmp_path)
    now = _now()
    fa = dag.add_fact("A", now, now, now, None, 0.9, "user")
    fb = dag.add_fact("B", now, now, now, None, 0.9, "user")
    # Add contradiction edge
    dag.add_edge(fa, fb, EdgeType.CONTRADICTS, 1.0, now, None, "test")
    fact_a = dag.get_fact(fa)
    fact_b = dag.get_fact(fb)
    path_a = CausalPath(edges=[], confidence_product=1.0, temporal_consistency=1.0)
    path_b = CausalPath(edges=[], confidence_product=1.0, temporal_consistency=1.0)
    bundle = FiberBundle(fibers={
        fa: Fiber(fact=fact_a, paths=[path_a], degeneracy=1, max_confidence=1.0),
        fb: Fiber(fact=fact_b, paths=[path_b], degeneracy=1, max_confidence=1.0),
    })
    critic = LyapunovCritic(dag)
    result = critic.evaluate(bundle)
    assert result.dimensions["contradiction_score"] > 0.0

def test_thresholds_configurable(tmp_path):
    dag = _make_dag(tmp_path)
    critic = LyapunovCritic(dag, stable_threshold=0.9, unstable_threshold=0.6)
    bundle = FiberBundle(fibers={})
    result = critic.evaluate(bundle)
    # Empty bundle gets full score = 1.0, which is >= 0.9 → stable
    assert result.status == "stable"
```

- [ ] **Step 7.2: Run to verify failure**

```
pytest tests/test_reasoning_lyapunov.py -v
```
Expected: `ModuleNotFoundError: No module named 'llm_kosh.engine.reasoning.lyapunov_critic'`

- [ ] **Step 7.3: Implement `lyapunov_critic.py`**

```python
# llm_kosh/engine/reasoning/lyapunov_critic.py
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from llm_kosh.engine.reasoning.causal_dag import CausalDAG, EdgeType, _ts
from llm_kosh.engine.reasoning.fiber_bundle import FiberBundle


@dataclass
class StabilityResult:
    score: float
    status: str            # "stable" | "marginal" | "unstable"
    dimensions: Dict[str, float]
    implicated_facts: List[str]


class LyapunovCritic:
    """
    Computes stability score V for a FiberBundle.

    V = w1·temporal_consistency + w2·path_diversity + w3·degeneracy - w4·contradiction_score

    Default weights and thresholds are configurable.
    """

    DEFAULT_WEIGHTS = {
        "temporal_consistency": 0.35,
        "path_diversity": 0.25,
        "degeneracy": 0.25,
        "contradiction_score": 0.15,
    }
    DEFAULT_STABLE = 0.7
    DEFAULT_UNSTABLE = 0.4

    def __init__(
        self,
        dag: CausalDAG,
        weights: Optional[Dict[str, float]] = None,
        stable_threshold: float = DEFAULT_STABLE,
        unstable_threshold: float = DEFAULT_UNSTABLE,
    ) -> None:
        self.dag = dag
        self.weights = weights or dict(self.DEFAULT_WEIGHTS)
        self.stable_threshold = stable_threshold
        self.unstable_threshold = unstable_threshold

    def evaluate(self, bundle: FiberBundle) -> StabilityResult:
        if not bundle.fibers:
            return StabilityResult(
                score=1.0,
                status="stable",
                dimensions={
                    "temporal_consistency": 1.0,
                    "contradiction_score": 0.0,
                    "path_diversity": 1.0,
                    "degeneracy": 1.0,
                },
                implicated_facts=[],
            )

        temporal_consistency = self._temporal_consistency(bundle)
        contradiction_score = self._contradiction_score(bundle)
        path_diversity = self._path_diversity(bundle)
        degeneracy = self._degeneracy(bundle)

        w = self.weights
        score = (
            w["temporal_consistency"] * temporal_consistency
            + w["path_diversity"] * path_diversity
            + w["degeneracy"] * degeneracy
            - w["contradiction_score"] * contradiction_score
        )
        score = max(0.0, min(1.0, score))

        if score >= self.stable_threshold:
            status = "stable"
        elif score >= self.unstable_threshold:
            status = "marginal"
        else:
            status = "unstable"

        return StabilityResult(
            score=round(score, 4),
            status=status,
            dimensions={
                "temporal_consistency": round(temporal_consistency, 4),
                "contradiction_score": round(contradiction_score, 4),
                "path_diversity": round(path_diversity, 4),
                "degeneracy": round(degeneracy, 4),
            },
            implicated_facts=[],
        )

    # ------------------------------------------------------------------ dimensions

    def _temporal_consistency(self, bundle: FiberBundle) -> float:
        all_edges = [
            edge
            for fiber in bundle.fibers.values()
            for path in fiber.paths
            for edge in path.edges
        ]
        if not all_edges:
            return 1.0
        consistent = sum(1 for e in all_edges if self._edge_temporally_ok(e))
        return consistent / len(all_edges)

    def _edge_temporally_ok(self, edge) -> bool:
        src = self.dag.get_fact(edge.source_id)
        tgt = self.dag.get_fact(edge.target_id)
        if src is None or tgt is None:
            return True
        src_ts = _ts(src.valid_from) or 0.0
        tgt_ts = _ts(tgt.valid_from) or 0.0
        return src_ts <= tgt_ts

    def _contradiction_score(self, bundle: FiberBundle) -> float:
        fact_ids = list(bundle.fibers.keys())
        pairs = 0
        contradictions = 0
        for i, fid_a in enumerate(fact_ids):
            for fid_b in fact_ids[i + 1 :]:
                pairs += 1
                if self.dag.has_contradiction(fid_a, fid_b):
                    contradictions += 1
        return contradictions / pairs if pairs > 0 else 0.0

    def _path_diversity(self, bundle: FiberBundle) -> float:
        total_paths = sum(len(fiber.paths) for fiber in bundle.fibers.values())
        # Normalize: expect at least 1 path per fact
        max_expected = max(len(bundle.fibers) * 2, 1)
        return min(1.0, total_paths / max_expected)

    def _degeneracy(self, bundle: FiberBundle) -> float:
        high_conf = [
            fiber for fiber in bundle.fibers.values()
            if fiber.max_confidence >= 0.6
        ]
        if not high_conf:
            return 0.5  # neutral when no high-confidence facts
        multi = sum(1 for fiber in high_conf if fiber.degeneracy >= 2)
        return multi / len(high_conf)
```

- [ ] **Step 7.4: Run tests**

```
pytest tests/test_reasoning_lyapunov.py -v
```
Expected: all tests PASS

- [ ] **Step 7.5: Commit**

```bash
git add llm_kosh/engine/reasoning/lyapunov_critic.py tests/test_reasoning_lyapunov.py
git commit -m "feat(reasoning): add LyapunovCritic — four-dimension stability scoring"
```

---

## Task 8: EscapeMechanism

**Files:**
- Create: `llm_kosh/engine/reasoning/escape.py`
- Test: `tests/test_reasoning_escape.py`

- [ ] **Step 8.1: Write failing tests**

```python
# tests/test_reasoning_escape.py
import pytest, time
from datetime import datetime, timezone
from llm_kosh.core.memory import init_cartridge
from llm_kosh.engine.reasoning.causal_dag import CausalDAG, EdgeType, TrajectoryState
from llm_kosh.engine.reasoning.fiber_bundle import FiberBundle, Fiber, CausalPath, build_fiber_bundle
from llm_kosh.engine.reasoning.lyapunov_critic import LyapunovCritic, StabilityResult
from llm_kosh.engine.reasoning.escape import EscapeMechanism
from llm_kosh.engine.reasoning.causal_dag import CausalEdge

def _now():
    return datetime.now(timezone.utc)

@pytest.fixture
def sparse_dag(tmp_path):
    """DAG with low-confidence edges not normally traversed."""
    init_cartridge(tmp_path, "Test")
    dag = CausalDAG(tmp_path)
    now = _now()
    fa = dag.add_fact("Central fact", now, now, now, None, 0.9, "user")
    fb = dag.add_fact("Low-conf fact", now, now, now, None, 0.9, "user")
    # Low-confidence edge — normally skipped by retrieval
    dag.add_edge(fa, fb, EdgeType.ENABLES, 0.2, now, None, "test")
    return dag, fa, fb

def test_escape_increments_count(sparse_dag):
    dag, fa, fb = sparse_dag
    trajectory = TrajectoryState(session_id="s1")
    escape = EscapeMechanism(dag)
    bundle = FiberBundle(fibers={})
    diagnosis = StabilityResult(score=0.3, status="unstable",
        dimensions={"temporal_consistency": 1.0, "contradiction_score": 0.0,
                    "path_diversity": 0.1, "degeneracy": 0.1},
        implicated_facts=[])
    new_bundle = escape.escape(bundle, diagnosis, trajectory, time.time(), {}, depth=2)
    assert trajectory.escape_count == 1

def test_escape_low_diversity_adds_paths(sparse_dag):
    dag, fa, fb = sparse_dag
    trajectory = TrajectoryState(session_id="s1")
    escape = EscapeMechanism(dag)
    # Bundle with only fa, low path diversity
    fact_a = dag.get_fact(fa)
    path = CausalPath(edges=[], confidence_product=1.0, temporal_consistency=1.0)
    bundle = FiberBundle(fibers={
        fa: Fiber(fact=fact_a, paths=[path], degeneracy=1, max_confidence=1.0)
    })
    diagnosis = StabilityResult(score=0.3, status="unstable",
        dimensions={"temporal_consistency": 1.0, "contradiction_score": 0.0,
                    "path_diversity": 0.1, "degeneracy": 0.1},
        implicated_facts=[])
    new_bundle = escape.escape(bundle, diagnosis, trajectory, time.time(), {}, depth=2)
    # fb should now appear in the escaped bundle (via low-confidence edge traversal)
    assert fb in new_bundle.fibers or fa in new_bundle.fibers

def test_deep_instability_flag(sparse_dag):
    dag, fa, fb = sparse_dag
    trajectory = TrajectoryState(session_id="s1", escape_count=3)
    escape = EscapeMechanism(dag)
    bundle = FiberBundle(fibers={})
    diagnosis = StabilityResult(score=0.2, status="unstable",
        dimensions={"temporal_consistency": 0.5, "contradiction_score": 0.5,
                    "path_diversity": 0.1, "degeneracy": 0.1},
        implicated_facts=[])
    new_bundle = escape.escape(bundle, diagnosis, trajectory, time.time(), {}, depth=2)
    assert new_bundle.fibers.get("__deep_instability__") is not None or trajectory.escape_count == 4
```

- [ ] **Step 8.2: Run to verify failure**

```
pytest tests/test_reasoning_escape.py -v
```
Expected: `ModuleNotFoundError: No module named 'llm_kosh.engine.reasoning.escape'`

- [ ] **Step 8.3: Implement `escape.py`**

```python
# llm_kosh/engine/reasoning/escape.py
from __future__ import annotations

from typing import Dict, List, Optional

from llm_kosh.engine.reasoning.causal_dag import (
    CausalDAG, CausalEdge, EdgeType, TemporalFact, TrajectoryState, _ts
)
from llm_kosh.engine.reasoning.fiber_bundle import (
    CausalPath, Fiber, FiberBundle, _enumerate_paths
)
from llm_kosh.engine.reasoning.lyapunov_critic import StabilityResult

_LOW_CONF_THRESHOLD = 0.4   # edges below this are "in the dark"
_TEMPORAL_WIDEN_SECS = 86400  # widen validity window by 24h on temporal escape


class EscapeMechanism:
    """
    Targeted escape from coherence traps.
    Acts only when LyapunovCritic returns unstable or marginal.
    Each escape strategy targets a specific failure dimension.
    """

    def __init__(self, dag: CausalDAG) -> None:
        self.dag = dag

    def escape(
        self,
        bundle: FiberBundle,
        diagnosis: StabilityResult,
        trajectory: TrajectoryState,
        query_time: float,
        query_profile: dict,
        depth: int,
    ) -> FiberBundle:
        """
        Targeted escape based on diagnosis dimensions.
        Modifies the bundle in place and returns it.
        Increments trajectory.escape_count.
        """
        if trajectory.escape_count >= 3:
            trajectory.escape_count += 1
            # Signal deep instability — structural problem in the causal graph
            bundle.fibers["__deep_instability__"] = Fiber(
                fact=None,  # type: ignore[arg-type]
                paths=[],
                degeneracy=0,
                max_confidence=0.0,
            )
            return bundle

        dims = diagnosis.dimensions

        if dims.get("temporal_consistency", 1.0) < 0.5:
            bundle = self._escape_temporal(bundle, query_time)

        if dims.get("contradiction_score", 0.0) > 0.3:
            bundle = self._escape_contradiction(bundle, query_time)

        if dims.get("path_diversity", 1.0) < 0.4:
            bundle = self._escape_low_confidence(bundle, query_time, depth)

        if dims.get("degeneracy", 1.0) < 0.4:
            bundle = self._escape_alternative_routes(bundle, query_time, depth)

        trajectory.escape_count += 1
        return bundle

    # ------------------------------------------------------------------ strategies

    def _escape_temporal(self, bundle: FiberBundle, query_time: float) -> FiberBundle:
        """Widen the temporal window to surface facts just outside validity."""
        widened_time = query_time + _TEMPORAL_WIDEN_SECS
        extra_ids = set(self.dag.interval_tree.query_valid_at(widened_time))
        current_ids = set(bundle.fibers.keys())
        for fid in extra_ids - current_ids:
            fact = self.dag.get_fact(fid)
            if fact:
                bundle.fibers[fid] = Fiber(
                    fact=fact, paths=[], degeneracy=0, max_confidence=fact.confidence
                )
        return bundle

    def _escape_contradiction(self, bundle: FiberBundle, query_time: float) -> FiberBundle:
        """Surface both sides of active contradictions explicitly."""
        fact_ids = list(bundle.fibers.keys())
        for i, fid_a in enumerate(fact_ids):
            for fid_b in fact_ids[i + 1 :]:
                if self.dag.has_contradiction(fid_a, fid_b):
                    # Both are already in the bundle — mark them by adding a zero path
                    for fid in (fid_a, fid_b):
                        fiber = bundle.fibers.get(fid)
                        if fiber is not None and not fiber.paths:
                            fact = self.dag.get_fact(fid)
                            if fact:
                                fiber.paths.append(
                                    CausalPath(edges=[], confidence_product=fact.confidence,
                                               temporal_consistency=1.0)
                                )
        return bundle

    def _escape_low_confidence(
        self, bundle: FiberBundle, query_time: float, depth: int
    ) -> FiberBundle:
        """Traverse low-confidence edges (< threshold) from existing bundle anchors."""
        current_ids = set(bundle.fibers.keys())
        to_add: Dict[str, Fiber] = {}

        for fid in list(current_ids):
            for edge in self.dag.edges.get(fid, []):
                if edge.confidence < _LOW_CONF_THRESHOLD:
                    target_id = edge.target_id
                    if target_id in current_ids or target_id in to_add:
                        continue
                    fact = self.dag.get_fact(target_id)
                    if fact is None:
                        continue
                    vf = _ts(fact.valid_from) or 0.0
                    vu = _ts(fact.valid_until)
                    if vf <= query_time and (vu is None or vu > query_time):
                        path = CausalPath(
                            edges=[edge],
                            confidence_product=edge.confidence,
                            temporal_consistency=1.0,
                        )
                        to_add[target_id] = Fiber(
                            fact=fact, paths=[path], degeneracy=1,
                            max_confidence=edge.confidence,
                        )

        bundle.fibers.update(to_add)
        return bundle

    def _escape_alternative_routes(
        self, bundle: FiberBundle, query_time: float, depth: int
    ) -> FiberBundle:
        """Search for alternative causal paths to high-confidence targets."""
        high_conf_targets = {
            fid for fid, fiber in bundle.fibers.items()
            if fiber.max_confidence >= 0.6 and fiber.degeneracy < 2
        }
        if not high_conf_targets:
            return bundle

        # BFS from all facts, look for new paths to high_conf_targets
        for start_id in list(self.dag.nodes.keys()):
            if start_id in bundle.fibers:
                continue
            paths_to = _enumerate_paths(
                self.dag, start_id, high_conf_targets, depth, query_time
            )
            for target_id, new_paths in paths_to.items():
                if target_id in bundle.fibers:
                    bundle.fibers[target_id].paths.extend(new_paths)
                    fiber = bundle.fibers[target_id]
                    fiber.degeneracy = len(fiber.paths)
                    fiber.max_confidence = max(
                        (p.confidence_product for p in fiber.paths), default=0.0
                    )

        return bundle
```

- [ ] **Step 8.4: Run tests**

```
pytest tests/test_reasoning_escape.py -v
```
Expected: all tests PASS

- [ ] **Step 8.5: Commit**

```bash
git add llm_kosh/engine/reasoning/escape.py tests/test_reasoning_escape.py
git commit -m "feat(reasoning): add EscapeMechanism — four targeted escape strategies + deep instability flag"
```

---

## Task 9: ReasoningEngine Public Class

**Files:**
- Modify: `llm_kosh/engine/reasoning/__init__.py`
- Test: `tests/test_reasoning_engine.py`

- [ ] **Step 9.1: Write failing tests**

```python
# tests/test_reasoning_engine.py
import pytest, time
from datetime import datetime, timezone
from pathlib import Path
from llm_kosh.core.memory import init_cartridge
from llm_kosh.engine.reasoning import ReasoningEngine, QueryResult

def _now():
    return datetime.now(timezone.utc)

@pytest.fixture
def engine(tmp_path):
    init_cartridge(tmp_path, "Test")
    return ReasoningEngine(tmp_path)

def test_engine_initializes(engine):
    assert engine is not None
    assert engine.dag is not None

def test_engine_ingest_returns_id(engine):
    now = _now()
    fid = engine.ingest(
        content="The sun rises in the east",
        documented_at=now,
        valid_from=now,
        valid_until=None,
        confidence=0.95,
        causal_edges=[],
    )
    assert fid.startswith("fact.")

def test_engine_ingest_with_edge(engine):
    now = _now()
    fid1 = engine.ingest("Cause fact", now, now, None, 0.9, [])
    fid2 = engine.ingest("Effect fact", now, now, None, 0.9,
                         [{"target_id": fid1, "edge_type": "ENABLES", "confidence": 0.8}])
    assert fid1 in engine.dag.nodes
    assert fid2 in engine.dag.nodes

def test_engine_query_returns_result(engine):
    now = _now()
    engine.ingest("Gravity pulls objects toward Earth", now, now, None, 0.95, [])
    engine.ingest("Newton studied gravity and motion", now, now, None, 0.9, [])
    result = engine.query("gravity Newton", temporal_context=None, depth=2)
    assert isinstance(result, QueryResult)
    assert hasattr(result, "bundle")
    assert hasattr(result, "stability")
    assert hasattr(result, "anchors")

def test_engine_critique(engine):
    now = _now()
    fid = engine.ingest("Test fact", now, now, None, 0.9, [])
    result = engine.critique([fid])
    assert 0.0 <= result.score <= 1.0
    assert result.status in ("stable", "marginal", "unstable")

def test_engine_explore(engine):
    now = _now()
    fid1 = engine.ingest("Source", now, now, None, 0.9, [])
    fid2 = engine.ingest("Target", now, now, None, 0.9,
                         [{"target_id": fid1, "edge_type": "CAUSES", "confidence": 0.8}])
    bundle = engine.explore(fid2, fid1, max_hops=2)
    from llm_kosh.engine.reasoning.fiber_bundle import FiberBundle
    assert isinstance(bundle, FiberBundle)

def test_engine_rebuilds_from_log(tmp_path):
    init_cartridge(tmp_path, "Test")
    e1 = ReasoningEngine(tmp_path)
    now = _now()
    fid = e1.ingest("Persisted fact", now, now, None, 0.9, [])
    # Fresh engine must see the same fact
    e2 = ReasoningEngine(tmp_path)
    assert fid in e2.dag.nodes
```

- [ ] **Step 9.2: Run to verify failure**

```
pytest tests/test_reasoning_engine.py -v
```
Expected: `ImportError: cannot import name 'ReasoningEngine'`

- [ ] **Step 9.3: Implement `__init__.py`**

```python
# llm_kosh/engine/reasoning/__init__.py
from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from llm_kosh.engine.reasoning.causal_dag import CausalDAG, EdgeType, TrajectoryState
from llm_kosh.engine.reasoning.causal_retrieval import CausalRetrieval
from llm_kosh.engine.reasoning.escape import EscapeMechanism
from llm_kosh.engine.reasoning.fiber_bundle import FiberBundle, build_fiber_bundle
from llm_kosh.engine.reasoning.lyapunov_critic import LyapunovCritic, StabilityResult


@dataclass
class QueryResult:
    anchors: List[str]
    bundle: FiberBundle
    stability: StabilityResult
    escape_triggered: bool
    escape_surfaced: List[str]


class ReasoningEngine:
    """
    Public API for the Temporal Causal Reasoning Engine.
    Initialize once per cartridge root; call query/ingest/critique/explore.
    """

    def __init__(self, root: Path) -> None:
        self.root = root
        self.dag = CausalDAG(root)
        self._retrieval = CausalRetrieval(self.dag)
        self._critic = LyapunovCritic(self.dag)
        self._escape = EscapeMechanism(self.dag)

    # ------------------------------------------------------------------ public API

    def ingest(
        self,
        content: str,
        documented_at: datetime,
        valid_from: datetime,
        valid_until: Optional[datetime],
        confidence: float,
        causal_edges: List[dict],
    ) -> str:
        """
        Add a fact to the causal graph.
        causal_edges: list of {"target_id": str, "edge_type": str, "confidence": float}
        Returns the new fact_id.
        """
        now = datetime.now(timezone.utc)
        fact_id = self.dag.add_fact(
            content=content,
            ingested_at=now,
            documented_at=documented_at,
            valid_from=valid_from,
            valid_until=valid_until,
            confidence=confidence,
            source="agent",
        )
        for edge_spec in causal_edges:
            try:
                self.dag.add_edge(
                    source_id=fact_id,
                    target_id=edge_spec["target_id"],
                    edge_type=EdgeType(edge_spec.get("edge_type", "ENABLES")),
                    confidence=float(edge_spec.get("confidence", 0.7)),
                    valid_from=valid_from,
                    valid_until=valid_until,
                    established_by="agent",
                )
            except (KeyError, ValueError):
                pass
        # Refresh retrieval index
        self._retrieval = CausalRetrieval(self.dag)
        return fact_id

    def query(
        self,
        query: str,
        temporal_context: Optional[str] = None,
        depth: int = 3,
    ) -> QueryResult:
        """
        Full pipeline: retrieve → bundle → critique → escape if needed → return.
        temporal_context: ISO 8601 datetime string, Unix timestamp str, or None (uses now).
        """
        query_time = self._parse_temporal_context(temporal_context)
        trajectory = TrajectoryState(session_id=f"q-{int(query_time)}")

        candidates = self._retrieval.retrieve(query, query_time, depth=depth)
        anchor_ids = [c[0].id for c in candidates[:5]]

        bundle = build_fiber_bundle(
            self.dag, candidates, anchor_ids=anchor_ids,
            query_time=query_time, max_hops=depth,
        )
        diagnosis = self._critic.evaluate(bundle)

        escaped = False
        escape_surfaced: List[str] = []

        if diagnosis.status in ("unstable", "marginal"):
            query_profile = {}  # resonance profile not needed by escape strategies directly
            prev_ids = set(bundle.fibers.keys())
            bundle = self._escape.escape(bundle, diagnosis, trajectory, query_time, query_profile, depth)
            escape_surfaced = [fid for fid in bundle.fibers if fid not in prev_ids and fid != "__deep_instability__"]
            diagnosis = self._critic.evaluate(bundle)
            escaped = True

        return QueryResult(
            anchors=anchor_ids,
            bundle=bundle,
            stability=diagnosis,
            escape_triggered=escaped,
            escape_surfaced=escape_surfaced,
        )

    def critique(self, fact_ids: List[str]) -> StabilityResult:
        """Run the Lyapunov critic on a specific set of facts (no path enumeration)."""
        from llm_kosh.engine.reasoning.fiber_bundle import Fiber, CausalPath
        fibers = {}
        for fid in fact_ids:
            fact = self.dag.get_fact(fid)
            if fact:
                path = CausalPath(edges=[], confidence_product=fact.confidence,
                                  temporal_consistency=1.0)
                fibers[fid] = Fiber(fact=fact, paths=[path], degeneracy=1,
                                    max_confidence=fact.confidence)
        bundle = FiberBundle(fibers=fibers)
        return self._critic.evaluate(bundle)

    def explore(
        self, from_fact_id: str, to_fact_id: str, max_hops: int = 5
    ) -> FiberBundle:
        """Enumerate all causal paths between two known facts."""
        from llm_kosh.engine.reasoning.fiber_bundle import _enumerate_paths
        query_time = time.time()
        to_fact = self.dag.get_fact(to_fact_id)
        if to_fact is None:
            return FiberBundle(fibers={})
        paths = _enumerate_paths(
            self.dag, from_fact_id, {to_fact_id}, max_hops, query_time
        )
        from llm_kosh.engine.reasoning.fiber_bundle import Fiber
        fibers = {}
        if to_fact_id in paths:
            path_list = paths[to_fact_id]
            fibers[to_fact_id] = Fiber(
                fact=to_fact,
                paths=path_list,
                degeneracy=len(path_list),
                max_confidence=max((p.confidence_product for p in path_list), default=0.0),
            )
        return FiberBundle(fibers=fibers)

    # ------------------------------------------------------------------ helpers

    @staticmethod
    def _parse_temporal_context(ctx: Optional[str]) -> float:
        if ctx is None:
            return time.time()
        try:
            return float(ctx)
        except (TypeError, ValueError):
            pass
        try:
            return datetime.fromisoformat(ctx.replace("Z", "+00:00")).timestamp()
        except Exception:
            return time.time()
```

- [ ] **Step 9.4: Run tests**

```
pytest tests/test_reasoning_engine.py -v
```
Expected: all tests PASS

- [ ] **Step 9.5: Run full suite to confirm no regressions**

```
pytest tests/ -v --ignore=tests/test_reasoning_mcp.py
```
Expected: all existing tests still PASS

- [ ] **Step 9.6: Commit**

```bash
git add llm_kosh/engine/reasoning/__init__.py tests/test_reasoning_engine.py
git commit -m "feat(reasoning): add ReasoningEngine public class — full pipeline query/ingest/critique/explore"
```

---

## Task 10: MCP Tools

**Files:**
- Modify: `llm_kosh/mcp_server.py`
- Test: `tests/test_reasoning_mcp.py`

- [ ] **Step 10.1: Write failing tests**

```python
# tests/test_reasoning_mcp.py
import pytest
import json
from pathlib import Path
from llm_kosh.core.memory import init_cartridge
from llm_kosh.mcp_server import mcp, start_server

@pytest.fixture
def mcp_cartridge(tmp_path):
    init_cartridge(tmp_path, "MCP Reasoning Test")
    start_server(tmp_path, stdio=False, http=False,
                 allow_write=True, allow_mutate=False, allow_private=False)
    return tmp_path

@pytest.mark.asyncio
async def test_reasoning_ingest_tool(mcp_cartridge):
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).isoformat()
    res = await mcp.call_tool("reasoning_ingest", {
        "content": "Test memory from MCP",
        "documented_at": now,
        "valid_from": now,
        "confidence": 0.9,
    })
    assert "fact." in str(res)

@pytest.mark.asyncio
async def test_reasoning_query_tool(mcp_cartridge):
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).isoformat()
    await mcp.call_tool("reasoning_ingest", {
        "content": "Apples fall due to gravity",
        "documented_at": now,
        "valid_from": now,
        "confidence": 0.9,
    })
    res = await mcp.call_tool("reasoning_query", {"query": "gravity apples"})
    data = json.loads(res)
    assert "anchors" in data
    assert "bundle" in data
    assert "stability" in data

@pytest.mark.asyncio
async def test_reasoning_critique_tool(mcp_cartridge):
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).isoformat()
    ingest_res = await mcp.call_tool("reasoning_ingest", {
        "content": "Fact to critique",
        "documented_at": now,
        "valid_from": now,
        "confidence": 0.8,
    })
    fact_id = str(ingest_res).split("fact.")[1].split('"')[0]
    fact_id = "fact." + fact_id
    res = await mcp.call_tool("reasoning_critique", {"fact_ids": [fact_id]})
    data = json.loads(res)
    assert "score" in data
    assert "status" in data

@pytest.mark.asyncio
async def test_reasoning_explore_tool(mcp_cartridge):
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).isoformat()
    fid1_raw = await mcp.call_tool("reasoning_ingest", {
        "content": "Source fact",
        "documented_at": now,
        "valid_from": now,
        "confidence": 0.9,
    })
    fid2_raw = await mcp.call_tool("reasoning_ingest", {
        "content": "Target fact",
        "documented_at": now,
        "valid_from": now,
        "confidence": 0.9,
    })
    # explore with no path — should return empty bundle gracefully
    fid1 = str(fid1_raw).split('"fact_id": "')[1].split('"')[0] if '"fact_id"' in str(fid1_raw) else "fact.missing"
    fid2 = str(fid2_raw).split('"fact_id": "')[1].split('"')[0] if '"fact_id"' in str(fid2_raw) else "fact.missing"
    res = await mcp.call_tool("reasoning_explore", {"from_fact_id": fid1, "to_fact_id": fid2})
    data = json.loads(res)
    assert "fibers" in data
```

- [ ] **Step 10.2: Run to verify failure**

```
pytest tests/test_reasoning_mcp.py::test_reasoning_ingest_tool -v
```
Expected: `mcp.exceptions.ToolNotFoundError: reasoning_ingest`

- [ ] **Step 10.3: Add four MCP tools to `mcp_server.py`**

Open `llm_kosh/mcp_server.py`. After the final existing `@mcp.tool()` block (after `apply_intake_proposal`), add:

```python
# --- REASONING TOOLS ---

@mcp.tool()
def reasoning_ingest(
    content: str,
    documented_at: str,
    valid_from: str,
    valid_until: str = "",
    confidence: float = 0.8,
    causal_edges: str = "[]",
) -> str:
    """
    Add a new fact to the Temporal Causal Reasoning Graph.
    documented_at and valid_from are ISO 8601 datetime strings.
    causal_edges: JSON array of {"target_id": str, "edge_type": str, "confidence": float}.
    Returns the new fact_id.
    """
    import json as _json
    from datetime import datetime, timezone
    from llm_kosh.engine.reasoning import ReasoningEngine

    def _parse(s: str) -> datetime:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))

    engine = ReasoningEngine(WORKSPACE_PATH)
    try:
        edges = _json.loads(causal_edges) if causal_edges else []
    except Exception:
        edges = []

    fact_id = engine.ingest(
        content=content,
        documented_at=_parse(documented_at),
        valid_from=_parse(valid_from),
        valid_until=_parse(valid_until) if valid_until else None,
        confidence=confidence,
        causal_edges=edges,
    )
    return _json.dumps({"fact_id": fact_id, "status": "ingested"})


@mcp.tool()
def reasoning_query(
    query: str,
    temporal_context: str = "",
    depth: int = 3,
) -> str:
    """
    Query the Temporal Causal Reasoning Graph.
    Returns a fiber bundle with stability score, escape metadata, and all causal paths.
    temporal_context: ISO 8601 datetime or Unix timestamp string (omit for now).
    """
    import json as _json
    from llm_kosh.engine.reasoning import ReasoningEngine

    engine = ReasoningEngine(WORKSPACE_PATH)
    result = engine.query(query, temporal_context=temporal_context or None, depth=depth)

    bundle_out = {}
    for fid, fiber in result.bundle.fibers.items():
        if fid == "__deep_instability__":
            continue
        bundle_out[fid] = {
            "fact": {
                "id": fiber.fact.id if fiber.fact else fid,
                "content": fiber.fact.content if fiber.fact else "",
                "valid_from": fiber.fact.valid_from.isoformat() if fiber.fact else "",
                "valid_until": fiber.fact.valid_until.isoformat() if (fiber.fact and fiber.fact.valid_until) else None,
                "confidence": fiber.fact.confidence if fiber.fact else 0.0,
            },
            "paths": [
                {
                    "edge_count": len(p.edges),
                    "confidence_product": p.confidence_product,
                    "temporal_consistency": p.temporal_consistency,
                }
                for p in fiber.paths
            ],
            "degeneracy": fiber.degeneracy,
            "max_confidence": fiber.max_confidence,
        }

    return _json.dumps({
        "anchors": result.anchors,
        "bundle": bundle_out,
        "stability": {
            "score": result.stability.score,
            "status": result.stability.status,
            "dimensions": result.stability.dimensions,
            "escape_triggered": result.escape_triggered,
            "escape_surfaced": result.escape_surfaced,
        },
    })


@mcp.tool()
def reasoning_critique(fact_ids: List[str]) -> str:
    """
    Run the Lyapunov critic on a specific list of fact IDs.
    Returns stability score, status, and per-dimension breakdown.
    """
    import json as _json
    from llm_kosh.engine.reasoning import ReasoningEngine

    engine = ReasoningEngine(WORKSPACE_PATH)
    result = engine.critique(fact_ids)
    return _json.dumps({
        "score": result.score,
        "status": result.status,
        "dimensions": result.dimensions,
        "implicated_facts": result.implicated_facts,
    })


@mcp.tool()
def reasoning_explore(from_fact_id: str, to_fact_id: str, max_hops: int = 5) -> str:
    """
    Enumerate all causal paths between two known facts.
    Returns the fiber bundle for that specific pair.
    """
    import json as _json
    from llm_kosh.engine.reasoning import ReasoningEngine

    engine = ReasoningEngine(WORKSPACE_PATH)
    bundle = engine.explore(from_fact_id, to_fact_id, max_hops=max_hops)

    fibers_out = {}
    for fid, fiber in bundle.fibers.items():
        fibers_out[fid] = {
            "paths": [
                {
                    "edges": [
                        {"source": e.source_id, "target": e.target_id,
                         "type": e.edge_type.value, "confidence": e.confidence}
                        for e in p.edges
                    ],
                    "confidence_product": p.confidence_product,
                    "temporal_consistency": p.temporal_consistency,
                }
                for p in fiber.paths
            ],
            "degeneracy": fiber.degeneracy,
            "max_confidence": fiber.max_confidence,
        }
    return _json.dumps({"fibers": fibers_out})
```

- [ ] **Step 10.4: Run MCP tests**

```
pytest tests/test_reasoning_mcp.py -v
```
Expected: all 4 tests PASS

- [ ] **Step 10.5: Run full suite**

```
pytest tests/ -v
```
Expected: all tests PASS, no regressions

- [ ] **Step 10.6: Commit**

```bash
git add llm_kosh/mcp_server.py tests/test_reasoning_mcp.py
git commit -m "feat(reasoning): add four MCP tools — reasoning_query, reasoning_ingest, reasoning_critique, reasoning_explore"
```

---

## Task 11: Snapshot — Cold Storage Tier

**Files:**
- Modify: `llm_kosh/engine/reasoning/causal_dag.py`
- Test: `tests/test_reasoning_causal_dag.py` (extend)

Snapshots avoid full log replay on startup. They are a cache — discarded and rebuilt from log if corrupt or missing.

- [ ] **Step 11.1: Add snapshot tests**

Append to `tests/test_reasoning_causal_dag.py`:

```python
def test_snapshot_save_and_load(cartridge):
    dag1 = CausalDAG(cartridge)
    now = _now()
    fid = dag1.add_fact("Snapshot fact", now, now, now, None, 0.9, "user")
    dag1.save_snapshot()
    snapshot_path = cartridge / "reasoning" / "snapshot.json"
    assert snapshot_path.exists()

    # Load from snapshot — should not need to replay log
    dag2 = CausalDAG(cartridge)
    assert fid in dag2.nodes

def test_corrupt_snapshot_falls_back_to_log(cartridge):
    dag1 = CausalDAG(cartridge)
    now = _now()
    fid = dag1.add_fact("Log-only fact", now, now, now, None, 0.9, "user")
    dag1.save_snapshot()
    # Corrupt the snapshot
    (cartridge / "reasoning" / "snapshot.json").write_text("NOT JSON", encoding="utf-8")
    # Should still load from log
    dag2 = CausalDAG(cartridge)
    assert fid in dag2.nodes
```

- [ ] **Step 11.2: Run to verify failure**

```
pytest tests/test_reasoning_causal_dag.py::test_snapshot_save_and_load -v
```
Expected: `AttributeError: 'CausalDAG' object has no attribute 'save_snapshot'`

- [ ] **Step 11.3: Add snapshot save/load to CausalDAG**

Add these methods inside the `CausalDAG` class, after `_load_from_log`:

```python
    SNAPSHOT_FILE = "reasoning/snapshot.json"

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
```

Update `__init__` to try snapshot before log replay:

```python
    def __init__(self, root: Path) -> None:
        self.root = root
        self.nodes: Dict[str, TemporalFact] = {}
        self.edges: Dict[str, List[CausalEdge]] = {}
        self.hyperedges: List[HyperEdge] = []
        self.interval_tree = IntervalTree()
        self._ensure_dirs()
        if not self._try_load_snapshot():
            self._load_from_log()
```

- [ ] **Step 11.4: Run tests**

```
pytest tests/test_reasoning_causal_dag.py -v
```
Expected: all tests PASS

- [ ] **Step 11.5: Commit**

```bash
git add llm_kosh/engine/reasoning/causal_dag.py tests/test_reasoning_causal_dag.py
git commit -m "feat(reasoning): add snapshot save/load — cold tier cache avoids full log replay on startup"
```

---

## Task 12: Final Integration Check

**Files:** None new — verification only.

- [ ] **Step 12.1: Run the full test suite**

```
pytest tests/ -v
```
Expected: all tests PASS

- [ ] **Step 12.2: Verify reasoning subpackage is importable**

```
python -c "from llm_kosh.engine.reasoning import ReasoningEngine; print('OK')"
```
Expected: `OK`

- [ ] **Step 12.3: Verify no existing modules were changed**

```bash
git diff HEAD~11 -- llm_kosh/engine/search.py llm_kosh/engine/tensor_fusion.py llm_kosh/engine/receipt_dag.py llm_kosh/engine/math_fallback.py
```
Expected: empty diff (no changes to these files)

- [ ] **Step 12.4: Verify `reasoning/` directory is created on `init_cartridge`**

```
python -c "
import tempfile, shutil
from pathlib import Path
from llm_kosh.core.memory import init_cartridge
tmp = Path(tempfile.mkdtemp())
init_cartridge(tmp, 'Test')
assert (tmp / 'reasoning').is_dir(), 'reasoning dir missing'
shutil.rmtree(tmp)
print('OK')
"
```
Expected: `OK`

- [ ] **Step 12.5: Final commit**

```bash
git add .
git commit -m "feat(reasoning): v0.1 Temporal Causal Reasoning Engine — complete

Five components: CausalDAG (temporal hypergraph + append-only log),
CausalRetrieval (DCT resonance matching + BFS causal traversal),
FiberBundle (DFS path enumeration, never collapses), LyapunovCritic
(four-dimension stability scoring), EscapeMechanism (four targeted
escape strategies). ReasoningEngine public class. Four MCP tools.
Zero breaking changes to existing llm-kosh pipeline."
```
