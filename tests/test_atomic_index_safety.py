import sqlite3

import pytest

from llm_kosh.core.memory import add_memory, init_cartridge
from llm_kosh.engine import search
from llm_kosh.engine.commands import status


def _count(db_path):
    with sqlite3.connect(str(db_path)) as conn:
        return conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0]


def test_failed_index_activation_preserves_previous_database(tmp_path, monkeypatch):
    init_cartridge(tmp_path, "Atomic index")
    add_memory(tmp_path, kind="note", title="First fact", body="First searchable body.")
    assert search.rebuild_index(tmp_path, force=True)
    db_path = tmp_path / "indexes" / "memory.sqlite"
    assert _count(db_path) == 1

    add_memory(
        tmp_path, kind="note", title="Second fact",
        body="Second searchable body.", reindex=False,
    )
    real_replace = search.os.replace

    def fail_final_activation(source, destination):
        if str(destination) == str(db_path):
            raise OSError("simulated activation failure")
        return real_replace(source, destination)

    monkeypatch.setattr(search.os, "replace", fail_final_activation)
    with pytest.raises(OSError, match="activation failure"):
        search.rebuild_index(tmp_path, force=True)

    assert _count(db_path) == 1


def test_index_inspection_is_read_only_and_reports_staleness(tmp_path):
    init_cartridge(tmp_path, "Index health")
    add_memory(tmp_path, kind="note", title="Indexed fact", body="Searchable material.")
    search.rebuild_index(tmp_path, force=True)
    assert search.inspect_index(tmp_path)["healthy"] is True

    add_memory(
        tmp_path, kind="note", title="New fact",
        body="Not indexed yet.", reindex=False,
    )
    health = search.inspect_index(tmp_path)
    assert health["healthy"] is False
    assert "cardinality mismatch" in health["error"]


def test_validation_failure_removes_partial_replacement(tmp_path, monkeypatch):
    init_cartridge(tmp_path, "Partial cleanup")
    add_memory(tmp_path, kind="note", title="A fact", body="Searchable body.", reindex=False)

    real_connect = search.sqlite3.connect

    class BadCountConnection:
        def __init__(self, connection):
            self.connection = connection

        def __getattr__(self, name):
            return getattr(self.connection, name)

        def execute(self, sql, *args, **kwargs):
            cursor = self.connection.execute(sql, *args, **kwargs)
            if "COUNT(*) FROM documents_fts" in sql:
                class BadCursor:
                    def fetchone(self):
                        return (0,)
                return BadCursor()
            return cursor

    def wrapped_connect(path, *args, **kwargs):
        connection = real_connect(path, *args, **kwargs)
        if ".build-" in str(path):
            return BadCountConnection(connection)
        return connection

    monkeypatch.setattr(search.sqlite3, "connect", wrapped_connect)
    with pytest.raises(RuntimeError, match="validation failed"):
        search.rebuild_index(tmp_path, force=True)
    assert list((tmp_path / "indexes").glob("*.tmp")) == []


def test_status_does_not_initialize_missing_cartridge(tmp_path, capsys):
    missing = tmp_path / "not-created"
    status(missing)
    assert "not initialized" in capsys.readouterr().out
    assert not missing.exists()
