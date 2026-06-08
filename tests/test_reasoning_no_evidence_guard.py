from datetime import datetime, timezone
from pathlib import Path

from llm_kosh.engine.reasoning import ReasoningEngine


def dt(s: str):
    return datetime.fromisoformat(s.replace('Z', '+00:00'))


def test_unrelated_query_abstains_with_no_evidence(tmp_path: Path):
    eng = ReasoningEngine(tmp_path)
    eng.dag.add_fact(
        content='Remote work policy allows three days from home.',
        ingested_at=dt('2026-01-01T00:00:00+00:00'),
        documented_at=dt('2026-01-01T00:00:00+00:00'),
        valid_from=dt('2026-01-01T00:00:00+00:00'),
        valid_until=None,
        confidence=0.9,
        source='test',
    )
    eng._retrieval._build_resonance_index()
    res = eng.query('banana moonbeam payroll dragon', temporal_context='2026-02-01T00:00:00+00:00')
    assert res.stability.status == 'no_evidence'
    assert res.stability.abstain is True
    assert not res.bundle.fibers
