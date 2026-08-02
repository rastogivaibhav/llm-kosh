from datetime import datetime, timezone

import pytest

from llm_kosh.core.memory import add_memory, init_cartridge
from llm_kosh.daemon import job_sync_reasoning_graph
from llm_kosh.engine.reasoning import ReasoningEngine
from llm_kosh.engine.reasoning.causal_dag import MAX_FACT_CONTENT_CHARS


def test_reasoning_rejects_document_sized_facts(tmp_path):
    engine = ReasoningEngine(tmp_path)
    now = datetime.now(timezone.utc)
    with pytest.raises(ValueError, match="store the full source as evidence"):
        engine.ingest("x" * (MAX_FACT_CONTENT_CHARS + 1), now, now, None, 0.8, [])


def test_daemon_sync_does_not_copy_complete_memory_body(tmp_path):
    init_cartridge(tmp_path, "Bounded reasoning")
    huge_marker = "WHOLE_DOCUMENT_MARKER"
    add_memory(
        tmp_path,
        kind="note",
        title="Bounded graph fact",
        body="Short summary. " + ("padding " * 2_000) + huge_marker,
    )
    success, _ = job_sync_reasoning_graph(tmp_path)
    assert success
    engine = ReasoningEngine(tmp_path)
    assert len(engine.dag.nodes) == 1
    fact = next(iter(engine.dag.nodes.values()))
    assert len(fact.content) <= MAX_FACT_CONTENT_CHARS
    assert huge_marker not in fact.content
