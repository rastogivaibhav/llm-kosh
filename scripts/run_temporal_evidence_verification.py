#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from llm_kosh.engine.reasoning import ReasoningEngine
from llm_kosh.engine.reasoning.temporal_evidence import TemporalEvidenceEngine


def dt(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def make_engine(root: Path) -> ReasoningEngine:
    engine = ReasoningEngine(root)
    old = engine.ingest(
        "Policy v1: remote work is allowed for the team.",
        dt("2026-02-01T00:00:00Z"),
        dt("2026-02-01T00:00:00Z"),
        dt("2026-04-01T00:00:00Z"),
        0.9,
        [],
    )
    new = engine.ingest(
        "Policy v2: remote work is not allowed for the team.",
        dt("2026-04-01T00:00:00Z"),
        dt("2026-04-01T00:00:00Z"),
        None,
        0.95,
        [],
    )
    engine.add_edge_at(new, old, "SUPERSEDES", 0.95, dt("2026-04-01T00:00:00Z"))
    a = engine.ingest("Config file expanded beyond parser limit.", dt("2026-05-01T12:00:00Z"), dt("2026-05-01T12:00:00Z"), None, 0.9, [])
    b = engine.ingest("Parser failed while reading generated configuration.", dt("2026-05-01T12:05:00Z"), dt("2026-05-01T12:05:00Z"), None, 0.9, [])
    c = engine.ingest("Service degraded after the parser failed.", dt("2026-05-01T12:10:00Z"), dt("2026-05-01T12:10:00Z"), None, 0.9, [])
    engine.add_edge_at(a, b, "CAUSES", 0.8, dt("2026-05-01T12:05:00Z"))
    engine.add_edge_at(b, c, "CAUSES", 0.85, dt("2026-05-01T12:10:00Z"))
    return engine


def main() -> int:
    out_dir = Path("reports/temporal_evidence")
    out_dir.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory() as td:
        engine = make_engine(Path(td))
        tee = TemporalEvidenceEngine()
        audit = tee.audit_dag(engine.dag)
        feb = engine.query("remote work allowed policy", "2026-02-15T00:00:00Z")
        may = engine.query("remote work allowed policy", "2026-05-15T00:00:00Z")
        constraints = tee.infer_constraints_from_edges(engine.dag)
        result = {
            "audit": audit.__dict__,
            "february_fibers": list(feb.bundle.fibers.keys()),
            "may_fibers": list(may.bundle.fibers.keys()),
            "constraint_count": len(constraints),
            "constraints": [c.to_dict() for c in constraints],
            "interpretation": {
                "time_needed": True,
                "timestamp_only": False,
                "temporal_evidence_needed": ["exact", "approximate", "relative", "versioned", "causal_order", "metadata"],
            },
        }
        # dataclass contains enum/list fields; use markdown as stable human output and custom json fallback
        (out_dir / "TEMPORAL_EVIDENCE_AUDIT.md").write_text(audit.to_markdown(), encoding="utf-8")
        (out_dir / "temporal_evidence_verification.json").write_text(
            json.dumps(result, default=str, indent=2), encoding="utf-8"
        )
    print("Wrote reports/temporal_evidence/TEMPORAL_EVIDENCE_AUDIT.md")
    print("Wrote reports/temporal_evidence/temporal_evidence_verification.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
