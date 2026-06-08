"""Tests for job_sync_reasoning_graph daemon job."""
import pytest
from pathlib import Path
from tempfile import TemporaryDirectory
from datetime import datetime, timezone

from llm_kosh.core.memory import init_cartridge, add_memory
from llm_kosh.daemon import job_sync_reasoning_graph, JOBS
from llm_kosh.engine.reasoning import ReasoningEngine


def test_job_registered_in_jobs_dict():
    assert "sync_reasoning_graph" in JOBS


def test_job_registered_in_enabled_defaults():
    from llm_kosh.daemon import _get_enabled_jobs
    with TemporaryDirectory() as t:
        root = Path(t)
        init_cartridge(root, "test")
        enabled = _get_enabled_jobs(root)
    assert "sync_reasoning_graph" in enabled


def test_sync_ingests_new_memories():
    with TemporaryDirectory() as t:
        root = Path(t)
        init_cartridge(root, "test")
        add_memory(root, kind="decision", title="Use PostgreSQL",
                   body="We chose PostgreSQL for JSONB support.", project="auth")
        add_memory(root, kind="note", title="OAuth2 done",
                   body="OAuth2 integration completed on Tuesday.", project="auth")

        success, msg = job_sync_reasoning_graph(root)
        assert success
        assert "2" in msg  # 2 new memories synced

        engine = ReasoningEngine(root)
        assert len(engine.dag.nodes) >= 2


def test_sync_is_incremental():
    """Second run syncs 0 new memories if nothing changed."""
    with TemporaryDirectory() as t:
        root = Path(t)
        init_cartridge(root, "test")
        add_memory(root, kind="note", title="First note", body="Content A.", project="p")

        job_sync_reasoning_graph(root)  # first run
        success, msg = job_sync_reasoning_graph(root)  # second run

        assert success
        assert "0" in msg  # 0 new on second run


def test_sync_picks_up_new_memory_after_first_run():
    with TemporaryDirectory() as t:
        root = Path(t)
        init_cartridge(root, "test")
        add_memory(root, kind="note", title="Memory A", body="Content A.", project="p")
        job_sync_reasoning_graph(root)  # first run syncs 1

        add_memory(root, kind="note", title="Memory B", body="Content B.", project="p")
        success, msg = job_sync_reasoning_graph(root)  # second run syncs 1 more

        assert success
        assert "1" in msg
